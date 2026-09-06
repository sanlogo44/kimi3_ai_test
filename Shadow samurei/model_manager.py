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


def _hat_cuda() -> bool:
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _hat_mps() -> bool:
    try:
        return bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    except Exception:
        return False


def _hat_xpu() -> bool:
    """Intel oneAPI-Gerät (intel_extension_for_pytorch)."""
    try:
        return bool(getattr(torch, "xpu", None) and torch.xpu.is_available())
    except Exception:
        return False


def _hat_npu() -> bool:
    """Huawei-Ascend-NPU (torch_npu). Nicht zu verwechseln mit OpenVINO-Inferenz."""
    try:
        import torch_npu  # noqa: F401
        return bool(torch.npu.is_available())
    except Exception:
        return False


def _hat_tpu() -> bool:
    """Google-TPU (torch_xla)."""
    try:
        import torch_xla.core.xla_model as xm  # noqa: F401
        return True
    except Exception:
        return False


def _xla_geraet():
    """Liefert das XLA-Geräteobjekt für die TPU oder None."""
    try:
        import torch_xla.core.xla_model as xm
        return xm.xla_device()
    except Exception:
        return None


def verfuegbare_geraete() -> list[str]:
    """Listet alle Geräte auf, die PyTorch direkt für ``.to(device)`` nutzen kann.

    Reihenfolge (Priorität): cuda, mps, xpu, npu, tpu, cpu.
    Für die TPU wird das Gerät über ``torch_xla`` bezogen; der Eintrag
    ``"tpu"`` ist ein Platzhalter, der in ``loese_geraet`` aufgelöst wird.
    """
    geraete: list[str] = []
    if _hat_cuda():
        anzahl = torch.cuda.device_count()
        for i in range(anzahl):
            geraete.append(f"cuda:{i}")
    if _hat_mps():
        geraete.append("mps")
    if _hat_xpu():
        anzahl = getattr(torch.xpu, "device_count", lambda: 1)()
        for i in range(anzahl):
            geraete.append(f"xpu:{i}")
    if _hat_npu():
        anzahl = getattr(torch.npu, "device_count", lambda: 1)()
        for i in range(anzahl):
            geraete.append(f"npu:{i}")
    if _hat_tpu():
        geraete.append("tpu")
    geraete.append("cpu")
    return geraete


def geraet_info() -> dict[str, Any]:
    """Liefert eine Statusübersicht aller erkannten Geräteklassen."""
    return {
        "cuda": _hat_cuda(),
        "mps": _hat_mps(),
        "xpu": _hat_xpu(),
        "npu": _hat_npu(),
        "tpu": _hat_tpu(),
        "verfuegbare_geraete": verfuegbare_geraete(),
    }


def loese_geraet(wunsch: str | None = "auto", index: int = 0):
    """Übersetzt einen Konfigurationswunsch in ein torch-fähiges Gerät.

    ``wunsch`` kann sein: ``auto``, ``cuda``, ``cuda:0``, ``mps``, ``xpu``,
    ``npu``, ``tpu`` oder ``cpu``. Bei ``auto`` wird das erste verfügbare Gerät
    in der Prioritätsreihenfolge gewählt. Ist ein Wunsch nicht verfügbar,
    fällt die Funktion auf die CPU zurück und liefert eine Warnung.
    """
    wunsch = (wunsch or "auto").strip().lower()

    if wunsch in ("auto", "", None):
        verfuegbar = verfuegbare_geraete()
        if not verfuegbar:
            return "cpu"
        # „tpu" ist nur ein Platzhalter – in ein echtes XLA-Gerät auflösen.
        if verfuegbar[0] == "tpu":
            xla = _xla_geraet()
            return xla if xla is not None else (verfuegbar[1] if len(verfuegbar) > 1 else "cpu")
        return verfuegbar[0]

    if wunsch == "cpu":
        return "cpu"

    if wunsch.startswith("cuda"):
        if _hat_cuda():
            if wunsch == "cuda":
                return f"cuda:{min(index, torch.cuda.device_count() - 1)}"
            return wunsch
        print(f"[model_manager] CUDA nicht verfügbar – falle auf CPU zurück (Wunsch: {wunsch}).")
        return "cpu"

    if wunsch == "mps":
        if _hat_mps():
            return "mps"
        print("[model_manager] MPS nicht verfügbar – falle auf CPU zurück.")
        return "cpu"

    if wunsch.startswith("xpu"):
        if _hat_xpu():
            return wunsch if wunsch != "xpu" else "xpu:0"
        print(f"[model_manager] XPU nicht verfügbar – falle auf CPU zurück (Wunsch: {wunsch}).")
        return "cpu"

    if wunsch.startswith("npu"):
        if _hat_npu():
            return wunsch if wunsch != "npu" else "npu:0"
        print(f"[model_manager] NPU nicht verfügbar – falle auf CPU zurück (Wunsch: {wunsch}).")
        return "cpu"

    if wunsch == "tpu":
        xla = _xla_geraet()
        if xla is not None:
            return xla
        print("[model_manager] TPU (torch_xla) nicht verfügbar – falle auf CPU zurück.")
        return "cpu"

    # Unbekannter Wunsch: sicherer Fallback.
    print(f"[model_manager] Unbekanntes Gerät „{wunsch}“ – verwende CPU.")
    return "cpu"


DEVICE = loese_geraet("auto")
GERAET = DEVICE


def _auf_geraet(geraet):
    """Löst ein Gerät für die Nutzung in ``.to()`` auf (String oder Objekt)."""
    if geraet is None:
        return DEVICE
    if isinstance(geraet, str) and geraet.lower() == "tpu":
        return _xla_geraet() or DEVICE
    return geraet


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


def soup(models: list[nn.Module], device=None) -> nn.Module:
    """Mittelt die Gewichte mehrerer Modelle zu einem neuen Modell.

    Die Modelle müssen dieselbe Struktur haben. Das Ergebnis ist ein neues
    Modell; die Eingabemodelle bleiben unverändert. ``device`` steuert, auf
    welchem Gerät das Ergebnis liegt (Standard: das global erkannte Gerät).
    """
    ziel = _auf_geraet(device)
    if not models:
        raise ValueError("Für ein SOUP-Modell wird mindestens ein Modell benötigt.")

    gemittelt = ToyModel().to(ziel)
    zustaende = [modell.state_dict() for modell in models]
    neuer_zustand = {}
    for schluessel in zustaende[0]:
        summe = sum(zustand[schluessel].float().to(ziel) for zustand in zustaende)
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


def evaluate(model: nn.Module, X: torch.Tensor, y: torch.Tensor, device=None) -> float:
    """Berechnet die Trefferquote des Modells auf den übergebenen Daten."""
    ziel = _auf_geraet(device)
    war_im_training = model.training
    model.eval()
    with torch.no_grad():
        vorhersage = model(X.to(ziel)).argmax(1)
        genauigkeit = (vorhersage == y.to(ziel)).float().mean().item()
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
    device=None,
) -> dict[str, Any]:
    """Trainiert das Modell und gibt die Kennzahlen des Laufs zurück.

    ``train_layers=None`` trainiert alle Schichten, sonst nur die genannten.
    ``token_callback`` meldet den simulierten Tokenverbrauch,
    ``progress_callback`` den Fortschritt (Epoche, Gesamtzahl, Verlust).
    ``device`` bestimmt das Trainingsgerät (Standard: global erkanntes Gerät).
    So lassen sich mehrere ``train_step``-Aufrufe parallel auf verschiedenen
    Geräten ausführen.
    """
    ziel = _auf_geraet(device)
    epochs = max(1, int(epochs))
    aktive_schichten = freeze_except(model, train_layers)
    parameter = [p for p in model.parameters() if p.requires_grad]
    if not parameter:
        raise ValueError("Es ist keine Schicht zum Trainieren ausgewählt.")

    optimierer = torch.optim.Adam(parameter, lr=lr)
    verlust_funktion = nn.CrossEntropyLoss()
    daten_x, daten_y = X.to(ziel), y.to(ziel)
    model.to(ziel)
    model.train()

    ist_xla = "xla" in str(ziel).lower()
    tokens = 0
    verlaufe: list[dict[str, float]] = []
    start = time.time()
    letzter_verlust = 0.0
    for epoche in range(epochs):
        optimierer.zero_grad()
        ausgabe = model(daten_x)
        verlust = verlust_funktion(ausgabe, daten_y)
        verlust.backward()
        if ist_xla:
            # Auf der TPU muss der Optimierungsschritt über XLA laufen.
            import torch_xla.core.xla_model as xm
            xm.optimizer_step(optimierer)
            xm.mark_step()
        else:
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
        "accuracy": evaluate(model, daten_x, daten_y, device=ziel),
        "loss": letzter_verlust,
        "history": verlaufe,
        "layers": aktive_schichten,
        "device": str(ziel),
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


def load_checkpoint(cid: str, device=None) -> tuple[nn.Module, dict[str, Any]]:
    """Lädt einen Checkpoint als frische Kopie; das Original bleibt unberührt."""
    ziel = _auf_geraet(device)
    for datei in os.listdir(CHECKPOINT_ORDNER):
        if datei.startswith(cid) and datei.endswith(".pt"):
            inhalt = torch.load(
                os.path.join(CHECKPOINT_ORDNER, datei),
                map_location=ziel, weights_only=False,
            )
            modell = ToyModel().to(ziel)
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


# ----------------------------------------------------------- Paralleles Training
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


def _geraet_fuer_index(verfuegbar: list, index: int, strategie: str):
    """Wählt ein Gerät für den ``index``-ten parallelen Auftrag.

    ``balance``: über alle verfügbaren Geräte rotieren.
    ``pin``: alle Aufträge auf das erste Gerät (Standard-Fallback).
    Fehlt nur die CPU, wird diese mehrfach genutzt.
    """
    if not verfuegbar:
        return DEVICE
    if strategie == "pin" or len(verfuegbar) == 1:
        return verfuegbar[0]
    return verfuegbar[index % len(verfuegbar)]


def train_parallel(
    aufgaben: list[dict[str, Any]],
    max_workers: int | None = None,
    strategie: str = "balance",
    geraet_wunsch: str | None = None,
) -> list[dict[str, Any]]:
    """Trainiert mehrere Aufgaben gleichzeitig auf mehreren Geräten.

    Jeder Eintrag in ``aufgaben`` ist ein dict mit den Schlüsseln für
    ``train_step`` (z. B. ``epochs``, ``lr``, ``train_layers``) plus einem
    optionalen ``task_id``. Pro Auftrag wird ein frisches Modell erzeugt, damit
    sich parallele Läufe nicht in denselben Gewichten stören.

    ``max_workers`` begrenzt die gleichzeitigen Aufträge (Standard: Anzahl der
    verfügbaren Geräte, mindestens 1). ``strategie`` ist ``balance`` (Last
    verteilen) oder ``pin`` (alle auf ein Gerät). ``geraet_wunsch`` erzwingt
    ein einzelnes Gerät (z. B. ``cpu`` oder ``cuda:0``).
    """
    if not aufgaben:
        return []

    verfuegbar = verfuegbare_geraete()
    if geraet_wunsch:
        verfuegbar = [loese_geraet(geraet_wunsch)]

    if max_workers is None or max_workers <= 0:
        # Standard: ein Worker pro nicht-CPU-Gerät, mindestens 1.
        nicht_cpu = [g for g in verfuegbar if not str(g).startswith("cpu")]
        max_workers = max(1, len(nicht_cpu) if nicht_cpu else 1)
    max_workers = max(1, min(max_workers, len(aufgaben)))

    sperr = threading.Lock()
    ergebnisse: list[dict[str, Any]] = [None] * len(aufgaben)  # type: ignore[list-item]

    def _arbeite(aufgaben_index: int) -> dict[str, Any]:
        aufgabe = aufgaben[aufgaben_index]
        task_id = aufgabe.get("task_id", aufgaben_index)
        ziel = _geraet_fuer_index(verfuegbar, aufgaben_index, strategie)
        # Platzhalter „tpu" in ein echtes XLA-Gerät auflösen, damit .to() klappt.
        ziel = _auf_geraet(ziel)
        frisches_modell = ToyModel().to(ziel)
        X, y = synthetic_data(
            n=aufgabe.get("n", 512),
            in_dim=aufgabe.get("in_dim", 16),
            out_dim=aufgabe.get("out_dim", 3),
            seed=aufgabe.get("seed", aufgaben_index),
        )
        ergebnis = train_step(
            frisches_modell,
            X,
            y,
            epochs=aufgabe.get("epochs", 10),
            lr=aufgabe.get("lr", 1e-2),
            train_layers=aufgabe.get("train_layers"),
            device=ziel,
        )
        ergebnis["task_id"] = task_id
        ergebnis["checkpoint_id"] = None
        if aufgabe.get("speichern", True):
            with sperr:
                ergebnis["checkpoint_id"] = save_checkpoint(
                    frisches_modell,
                    name=f"parallel_{task_id}",
                    meta={"task_id": task_id, "device": str(ziel)},
                )
        return ergebnis

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_index = {
            pool.submit(_arbeite, i): i for i in range(len(aufgaben))
        }
        for future in as_completed(future_index):
            i = future_index[future]
            try:
                ergebnisse[i] = future.result()
            except Exception as fehler:
                ergebnisse[i] = {
                    "task_id": aufgaben[i].get("task_id", i),
                    "fehler": str(fehler),
                }

    return ergebnisse
