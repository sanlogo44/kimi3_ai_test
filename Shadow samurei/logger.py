"""Protokoll-Modul für die Anwendung.

Die Ausgabe erledigt der Rust-Kern (``kimi3_kern.richte_protokoll_ein`` und
``kimi3_kern.protokolliere``): farbige Konsolenausgabe im Format
``[HH:MM:SS] STUFE Meldung`` und optional eine Protokolldatei im Format
``[JJJJ-MM-TT HH:MM:SS] [STUFE] Meldung``. Dieses Modul ist nur die dünne
Hülle darüber und behält die bisherige Schnittstelle (:class:`Logger`,
:func:`get_logger`).
"""
from __future__ import annotations

from typing import Optional

from kern_modul import kern

#: Rangfolge der Protokollstufen, damit :meth:`Logger.set_level` wirkt.
STUFEN_RANG = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


def _stufenname(stufe) -> str:
    """Gibt einen gültigen Stufennamen zurück; unbekannte Angaben ergeben INFO."""
    name = str(stufe or "INFO").strip().upper()
    return name if name in STUFEN_RANG else "INFO"


class Logger:
    """Einzelinstanz für die Protokollausgabe des Kerns."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name="KI_Assistent", level="INFO", colored=True, log_file=None):
        if self._initialized:
            return
        self._initialized = True
        self.name = name
        self._stufe = _stufenname(level)
        self.datei: Optional[str] = log_file or None
        # Nur der erste Aufruf im Prozess richtet das Protokoll ein; der Kern
        # legt den Ordner der Protokolldatei bei Bedarf selbst an.
        kern.richte_protokoll_ein(self._stufe, bool(colored), self.datei)
        # Ist das Protokoll schon eingerichtet, gilt trotzdem die hier
        # gewünschte Stufe.
        kern.setze_protokollstufe(self._stufe)

    def _schreibe(self, stufe: str, meldung) -> None:
        """Gibt eine Meldung aus, wenn ihre Stufe hoch genug ist."""
        if STUFEN_RANG[stufe] >= STUFEN_RANG[self._stufe]:
            kern.protokolliere(stufe, str(meldung))

    def debug(self, msg): self._schreibe("DEBUG", msg)
    def info(self, msg): self._schreibe("INFO", msg)
    def warning(self, msg): self._schreibe("WARNING", msg)
    def error(self, msg): self._schreibe("ERROR", msg)
    def critical(self, msg): self._schreibe("CRITICAL", msg)

    def set_level(self, level):
        """Setzt die kleinste Stufe, die noch ausgegeben wird."""
        self._stufe = _stufenname(level)
        kern.setze_protokollstufe(self._stufe)

    @property
    def stufe(self) -> str:
        """Gibt die aktuell eingestellte Stufe zurück."""
        return self._stufe


_log = None
def get_logger(cfg=None):
    """Gibt die globale Protokoll-Instanz zurück (erstellt sie bei Bedarf)."""
    global _log
    if _log is None:
        if cfg is None:
            from config_loader import load_config
            cfg = load_config()
        lc = cfg.get("logging", {})
        _log = Logger(level=lc.get("level", "INFO"), colored=lc.get("colored", True), log_file=lc.get("log_file"))
    return _log
