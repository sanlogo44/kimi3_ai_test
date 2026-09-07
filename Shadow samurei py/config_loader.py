"""Konfigurationslader für die Anwendung.

Das Lesen der YAML- oder JSON-Datei und das Ergänzen fehlender Werte
übernimmt der Rust-Kern (``kimi3_kern.lade_konfiguration``). Dieses Modul ist
nur noch eine dünne Hülle darüber. Der Name ``DEFAULT_CONFIG`` bleibt
erhalten, weil andere Module ihn zum Nachschlagen verwenden.
"""
from __future__ import annotations

from typing import Any

from kern_modul import kern

#: Standardwerte, die der Kern über die Datei legt. Die Tabelle dient nur zum
#: Nachschlagen; verbindlich sind die Werte im Kern (``rust/kern/src/
#: konfiguration.rs``), die der Kern bei jedem Laden selbst einsetzt.
DEFAULT_CONFIG: dict[str, Any] = {
    "logging": {"level": "INFO", "colored": True, "log_file": None},
    "hardware": {"device": "auto", "use_4bit": True, "use_fp16": True, "weights_dtype": "fp32"},
    "model": {"name": "meta-llama/Meta-Llama-3-8B-Instruct", "max_tool_iterations": 5},
    "training": {"output_dir": "./tool_model", "batch_size": 1, "gradient_accumulation_steps": 8,
                 "num_epochs": 3, "learning_rate": 2e-4, "max_length": 2048},
    "auth": {"default_user": "Admin", "default_password": "1234",
             "force_password_change": True},
    "oberflaeche": {"erscheinungsbild": "System", "farbschema": "kimi"},
}


def load_config(path="config.yaml"):
    """Lädt die Konfiguration aus einer Datei oder nutzt die Standardwerte.

    Der Kern meldet eine fehlende oder unlesbare Datei selbst und gibt dann
    die Standardwerte zurück. Jeder Aufruf liefert ein neues Wörterbuch.
    """
    return kern.lade_konfiguration(path)
