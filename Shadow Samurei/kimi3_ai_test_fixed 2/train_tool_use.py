#!/usr/bin/env python3
"""Feinabstimmung eines Sprachmodells auf Werkzeug-Nutzung.

Das Skript erzeugt aus den registrierten MCP-Werkzeugen einen
Trainingsdatensatz aus Beispieldialogen und startet damit eine
Feinabstimmung (LoRA, sofern ``peft`` verfügbar ist).

Ohne installierte Modellbibliotheken lässt sich der Datensatz mit
``--trockenlauf`` erzeugen und prüfen::

    python train_tool_use.py --trockenlauf
    python train_tool_use.py --epochen 3
"""
from __future__ import annotations

import argparse
import json
import os
import random
from typing import Any

from config_loader import load_config
from logger import get_logger
from mcp_protocol import MCPClient
from tools import create_math_tools

#: Beispielfragen je Werkzeug – Grundlage der synthetischen Dialoge
BEISPIELE: dict[str, list[tuple[str, dict[str, Any]]]] = {
    "calculator": [
        ("Wie viel ist {a} mal {b}?", {}),
        ("Berechne bitte {a} + {b} * 2.", {}),
        ("Was ergibt die Wurzel aus {c}?", {}),
    ],
    "get_weather": [
        ("Wie ist das Wetter in {ort}?", {}),
        ("Brauche ich in {ort} eine Jacke?", {}),
    ],
    "web_search": [
        ("Suche mir Informationen zu {thema}.", {}),
        ("Finde drei Quellen über {thema}.", {}),
    ],
    "get_current_time": [
        ("Wie spät ist es gerade?", {}),
        ("Welches Datum haben wir heute?", {}),
    ],
}

ORTE = ["Scharbeutz", "Lübeck", "Hamburg", "Kiel", "Timmendorfer Strand"]
THEMEN = [
    "das MCP-Protokoll",
    "Feinabstimmung von Sprachmodellen",
    "LoRA-Adapter",
    "Werkzeug-Nutzung durch KI",
]


def _argumente_fuer(werkzeug: str, zufall: random.Random) -> tuple[str, dict[str, Any]]:
    """Erzeugt eine Beispielfrage und die passenden Werkzeug-Argumente."""
    vorlage, _ = zufall.choice(BEISPIELE[werkzeug])
    if werkzeug == "calculator":
        a, b, c = zufall.randint(2, 99), zufall.randint(2, 99), zufall.choice([16, 25, 81, 144])
        frage = vorlage.format(a=a, b=b, c=c)
        if "Wurzel" in vorlage:
            return frage, {"expression": f"sqrt({c})"}
        if "+" in vorlage:
            return frage, {"expression": f"{a}+{b}*2"}
        return frage, {"expression": f"{a}*{b}"}
    if werkzeug == "get_weather":
        ort = zufall.choice(ORTE)
        return vorlage.format(ort=ort), {"location": ort}
    if werkzeug == "web_search":
        thema = zufall.choice(THEMEN)
        return vorlage.format(thema=thema), {"query": thema, "num_results": 3}
    return vorlage, {}


def erzeuge_datensatz(
    anzahl: int = 240, ausgabepfad: str = "data/werkzeug_training.jsonl", seed: int = 7
) -> list[dict[str, Any]]:
    """Erzeugt Beispieldialoge für die Werkzeug-Nutzung und speichert sie."""
    zufall = random.Random(seed)
    server = create_math_tools()
    client = MCPClient(server)
    system = client.get_system_prompt_with_tools()
    werkzeuge = list(BEISPIELE.keys())

    beispiele: list[dict[str, Any]] = []
    for nummer in range(anzahl):
        werkzeug = werkzeuge[nummer % len(werkzeuge)]
        frage, argumente = _argumente_fuer(werkzeug, zufall)
        aufruf = json.dumps(
            {"tool_call": {"name": werkzeug, "arguments": argumente}}, ensure_ascii=False
        )
        beispiele.append(
            {
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": frage},
                    {"role": "assistant", "content": aufruf},
                ],
                "werkzeug": werkzeug,
            }
        )

    zufall.shuffle(beispiele)
    ordner = os.path.dirname(os.path.abspath(ausgabepfad))
    os.makedirs(ordner, exist_ok=True)
    with open(ausgabepfad, "w", encoding="utf-8") as datei:
        for beispiel in beispiele:
            datei.write(json.dumps(beispiel, ensure_ascii=False) + "\n")
    return beispiele


def _als_text(beispiel: dict[str, Any]) -> str:
    """Wandelt einen Dialog in einen Llama-3-Trainingstext um."""
    teile = []
    for nachricht in beispiel["messages"]:
        teile.append(
            f"<|start_header_id|>{nachricht['role']}<|end_header_id|>\n"
            f"{nachricht['content']}<|eot_id|>"
        )
    return "\n".join(teile)


def train(
    epochen: int | None = None,
    anzahl_beispiele: int = 240,
    ausgabeordner: str | None = None,
    trockenlauf: bool = False,
) -> dict[str, Any]:
    """Führt die Feinabstimmung auf Werkzeug-Nutzung durch."""
    konfiguration = load_config()
    protokoll = get_logger(konfiguration)
    training_cfg = konfiguration.get("training", {})
    modell_name = konfiguration.get("model", {}).get(
        "name", "meta-llama/Meta-Llama-3-8B-Instruct"
    )
    ausgabeordner = ausgabeordner or training_cfg.get("output_dir", "./tool_model")
    epochen = int(epochen or training_cfg.get("num_epochs", 3))

    protokoll.info("Erzeuge Trainingsdaten für die Werkzeug-Nutzung ...")
    beispiele = erzeuge_datensatz(anzahl=anzahl_beispiele)
    protokoll.info(f"{len(beispiele)} Beispieldialoge erzeugt.")

    verteilung: dict[str, int] = {}
    for beispiel in beispiele:
        verteilung[beispiel["werkzeug"]] = verteilung.get(beispiel["werkzeug"], 0) + 1
    protokoll.info(f"Verteilung je Werkzeug: {verteilung}")

    if trockenlauf:
        protokoll.info("Trockenlauf – es wird nicht trainiert.")
        return {
            "trainiert": False,
            "beispiele": len(beispiele),
            "verteilung": verteilung,
            "ausgabeordner": ausgabeordner,
        }

    try:
        import torch
        from datasets import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as fehler:
        protokoll.error(
            "Für das Training werden torch, transformers und datasets benötigt: "
            f"{fehler}"
        )
        return {
            "trainiert": False,
            "fehler": str(fehler),
            "beispiele": len(beispiele),
            "verteilung": verteilung,
        }

    protokoll.info(f"Lade Modell {modell_name} ...")
    zerleger = AutoTokenizer.from_pretrained(modell_name, trust_remote_code=True)
    if zerleger.pad_token is None:
        zerleger.pad_token = zerleger.eos_token

    maximale_laenge = int(training_cfg.get("max_length", 2048))
    texte = [_als_text(beispiel) for beispiel in beispiele]

    def zerlegen(stapel):
        """Zerlegt die Trainingstexte in Token."""
        return zerleger(
            stapel["text"], truncation=True, max_length=maximale_laenge, padding=False
        )

    datensatz = Dataset.from_dict({"text": texte}).map(
        zerlegen, batched=True, remove_columns=["text"]
    )

    modell = AutoModelForCausalLM.from_pretrained(
        modell_name,
        dtype=torch.float32 if not torch.cuda.is_available() else torch.float16,
        trust_remote_code=True,
    )

    try:  # LoRA nur nutzen, wenn peft installiert ist
        from peft import LoraConfig, get_peft_model

        modell = get_peft_model(
            modell,
            LoraConfig(
                r=16,
                lora_alpha=32,
                lora_dropout=0.05,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=["q_proj", "v_proj"],
            ),
        )
        protokoll.info("LoRA-Adapter aktiv – es werden nur wenige Gewichte trainiert.")
    except ImportError:
        protokoll.warning("peft ist nicht installiert – vollständige Feinabstimmung.")

    argumente = TrainingArguments(
        output_dir=ausgabeordner,
        num_train_epochs=epochen,
        per_device_train_batch_size=int(training_cfg.get("batch_size", 1)),
        gradient_accumulation_steps=int(
            training_cfg.get("gradient_accumulation_steps", 8)
        ),
        learning_rate=float(training_cfg.get("learning_rate", 2e-4)),
        logging_steps=10,
        save_strategy="epoch",
        report_to=[],
    )

    trainer = Trainer(
        model=modell,
        args=argumente,
        train_dataset=datensatz,
        data_collator=DataCollatorForLanguageModeling(zerleger, mlm=False),
    )
    protokoll.info(f"Starte Training über {epochen} Epochen ...")
    ergebnis = trainer.train()
    trainer.save_model(ausgabeordner)
    zerleger.save_pretrained(ausgabeordner)
    protokoll.info(f"Training abgeschlossen. Modell gespeichert unter {ausgabeordner}.")

    return {
        "trainiert": True,
        "beispiele": len(beispiele),
        "verteilung": verteilung,
        "ausgabeordner": ausgabeordner,
        "verlust": float(getattr(ergebnis, "training_loss", 0.0) or 0.0),
    }


def _lies_argumente() -> argparse.Namespace:
    """Liest die Kommandozeilenargumente."""
    from argumente import _DeutscheHilfe, deutscher_zerleger

    zerleger = deutscher_zerleger(
        description="Feinabstimmung auf die Nutzung von Werkzeugen",
        formatter_class=_DeutscheHilfe,
    )
    zerleger.add_argument("--epochen", type=int, default=None, help="Anzahl der Epochen")
    zerleger.add_argument(
        "--beispiele", type=int, default=240, help="Anzahl der Trainingsdialoge"
    )
    zerleger.add_argument(
        "--ausgabeordner", default=None, help="Zielordner für das trainierte Modell"
    )
    zerleger.add_argument(
        "--trockenlauf",
        action="store_true",
        help="Nur den Datensatz erzeugen und prüfen, nicht trainieren",
    )
    return zerleger.parse_args()


if __name__ == "__main__":
    argumente = _lies_argumente()
    bericht = train(
        epochen=argumente.epochen,
        anzahl_beispiele=argumente.beispiele,
        ausgabeordner=argumente.ausgabeordner,
        trockenlauf=argumente.trockenlauf,
    )
    print(json.dumps(bericht, ensure_ascii=False, indent=2))
