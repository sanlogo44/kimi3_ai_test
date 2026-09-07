"""
trainer.py – LLM-Trainer für Shadow (LoRA-Fine-Tuning)

Passt zur Projektstruktur: liest config.yaml, nutzt kern.protokoll,
speichert Metriken über kern.metriken und Checkpoints über kern.checkpoints.

Start:
    python trainer.py --daten data/trainingsdaten.jsonl
    python trainer.py --daten data/trainingsdaten.jsonl --schichten 16,17 --epochen 3
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

# --- optionale Abhängigkeiten (Oberfläche läuft auch ohne PyTorch) ----------
try:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    HAT_TORCH = True
except ImportError:
    HAT_TORCH = False

from config_loader import lade_konfiguration
from logger import log
from analytics import metriken


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def lade_daten(pfad: str, tokenizer, max_laenge: int = 2048) -> "Dataset":
    """Liest eine JSONL-Datei mit Feldern {'anweisung', 'antwort'} ein."""
    zeilen = []
    with open(pfad, "r", encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile:
                zeilen.append(json.loads(zeile))

    def formatieren(beispiel: dict) -> dict:
        # Chat-Format, wie es das Basismodell erwartet
        text = (
            f"<|im_start|>user\n{beispiel['anweisung']}<|im_end|>\n"
            f"<|im_start|>assistant\n{beispiel['antwort']}<|im_end|>"
        )
        return tokenizer(text, truncation=True, max_length=max_laenge)

    datensatz = Dataset.from_list(zeilen)
    return datensatz.map(formatieren, remove_columns=datensatz.column_names)


def baue_modell(konfig: dict):
    """Lädt Basismodell und hängt LoRA-Adapter an."""
    geraet = konfig["hardware"].get("device", "auto")
    if geraet == "auto":
        geraet = "cuda" if torch.cuda.is_available() else "cpu"

    laden_kwargs = {"torch_dtype": torch.float16}
    if konfig["hardware"].get("use_4bit") and geraet == "cuda":
        from transformers import BitsAndBytesConfig

        laden_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16
        )

    modell = AutoModelForCausalLM.from_pretrained(
        konfig["model"]["name"], **laden_kwargs
    )
    tokenizer = AutoTokenizer.from_pretrained(konfig["model"]["name"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    modell = get_peft_model(modell, lora)
    modell.print_trainable_parameters()
    return modell, tokenizer, geraet


# ---------------------------------------------------------------------------
# Haupteingang
# ---------------------------------------------------------------------------

def trainieren(
    daten_pfad: str,
    epochen: int = 3,
    lernrate: float = 2e-4,
    batch_groesse: int = 4,
    ausgabe: str = "data/checkpoints/letztes_training",
) -> None:
    if not HAT_TORCH:
        log("PyTorch/transformers fehlt – Training gesperrt.", stufe="FEHLER")
        return

    konfig = lade_konfiguration()
    modell, tokenizer, geraet = baue_modell(konfig)

    datensatz = lade_daten(daten_pfad, tokenizer)
    log(f"{len(datensatz)} Beispiele geladen. Starte Training auf {geraet} …")

    args = TrainingArguments(
        output_dir=ausgabe,
        num_train_epochs=epochen,
        per_device_train_batch_size=batch_groesse,
        learning_rate=lernrate,
        logging_steps=10,
        save_strategy="epoch",
        report_to=[],
    )

    trainer = Trainer(
        model=modell,
        args=args,
        train_dataset=datensatz,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    start = time.time()
    trainer.train()
    dauer = time.time() - start

    # Metriken im Shadow-Stil speichern
    metriken.eintragen(
        "training",
        {"epochen": epochen, "beispiele": len(datensatz),
         "dauer_sekunden": round(dauer, 1), "ausgabe": ausgabe},
    )
    modell.save_pretrained(ausgabe)
    tokenizer.save_pretrained(ausgabe)
    log(f"Training fertig nach {dauer / 60:.1f} min. Adapter: {ausgabe}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shadow LLM-Trainer")
    parser.add_argument("--daten", required=True, help="JSONL mit anweisung/antwort")
    parser.add_argument("--epochen", type=int, default=3)
    parser.add_argument("--lernrate", type=float, default=2e-4)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--ausgabe", default="data/checkpoints/letztes_training")
    cli = parser.parse_args()
    trainieren(cli.daten, cli.epochen, cli.lernrate, cli.batch, cli.ausgabe)
