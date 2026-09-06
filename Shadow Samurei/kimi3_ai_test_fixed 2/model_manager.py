"""Modellverwaltung: Checkpoints, Schicht-Training, SOUP und Weitertraining.

Das Original-Modell wird nie überschrieben: jedes Weitertraining arbeitet auf
einer Kopie, und jeder Checkpoint wird beim Laden als frisches Modell
aufgebaut. Die englischen Funktionsnamen bleiben erhalten, weil Web-Oberfläche,
Dashboard und Kommandozeile sie verwenden.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Callable

import torch
import torch.nn as nn

CHECKPOINT_ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "checkpoints")
os.makedirs(CHECKPOINT_ORDNER, exist_ok=True)

# Rückwärtskompatibler Name
CKPT_DIR = CHECKPOINT_ORDNER

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
GERAET = DEVICE


class ToyModel(nn.Module):
    """Demo-Netz mit benannten Schichten (layer1 bis layer4).

    Die Namen erlauben es, einzelne Schichten gezielt zu trainieren und alle
    übrigen einzufrieren.
    """

    def __init__(self, in_dim: int = 16, hidden: int = 32, out_dim: int = 3):
        super().__init__()
        self.layer1 = nn.Linear(in_dim, hidden)
        self.layer2 = nn.Linear(hidden, hidden)
        self.layer3 = nn.Linear(hidden, hidden)
        self.layer4 = nn.Linear(hidden, out_dim)
        self.activation = nn.ReLU()

    def forward(self, eingabe: torch.Tensor) -> torch.Tensor:
        """Berechnet die Ausgabe des Netzes."""
        zwischenwert = self.activation(self.layer1(eingabe))
        zwischenwert = self.activation(self.layer2(zwischenwert))
        zwischenwert = self.activation(self.layer3(zwischenwert))
        return self.layer4(zwischenwert)

    def layer_names(self) -> list[str]:
        """Gibt die Namen aller trainierbaren Schichten zurück."""
        return [name for name, _ in self.named_children() if name.startswith("layer")]

    # Deutscher Aliasname
    schichtnamen = layer_names


def freeze_except(model: nn.Module, train_layers: list[str] | None) -> list[str]:
    """Friert alle Schichten ein, die nicht in ``train_layers`` stehen.

    Gibt die Namen der tatsächlich trainierbaren Schichten zurück.
    """
    if not train_layers:
        for parameter in model.parameters():
            parameter.requires_grad = True
        return [name for name, _ in model.named_children() if name.startswith("layer")]

    gewuenscht = set(train_layers)
    aktiv: list[str] = []
    for name, modul in model.named_children():
        trainierbar = name in gewuenscht
        for parameter in modul.parameters():
            parameter.requires_grad = trainierbar
        if trainierbar:
            aktiv.append(name)
    return aktiv


def soup(models: list[nn.Module]) -> nn.Module:
    """Mittelt die Gewichte mehrerer Modelle zu einem neuen Modell.

    Die Modelle müssen dieselbe Struktur haben. Das Ergebnis ist ein neues
    Modell; die Eingabemodelle bleiben unverändert.
    """
    if not models:
        raise ValueError("Für ein SOUP-Modell wird mindestens ein Modell benötigt.")

    gemittelt = ToyModel().to(DEVICE)
    zustaende = [modell.state_dict() for modell in models]
    neuer_zustand = {}
    for schluessel in zustaende[0]:
        summe = sum(zustand[schluessel].float().to(DEVICE) for zustand in zustaende)
        neuer_zustand[schluessel] = summe / len(zustaende)
    gemittelt.load_state_dict(neuer_zustand)
    return gemittelt


def synthetic_data(n: int = 512, in_dim: int = 16, out_dim: int = 3, seed: int = 0):
    """Erzeugt einen reproduzierbaren künstlichen Datensatz."""
    zufall = torch.Generator().manual_seed(seed)
    merkmale = torch.randn(n, in_dim, generator=zufall)
    gewichte = torch.randn(in_dim, out_dim, generator=zufall)
    ziele = (
        merkmale @ gewichte + 0.1 * torch.randn(n, out_dim, generator=zufall)
    ).argmax(1)
    return merkmale, ziele


def evaluate(model: nn.Module, X: torch.Tensor, y: torch.Tensor) -> float:
    """Berechnet die Trefferquote des Modells auf den übergebenen Daten."""
    war_im_training = model.training
    model.eval()
    with torch.no_grad():
        vorhersage = model(X.to(DEVICE)).argmax(1)
        genauigkeit = (vorhersage == y.to(DEVICE)).float().mean().item()
    if war_im_training:
        model.train()
    return genauigkeit


def train_step(
    model: nn.Module,
    X: torch.Tensor,
    y: torch.Tensor,
    epochs: int = 10,
    lr: float = 1e-2,
    train_layers: list[str] | None = None,
    token_callback: Callable[[int], None] | None = None,
    progress_callback: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Trainiert das Modell und gibt die Kennzahlen des Laufs zurück.

    ``train_layers=None`` trainiert alle Schichten, sonst nur die genannten.
    ``token_callback`` meldet den simulierten Tokenverbrauch,
    ``progress_callback`` den Fortschritt (Epoche, Gesamtzahl, Verlust).
    """
    epochs = max(1, int(epochs))
    aktive_schichten = freeze_except(model, train_layers)
    parameter = [p for p in model.parameters() if p.requires_grad]
    if not parameter:
        raise ValueError("Es ist keine Schicht zum Trainieren ausgewählt.")

    optimierer = torch.optim.Adam(parameter, lr=lr)
    verlust_funktion = nn.CrossEntropyLoss()
    daten_x, daten_y = X.to(DEVICE), y.to(DEVICE)
    model.train()

    tokens = 0
    verlaufe: list[dict[str, float]] = []
    start = time.time()
    letzter_verlust = 0.0
    for epoche in range(epochs):
        optimierer.zero_grad()
        ausgabe = model(daten_x)
        verlust = verlust_funktion(ausgabe, daten_y)
        verlust.backward()
        optimierer.step()

        letzter_verlust = float(verlust.item())
        tokens += daten_x.numel() + ausgabe.numel()  # simulierte Tokenzählung
        verlaufe.append({"epoch": epoche + 1, "loss": letzter_verlust, "lr": lr})
        if token_callback:
            token_callback(tokens)
        if progress_callback:
            progress_callback(epoche + 1, epochs, letzter_verlust)

    return {
        "train_time": time.time() - start,
        "tokens": tokens,
        "accuracy": evaluate(model, daten_x, daten_y),
        "loss": letzter_verlust,
        "history": verlaufe,
        "layers": aktive_schichten,
    }


# --------------------------------------------------------------- Checkpoints
def save_checkpoint(model: nn.Module, name: str, meta: dict[str, Any] | None = None) -> str:
    """Speichert das Modell samt Zusatzinformationen und gibt die Kennung zurück."""
    kennung = uuid.uuid4().hex[:8]
    sicherer_name = "".join(
        zeichen if zeichen.isalnum() or zeichen in "-_" else "_" for zeichen in name
    ) or "checkpoint"
    pfad = os.path.join(CHECKPOINT_ORDNER, f"{kennung}_{sicherer_name}.pt")
    torch.save(
        {
            "state_dict": model.state_dict(),
            "meta": {
                "id": kennung,
                "name": name,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                **(meta or {}),
            },
        },
        pfad,
    )
    return kennung


def list_checkpoints() -> list[dict[str, Any]]:
    """Listet alle gespeicherten Checkpoints mit ihren Zusatzinformationen."""
    ergebnis: list[dict[str, Any]] = []
    if not os.path.isdir(CHECKPOINT_ORDNER):
        return ergebnis
    for datei in sorted(os.listdir(CHECKPOINT_ORDNER)):
        if not datei.endswith(".pt"):
            continue
        try:
            inhalt = torch.load(
                os.path.join(CHECKPOINT_ORDNER, datei),
                map_location=DEVICE, weights_only=False,
            )
            ergebnis.append(inhalt["meta"])
        except (OSError, KeyError, RuntimeError):
            # Beschädigte oder fremde Dateien werden übersprungen.
            continue
    return ergebnis


def load_checkpoint(cid: str) -> tuple[nn.Module, dict[str, Any]]:
    """Lädt einen Checkpoint als frische Kopie; das Original bleibt unberührt."""
    for datei in os.listdir(CHECKPOINT_ORDNER):
        if datei.startswith(cid) and datei.endswith(".pt"):
            inhalt = torch.load(
                os.path.join(CHECKPOINT_ORDNER, datei),
                map_location=DEVICE, weights_only=False,
            )
            modell = ToyModel().to(DEVICE)
            modell.load_state_dict(inhalt["state_dict"])
            return modell, inhalt["meta"]
    raise FileNotFoundError(f"Kein Checkpoint mit der Kennung {cid} gefunden.")


def delete_checkpoint(cid: str) -> bool:
    """Löscht einen Checkpoint und meldet, ob etwas entfernt wurde."""
    for datei in os.listdir(CHECKPOINT_ORDNER):
        if datei.startswith(cid) and datei.endswith(".pt"):
            os.remove(os.path.join(CHECKPOINT_ORDNER, datei))
            return True
    return False


def exportiere_uebersicht(pfad: str | None = None) -> str:
    """Schreibt eine JSON-Übersicht aller Checkpoints und gibt den Pfad zurück."""
    ziel = pfad or os.path.join(os.path.dirname(CHECKPOINT_ORDNER), "checkpoints.json")
    with open(ziel, "w", encoding="utf-8") as datei:
        json.dump(list_checkpoints(), datei, indent=2, ensure_ascii=False)
    return ziel
