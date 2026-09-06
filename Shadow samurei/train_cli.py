#!/usr/bin/env python3
"""Trainings-Modus für Shadow – paralleles Training auf mehreren Geräten.

Dieses Modul ist bewusst schlank: es importiert nur PyTorch (über
``model_manager``) und benötigt weder den Rust-Kern noch customtkinter.
So lässt sich ``python main.py --modus train`` auch ohne gebauten
Rust-Kern ausführen – das Training läuft rein in Python/PyTorch.

Aufruf:

    python main.py --modus train                  # 4 Aufgaben, Gerät auto
    python main.py --modus train --parallel 2     # 2 Aufgaben gleichzeitig
    python main.py --modus train --geraet cpu     # nur auf der CPU
    python main.py --modus train --geraet npu     # nur auf der NPU (torch_npu)
    python main.py --modus train --geraet tpu     # nur auf der TPU (torch_xla)
    python main.py --modus train --epochs 20      # 20 Epochen je Auftrag
"""
from __future__ import annotations

import os
from typing import Any

#: Standardwerte, falls config.yaml oder der Rust-Kern fehlen.
_STANDARD = {
    "logging": {"level": "INFO", "colored": True, "log_file": None},
    "hardware": {"device": "auto", "use_4bit": True, "use_fp16": True,
                 "weights_dtype": "fp32"},
    "training": {"num_epochs": 3, "learning_rate": 2e-4},
}


def _lade_konfiguration_robust() -> dict[str, Any]:
    """Lädt config.yaml; ohne yaml oder ohne Datei gelten die Standardwerte."""
    konfiguration = {k: dict(v) for k, v in _STANDARD.items()}
    try:
        import yaml

        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        with open(pfad, encoding="utf-8") as datei:
            geladen = yaml.safe_load(datei) or {}
        for schluessel, wert in geladen.items():
            if isinstance(wert, dict) and isinstance(konfiguration.get(schluessel), dict):
                konfiguration[schluessel].update(wert)
            else:
                konfiguration[schluessel] = wert
    except Exception:
        pass
    return konfiguration


def _protokolliere(stufe: str, meldung: str) -> None:
    """Gibt eine Protokollzeile aus (farblos, ohne Abhängigkeit zum Kern)."""
    print(f"[{stufe}] {meldung}")


def run_train(parallel: int = 0, geraet: str | None = None,
              epochs: int | None = None, anzahl: int = 4) -> int:
    """Startet das (parallele) Training und gibt den Rückgabewert zurück.

    Ohne PyTorch wird ein Hinweis ausgegeben und der Modus beendet. Mit
    PyTorch werden ``anzahl`` Aufgaben gleichzeitig trainiert – verteilt
    auf alle verfügbaren Geräte (CUDA, MPS, XPU, NPU, TPU, CPU) bzw. auf
    das per ``geraet`` gewählte Gerät.
    """
    konfiguration = _lade_konfiguration_robust()
    _protokolliere("INFO", "Starte Trainings-Modus ...")

    # Konfiguration in die Parameter übernehmen – CLI-Argumente haben Vorrang.
    hardware = konfiguration.get("hardware", {})
    parallel_cfg = hardware.get("parallel", {}) or {}
    training_cfg = konfiguration.get("training", {}) or {}

    if geraet is None:
        geraet_wunsche = hardware.get("device")
        if geraet_wunsche and geraet_wunsche != "auto":
            geraet = geraet_wunsche
    if parallel <= 0:
        parallel = int(parallel_cfg.get("max_workers", 0) or 0)
    strategie = parallel_cfg.get("strategy", "balance")
    if epochs is None or epochs <= 0:
        epochs = int(training_cfg.get("num_epochs", 5) or 5)
    lr = float(training_cfg.get("learning_rate", 1e-2) or 1e-2)

    try:
        from model_manager import geraet_info, train_parallel
    except Exception as fehler:
        print("Der Trainings-Modus benötigt AI-Abhängigkeiten (PyTorch/transformers).")
        print(f"Grund: {fehler}")
        print("Aktiviere mit: python start.py --mit-torch")
        return 1

    info = geraet_info()
    print("\nShadow – Trainings-Modus")
    print(f"Verfügbare Geräte: {info['verfuegbare_geraete']}")
    print(f"  cuda={info['cuda']} mps={info['mps']} xpu={info['xpu']} "
          f"npu={info['npu']} tpu={info['tpu']}")
    print(f"Aufträge: {anzahl} | Parallel: {parallel or 'auto'} | "
          f"Gerät: {geraet or 'auto'} | Epochen je Auftrag: {epochs} | "
          f"Strategie: {strategie}")
    print()

    aufgaben = [
        {"task_id": i, "epochs": epochs, "lr": lr, "seed": i * 7 + 1}
        for i in range(anzahl)
    ]
    try:
        ergebnisse = train_parallel(
            aufgaben,
            max_workers=parallel if parallel > 0 else None,
            strategie=strategie,
            geraet_wunsch=geraet,
        )
    except Exception as fehler:
        _protokolliere("ERROR", f"Fehler beim Training: {fehler}")
        print(f"Fehler: {fehler}")
        return 1

    print("Ergebnisse:")
    for eintrag in ergebnisse:
        if "fehler" in eintrag:
            print(f"  Aufgabe {eintrag['task_id']}: FEHLER – {eintrag['fehler']}")
            continue
        print(
            f"  Aufgabe {eintrag['task_id']}: Gerät={eintrag['device']} "
            f"Verlust={eintrag['loss']:.4f} Treffer={eintrag['accuracy']:.3f} "
            f"Checkpoint={eintrag['checkpoint_id']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_train())
