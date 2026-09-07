"""Sitzungen über ein unterschriebenes Kennwort-Plätzchen (Cookie).

Die Sitzung wird als JSON abgelegt, mit HMAC-SHA256 unterschrieben und im
Plätzchen ``kimi3_sitzung`` gespeichert. Ohne gültige Unterschrift gilt die
Sitzung als leer – der Inhalt lässt sich also nicht fälschen.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass

PLAETZCHEN = "kimi3_sitzung"
STANDARD_GEHEIMNIS = "kimi3-dev-geheimnis-bitte-aendern"


@dataclass
class Sitzung:
    """Inhalt einer Sitzung."""

    benutzer: str = ""
    ist_admin: bool = False

    def ist_angemeldet(self) -> bool:
        """Ist jemand mit Administratorrechten angemeldet?"""
        return bool(self.benutzer) and self.ist_admin


def geheimnis_aus_umgebung() -> str:
    """Liest das Geheimnis aus der Umgebungsvariablen ``SECRET_KEY``."""
    return os.environ.get("SECRET_KEY", STANDARD_GEHEIMNIS)


def _unterschrift(geheimnis: str, inhalt: str) -> str:
    """Berechnet die Unterschrift eines Textes."""
    rechner = hmac.new(geheimnis.encode("utf-8"), inhalt.encode("utf-8"), hashlib.sha256)
    return rechner.hexdigest()


def verpacke(geheimnis: str, sitzung: Sitzung) -> str:
    """Packt eine Sitzung in den Wert des Plätzchens."""
    roh = json.dumps(sitzung.__dict__, ensure_ascii=False, separators=(",", ":"))
    inhalt = roh.encode("utf-8").hex()
    zeichen = _unterschrift(geheimnis, inhalt)
    return f"{inhalt}.{zeichen}"


def entpacke(geheimnis: str, wert: str) -> Sitzung:
    """Liest eine Sitzung aus dem Wert des Plätzchens.

    Fehlt die Unterschrift oder passt sie nicht, ist die Sitzung leer.
    """
    if "." not in wert:
        return Sitzung()
    inhalt, zeichen = wert.rsplit(".", 1)
    erwartet = _unterschrift(geheimnis, inhalt)
    if not hmac.compare_digest(erwartet, zeichen):
        return Sitzung()
    try:
        roh = bytes.fromhex(inhalt).decode("utf-8")
        daten = json.loads(roh)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return Sitzung()
    return Sitzung(
        benutzer=daten.get("benutzer", ""),
        ist_admin=daten.get("ist_admin", False),
    )


def aus_kopfzeile(geheimnis: str, kopfzeile: str | None) -> Sitzung:
    """Sucht die Sitzung im Kopfzeilenwert ``Cookie``."""
    if not kopfzeile:
        return Sitzung()
    for teil in kopfzeile.split(";"):
        teil = teil.strip()
        if teil.startswith(f"{PLAETZCHEN}="):
            wert = teil[len(PLAETZCHEN) + 1:]
            return entpacke(geheimnis, wert)
    return Sitzung()


def setz_kopfzeile(geheimnis: str, sitzung: Sitzung) -> str:
    """Erzeugt den Wert für die Kopfzeile ``Set-Cookie``."""
    return (
        f"{PLAETZCHEN}={verpacke(geheimnis, sitzung)}; "
        f"Path=/; HttpOnly; SameSite=Lax"
    )


def loesch_kopfzeile() -> str:
    """Erzeugt den Wert für die Kopfzeile ``Set-Cookie``, der die Sitzung löscht."""
    return f"{PLAETZCHEN}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
