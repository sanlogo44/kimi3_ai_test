"""Protokollierung mit farbiger Konsolenausgabe und optionaler Datei.

Die Ausgabe entspricht der bisherigen Python-Fassung (logger.py):
[HH:MM:SS] STUFE Nachricht auf der Konsole und
[JJJJ-MM-TT HH:MM:SS] [STUFE] Nachricht in der Datei.
"""

import os
from enum import IntEnum

from .konfiguration import Konfiguration
from .pfade import stelle_ordner_bereit
from .zeit import jetzt_lesbar


class Stufe(IntEnum):
    """Die fünf Protokollstufen."""

    FEHLERSUCHE = 10
    HINWEIS = 20
    WARNUNG = 30
    FEHLER = 40
    KRITISCH = 50


_STUFEN_NAMEN = {
    Stufe.FEHLERSUCHE: "DEBUG",
    Stufe.HINWEIS: "INFO",
    Stufe.WARNUNG: "WARNING",
    Stufe.FEHLER: "ERROR",
    Stufe.KRITISCH: "CRITICAL",
}

_STUFEN_FARBEN = {
    Stufe.FEHLERSUCHE: "\x1b[36m",
    Stufe.HINWEIS: "\x1b[32m",
    Stufe.WARNUNG: "\x1b[33m",
    Stufe.FEHLER: "\x1b[31m",
    Stufe.KRITISCH: "\x1b[35m",
}


def stufe_name(stufe):
    """Gibt den Namen der Stufe zurück, wie er im Protokoll erscheint."""
    return _STUFEN_NAMEN.get(stufe, "INFO")


def stufe_farbe(stufe):
    """Gibt den ANSI-Farbcode der Stufe zurück."""
    return _STUFEN_FARBEN.get(stufe, "")


def stufe_aus_text(text):
    """Liest eine Stufe aus einem Text; unbekannte Angaben ergeben Hinweis."""
    text = text.strip().upper()
    mapping = {
        "DEBUG": Stufe.FEHLERSUCHE,
        "FEHLERSUCHE": Stufe.FEHLERSUCHE,
        "INFO": Stufe.HINWEIS,
        "HINWEIS": Stufe.HINWEIS,
        "WARNING": Stufe.WARNUNG,
        "WARN": Stufe.WARNUNG,
        "WARNUNG": Stufe.WARNUNG,
        "ERROR": Stufe.FEHLER,
        "FEHLER": Stufe.FEHLER,
        "CRITICAL": Stufe.KRITISCH,
        "KRITISCH": Stufe.KRITISCH,
    }
    return mapping.get(text, Stufe.HINWEIS)


class Protokoll:
    """Schreibt Meldungen auf die Konsole und optional in eine Datei."""

    def __init__(self, stufe, farbig, datei=None):
        if isinstance(stufe, str):
            stufe = stufe_aus_text(stufe)
        self._stufe = stufe
        self._farbig = farbig
        self._datei = datei
        if datei:
            stelle_ordner_bereit(datei)

    @classmethod
    def aus_konfiguration(cls, konfiguration):
        """Erzeugt ein Protokoll aus dem Abschnitt logging der Konfiguration."""
        if isinstance(konfiguration, dict):
            log_cfg = konfiguration.get("logging", {})
            datei_wert = log_cfg.get("log_file")
            stufe = log_cfg.get("level", "INFO")
            farbig = log_cfg.get("colored", True)
        else:
            datei_wert = konfiguration.hole(["logging", "log_file"])
            stufe = konfiguration.text(["logging", "level"], "INFO")
            farbig = konfiguration.wahrheitswert(["logging", "colored"], True)
        datei = None
        if isinstance(datei_wert, str) and datei_wert:
            datei = datei_wert
        return cls(stufe, farbig, datei)

    def setze_stufe(self, stufe):
        """Setzt die kleinste Stufe, die noch ausgegeben wird."""
        if isinstance(stufe, str):
            stufe = stufe_aus_text(stufe)
        self._stufe = stufe

    def stufe(self):
        """Gibt die aktuell eingestellte Stufe zurück."""
        return self._stufe

    def dateipfad(self):
        """Gibt den Pfad der Protokolldatei zurück, falls eine gesetzt ist."""
        return self._datei

    def schreibe(self, stufe, nachricht):
        """Schreibt eine Meldung, wenn ihre Stufe hoch genug ist."""
        if isinstance(stufe, str):
            stufe = stufe_aus_text(stufe)
        if stufe < self._stufe:
            return
        uhrzeit = jetzt_lesbar()
        if self._farbig:
            konsole = (
                f"[{uhrzeit[11:]}] {stufe_farbe(stufe)}"
                f"\x1b[1m{stufe_name(stufe)}\x1b[0m {nachricht}"
            )
        else:
            konsole = f"[{uhrzeit[11:]}] {stufe_name(stufe)} {nachricht}"
        print(konsole)
        if self._datei:
            zeile = f"[{uhrzeit}] [{stufe_name(stufe)}] {nachricht}\n"
            try:
                with open(self._datei, "a", encoding="utf-8") as f:
                    f.write(zeile)
            except OSError:
                pass

    def fehlersuche(self, nachricht):
        """Schreibt eine Meldung der Stufe DEBUG."""
        self.schreibe(Stufe.FEHLERSUCHE, nachricht)

    def hinweis(self, nachricht):
        """Schreibt eine Meldung der Stufe INFO."""
        self.schreibe(Stufe.HINWEIS, nachricht)

    def warnung(self, nachricht):
        """Schreibt eine Meldung der Stufe WARNING."""
        self.schreibe(Stufe.WARNUNG, nachricht)

    def fehler(self, nachricht):
        """Schreibt eine Meldung der Stufe ERROR."""
        self.schreibe(Stufe.FEHLER, nachricht)

    def kritisch(self, nachricht):
        """Schreibt eine Meldung der Stufe CRITICAL."""
        self.schreibe(Stufe.KRITISCH, nachricht)


# Gemeinsam genutztes Protokoll des Programms.
_PROTOKOLL = None


def hole_protokoll():
    """Gibt das gemeinsame Protokoll zurück und legt es beim ersten Aufruf an."""
    global _PROTOKOLL
    if _PROTOKOLL is None:
        _PROTOKOLL = Protokoll.aus_konfiguration(Konfiguration.lade_standardpfad())
    return _PROTOKOLL


def setze_protokoll(protokoll):
    """Setzt das gemeinsame Protokoll, solange es noch nicht angelegt wurde."""
    global _PROTOKOLL
    if _PROTOKOLL is not None:
        return False
    _PROTOKOLL = protokoll
    return True


def richte_protokoll_ein(stufe, farbig, datei):
    """Richtet Protokollierung ein."""
    global _PROTOKOLL
    _PROTOKOLL = Protokoll(stufe, farbig, datei)


def setze_protokollstufe(stufe):
    """Setzt Protokollstufe."""
    prot = hole_protokoll()
    prot.setze_stufe(stufe)


def protokolliere(stufe, meldung):
    """Gibt eine Protokollmeldung aus."""
    prot = hole_protokoll()
    prot.schreibe(stufe, meldung)
