"""Brücke zwischen der Rust-Weboberfläche und dem Python-Modellkern.

Die Weboberfläche ist in Rust geschrieben, der Modellkern (PyTorch) bleibt
Python. Rust startet diese Datei als **einen langlebigen Prozess** und tauscht
mit ihm zeilenweise JSON-Objekte aus:

    Anfrage:  {"befehl": "<name>", "daten": { ... }}
    Antwort:  {"ok": true, "daten": { ... }}
              {"ok": false, "fehler": "deutsche Meldung", "status": 503}

Auf ``stdout`` steht ausschließlich die Antwortzeile. Alle Ausgaben von
PyTorch oder vom Modellcode werden nach ``stderr`` umgeleitet.

PyTorch wird erst beim ersten Bedarf geladen. Fehlt es, startet der Prozess
trotzdem und beantwortet jeden Befehl außer ``benchmarks_status`` mit dem
Status 503 und einer verständlichen Meldung.

Das Protokoll ist in ``bruecke_protokoll.md`` beschrieben.
"""
from __future__ import annotations

import contextlib
import copy
import json
import sys
import threading
from typing import Any, Callable

import analytics
import benchmarks

# Zustand der Brücke: Arbeitsmodell, Sperre und letzte Kernmeldung.
# Bewusst eine ``RLock``: ``trainiere`` hält die Sperre und ruft darin
# ``hole_arbeitsmodell`` auf, das sie erneut anfordert.
_modell: Any = None
_modell_sperre = threading.RLock()
_kern_fehler: str | None = None


class BrueckenFehler(Exception):
    """Fehler mit einer deutschen Meldung und einem HTTP-Status.

    Die Weboberfläche gibt den Status unverändert an den Browser weiter.
    """

    def __init__(self, meldung: str, status: int = 500):
        super().__init__(meldung)
        self.meldung = meldung
        self.status = status


# ------------------------------------------------------------- Modellkern
def hole_kern():
    """Importiert ``model_manager`` erst bei Bedarf.

    Rückgabe ist das Modul oder ``None``, wenn PyTorch fehlt. Im Fehlerfall
    steht die Meldung anschließend in ``_kern_fehler``.
    """
    global _kern_fehler
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import model_manager

        _kern_fehler = None
        return model_manager
    except Exception as fehler:  # ImportError, aber auch CUDA-Fehler
        _kern_fehler = (
            f"PyTorch ist nicht verfügbar ({fehler}). "
            "Bitte „pip install -r requirements.txt“ ausführen."
        )
        return None


def kern_oder_fehler():
    """Gibt den Modellkern zurück oder wirft den 503-Fehler.

    So muss jeder Befehl den fehlenden Baustein nicht selbst behandeln.
    """
    kern = hole_kern()
    if kern is None:
        raise BrueckenFehler(_kern_fehler or "PyTorch ist nicht verfügbar.", 503)
    return kern


def hole_arbeitsmodell(kern):
    """Gibt das Arbeitsmodell zurück und legt es beim ersten Aufruf an."""
    global _modell
    with _modell_sperre:
        if _modell is None:
            _modell = kern.ToyModel().to(kern.DEVICE)
        return _modell


# ----------------------------------------------------------------- Befehle
def befehl_bereit(daten: dict) -> dict:
    """Meldet, dass die Brücke läuft; lädt PyTorch, um es früh zu prüfen."""
    kern_oder_fehler()
    return {}


def befehl_schichten(daten: dict) -> dict:
    """Nennt die Namen aller trainierbaren Schichten des Demo-Netzes."""
    kern = kern_oder_fehler()
    with contextlib.redirect_stdout(sys.stderr):
        schichten = list(kern.ToyModel().layer_names())
    return {"schichten": schichten}


def befehl_checkpoints(daten: dict) -> dict:
    """Listet die gespeicherten Checkpoints unverändert auf.

    Scheitert das Lesen, bleibt die Liste leer; die Weboberfläche liest die
    Dateinamen dann selbst.
    """
    kern = kern_oder_fehler()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            liste = list(kern.list_checkpoints())
    except Exception:
        liste = []
    return {"checkpoints": liste}


def befehl_checkpoint_speichern(daten: dict) -> dict:
    """Speichert das Arbeitsmodell als neuen Checkpoint."""
    kern = kern_oder_fehler()
    name = daten.get("name") or "checkpoint"
    genauigkeit = daten.get("genauigkeit")
    with contextlib.redirect_stdout(sys.stderr):
        with _modell_sperre:
            kennung = kern.save_checkpoint(
                hole_arbeitsmodell(kern), name, {"accuracy": genauigkeit}
            )
    return {"kennung": kennung}


def befehl_checkpoint_loeschen(daten: dict) -> dict:
    """Löscht den Checkpoint mit der angegebenen Kennung."""
    kern = kern_oder_fehler()
    kennung = daten.get("kennung") or ""
    with contextlib.redirect_stdout(sys.stderr):
        geloescht = bool(kern.delete_checkpoint(kennung))
    return {"geloescht": geloescht}


def befehl_checkpoint_nutzen(daten: dict) -> dict:
    """Ersetzt das Arbeitsmodell durch einen gespeicherten Checkpoint."""
    global _modell
    kern = kern_oder_fehler()
    kennung = daten.get("kennung") or ""
    try:
        with contextlib.redirect_stdout(sys.stderr):
            modell, zusatz = kern.load_checkpoint(kennung)
    except (FileNotFoundError, KeyError):
        raise BrueckenFehler("Checkpoint nicht gefunden.", 404)
    with _modell_sperre:
        _modell = modell
    return {"geladen": zusatz.get("name", "unbekannt")}


def befehl_trainiere(daten: dict) -> dict:
    """Trainiert eine Kopie des Modells; das Original bleibt unberührt."""
    kern = kern_oder_fehler()
    try:
        epochen = max(1, int(daten.get("epochen", 10)))
        lernrate = float(daten.get("lernrate", 1e-2))
    except (TypeError, ValueError):
        raise BrueckenFehler("Epochen und Lernrate müssen Zahlen sein.", 400)

    basis = daten.get("basis") or None
    schichten = daten.get("schichten") or None

    with contextlib.redirect_stdout(sys.stderr):
        daten_x, daten_y = kern.synthetic_data()
        zusatz: dict[str, Any] = {"name": "original"}
        if basis:
            try:
                modell, zusatz = kern.load_checkpoint(basis)
            except (FileNotFoundError, KeyError):
                raise BrueckenFehler("Checkpoint nicht gefunden.", 404)
        else:
            with _modell_sperre:
                modell = copy.deepcopy(hole_arbeitsmodell(kern))

        werte = kern.train_step(
            modell, daten_x, daten_y, epochs=epochen, lr=lernrate,
            train_layers=schichten,
        )

    return {
        "genauigkeit": werte["accuracy"],
        "trainingszeit": werte["train_time"],
        "tokens": werte["tokens"],
        "verlust": werte.get("loss", 0.0),
        "modellname": zusatz.get("name", "unbekannt"),
    }


def befehl_soup(daten: dict) -> dict:
    """Mittelt mehrere Checkpoints und speichert das Ergebnis."""
    kern = kern_oder_fehler()
    kennungen = daten.get("kennungen") or []
    modelle = []
    with contextlib.redirect_stdout(sys.stderr):
        for kennung in kennungen:
            try:
                modelle.append(kern.load_checkpoint(kennung)[0])
            except (FileNotFoundError, KeyError):
                raise BrueckenFehler(f"Checkpoint {kennung} nicht gefunden.", 404)
        if len(modelle) < 2:
            raise BrueckenFehler("Bitte mindestens zwei Checkpoints wählen.", 400)

        gemittelt = kern.soup(modelle)
        daten_x, daten_y = kern.synthetic_data()
        genauigkeit = kern.evaluate(gemittelt, daten_x, daten_y)
        modellname = f"soup_aus_{len(modelle)}"
        kennung_neu = kern.save_checkpoint(
            gemittelt, modellname, {"accuracy": genauigkeit}
        )

    return {
        "genauigkeit": genauigkeit,
        "kennung": kennung_neu,
        "modellname": modellname,
    }


def befehl_benchmarks_starten(daten: dict) -> dict:
    """Startet die wiederkehrenden Vergleichsläufe im Hintergrund."""
    kern = kern_oder_fehler()
    with contextlib.redirect_stdout(sys.stderr):
        benchmarks.starte(kern, analytics)
        laeuft = benchmarks.laeuft()
    return {"laeuft": laeuft}


def befehl_benchmarks_stoppen(daten: dict) -> dict:
    """Stoppt die wiederkehrenden Vergleichsläufe."""
    kern_oder_fehler()
    with contextlib.redirect_stdout(sys.stderr):
        benchmarks.stoppe()
        laeuft = benchmarks.laeuft()
    return {"laeuft": laeuft}


def befehl_benchmarks_status(daten: dict) -> dict:
    """Nennt Zustand und Ergebnisse der Vergleichsläufe.

    Dieser Befehl braucht PyTorch nicht: ohne laufende Benchmarks ist die
    Antwort ``{"laeuft": false, "ergebnisse": []}``.
    """
    with contextlib.redirect_stdout(sys.stderr):
        return {
            "laeuft": benchmarks.laeuft(),
            "ergebnisse": benchmarks.ergebnisse(),
        }


# Zuordnung der Befehlsnamen auf ihre Bearbeiter.
BEFEHLE: dict[str, Callable[[dict], dict]] = {
    "bereit": befehl_bereit,
    "schichten": befehl_schichten,
    "checkpoints": befehl_checkpoints,
    "checkpoint_speichern": befehl_checkpoint_speichern,
    "checkpoint_loeschen": befehl_checkpoint_loeschen,
    "checkpoint_nutzen": befehl_checkpoint_nutzen,
    "trainiere": befehl_trainiere,
    "soup": befehl_soup,
    "benchmarks_starten": befehl_benchmarks_starten,
    "benchmarks_stoppen": befehl_benchmarks_stoppen,
    "benchmarks_status": befehl_benchmarks_status,
}


# ------------------------------------------------------------ Verarbeitung
def bearbeite_anfrage(anfrage: Any) -> dict:
    """Führt eine einzelne Anfrage aus und gibt die Antwort als Wörterbuch."""
    if not isinstance(anfrage, dict):
        return {"ok": False, "fehler": "Ungültige Anfrage.", "status": 400}

    name = anfrage.get("befehl")
    daten = anfrage.get("daten")
    if not isinstance(daten, dict):
        daten = {}

    bearbeiter = BEFEHLE.get(name) if isinstance(name, str) else None
    if bearbeiter is None:
        return {"ok": False, "fehler": f"Unbekannter Befehl: {name}", "status": 400}

    try:
        return {"ok": True, "daten": bearbeiter(daten)}
    except BrueckenFehler as fehler:
        return {"ok": False, "fehler": fehler.meldung, "status": fehler.status}
    except Exception as fehler:  # niemals den Prozess beenden
        return {
            "ok": False,
            "fehler": f"Unerwarteter Fehler in der Brücke: {fehler}",
            "status": 500,
        }


def bearbeite_zeile(zeile: str) -> dict:
    """Liest eine Zeile als JSON und beantwortet sie."""
    try:
        anfrage = json.loads(zeile)
    except (ValueError, TypeError):
        return {"ok": False, "fehler": "Ungültige Anfrage.", "status": 400}
    return bearbeite_anfrage(anfrage)


def sende(antwort: dict) -> None:
    """Schreibt genau eine Antwortzeile nach stdout und leert den Puffer."""
    sys.stdout.write(json.dumps(antwort, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def haupt() -> int:
    """Liest Anfragen von stdin, bis die Gegenseite die Verbindung schließt."""
    try:
        for zeile in sys.stdin:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                antwort = bearbeite_zeile(zeile)
            except Exception as fehler:  # letzte Absicherung
                antwort = {
                    "ok": False,
                    "fehler": f"Unerwarteter Fehler in der Brücke: {fehler}",
                    "status": 500,
                }
            sende(antwort)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        pass
    finally:
        with contextlib.suppress(Exception):
            benchmarks.stoppe()
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
