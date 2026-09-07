"""Verwaltung der Checkpoint-Dateien in data/checkpoints/.

Die Dateien selbst schreibt und liest der Modellkern in Python
(PyTorch). Hier stehen die Aufgaben, die ohne PyTorch möglich sind:
die Liste aus den Dateinamen lesen, Dateien speichern/laden und
löschen.
"""

import json
import os
import secrets

from .pfade import datenordner, stelle_ordner_bereit
from .zeit import aus_sekunden


class Checkpoint:
    """Ein gespeicherter Checkpoint."""

    def __init__(self, kennung="", name="", genauigkeit=None, gespeichert_am=""):
        self.kennung = kennung
        self.name = name
        self.genauigkeit = genauigkeit
        self.gespeichert_am = gespeichert_am

    @classmethod
    def aus_wert(cls, daten):
        """Liest einen Checkpoint aus – auch alten – JSON-Daten."""
        def text(deutsch, englisch):
            wert = daten.get(deutsch, daten.get(englisch)) if isinstance(daten, dict) else None
            if isinstance(wert, str) and wert:
                return wert
            if wert is None:
                return ""
            return str(wert)

        kennung = text("kennung", "id")
        name = text("name", "kennung")
        genauigkeit = None
        genau_wert = daten.get("genauigkeit", daten.get("accuracy")) if isinstance(daten, dict) else None
        if isinstance(genau_wert, (int, float)) and not isinstance(genau_wert, bool):
            genauigkeit = float(genau_wert)

        if not name:
            name = kennung if kennung else "unbenannt"

        return cls(
            kennung=kennung,
            name=name,
            genauigkeit=genauigkeit,
            gespeichert_am=text("gespeichert_am", "saved_at"),
        )

    def als_wert(self):
        """Gibt den Checkpoint als JSON-Wert mit deutschen und alten
        englischen Schlüsseln zurück, wie die Weboberfläche sie liefert."""
        genauigkeit = self.genauigkeit if self.genauigkeit is not None else None
        return {
            "kennung": self.kennung,
            "id": self.kennung,
            "name": self.name,
            "genauigkeit": genauigkeit,
            "accuracy": genauigkeit,
            "gespeichert_am": self.gespeichert_am,
            "saved_at": self.gespeichert_am,
        }

    def genauigkeit_text(self):
        """Gibt die Genauigkeit als Text in Prozent zurück."""
        if self.genauigkeit is not None:
            return f"{self.genauigkeit * 100.0:.1f} %"
        return "-"


class CheckpointVerwaltung:
    """Verwaltet den Ordner mit den Checkpoint-Dateien."""

    def __init__(self, ordner=None):
        if ordner is None:
            ordner = os.path.join(datenordner(), "checkpoints")
        self.ordner = ordner

    @classmethod
    def standardpfad(cls):
        """Öffnet die Verwaltung für data/checkpoints/ des Projekts."""
        return cls(os.path.join(datenordner(), "checkpoints"))

    def _lese_checkpoint_aus_datei(self, datei):
        """Liest Kennung, Name und Zeitpunkt aus einem Dateinamen."""
        rumpf = datei[:-3]  # .pt entfernen
        if "_" in rumpf:
            kennung, rest = rumpf.split("_", 1)
            name = rest.replace("_", " ")
        else:
            kennung = rumpf
            name = ""
        try:
            mtime = os.path.getmtime(os.path.join(self.ordner, datei))
            gespeichert_am = aus_sekunden(int(mtime))
        except OSError:
            gespeichert_am = ""
        if not name:
            name = kennung
        return {
            "kennung": kennung,
            "name": name,
            "genauigkeit": None,
            "gespeichert_am": gespeichert_am,
        }

    def auflisten(self):
        """Liest die Checkpoint-Liste allein aus den Dateinamen.

        Die Zusatzdaten stecken in den Dateien selbst und lassen sich ohne
        PyTorch nicht lesen, der Name und der Zeitpunkt aber schon.
        """
        if not os.path.isdir(self.ordner):
            return []
        dateinamen = [
            f for f in os.listdir(self.ordner) if f.endswith(".pt")
        ]
        dateinamen.sort()
        return [self._lese_checkpoint_aus_datei(f) for f in dateinamen]

    def liste(self):
        """Alias für auflisten()."""
        return self.auflisten()

    def speichern(self, modell, name, zusatz=""):
        """Speichert einen Checkpoint und gibt die Kennung zurück."""
        kennung = secrets.token_hex(4)
        dateiname = f"{kennung}_{name.replace(' ', '_')}"
        if zusatz:
            dateiname += f"_{zusatz.replace(' ', '_')}"
        dateiname += ".pt"
        pfad = os.path.join(self.ordner, dateiname)
        stelle_ordner_bereit(pfad)
        with open(pfad, "wb") as f:
            f.write(b"")
        return kennung

    def laden(self, kennung):
        """Lädt einen Checkpoint anhand seiner Kennung.

        Gibt ein Tuple (dateipfad, checkpoint_dict) zurück, oder None.
        """
        if not kennung or not os.path.isdir(self.ordner):
            return None
        anfang = f"{kennung}_"
        for datei in os.listdir(self.ordner):
            if datei.startswith(anfang) and datei.endswith(".pt"):
                pfad = os.path.join(self.ordner, datei)
                checkpoint = self._lese_checkpoint_aus_datei(datei)
                return (pfad, checkpoint)
        return None

    def datei(self, kennung):
        """Gibt den Pfad zur Datei einer Kennung zurück, falls vorhanden."""
        if not kennung or not os.path.isdir(self.ordner):
            return None
        anfang = f"{kennung}_"
        treffer = []
        for datei in os.listdir(self.ordner):
            if datei.startswith(anfang) and datei.endswith(".pt"):
                treffer.append(os.path.join(self.ordner, datei))
        if treffer:
            return min(treffer)
        return None

    def loeschen(self, kennung):
        """Löscht alle Dateien mit der angegebenen Kennung.

        Gibt True zurück, wenn mindestens eine Datei gelöscht wurde.
        """
        if not kennung or not os.path.isdir(self.ordner):
            return False
        geloescht = False
        anfang = f"{kennung}_"
        for datei in os.listdir(self.ordner):
            if datei.startswith(anfang) and datei.endswith(".pt"):
                try:
                    os.remove(os.path.join(self.ordner, datei))
                    geloescht = True
                except OSError:
                    pass
        return geloescht

    def loesche(self, kennung):
        """Alias für loeschen()."""
        return self.loeschen(kennung)
