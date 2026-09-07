"""Benutzerkonten in data/users.json.

Entspricht der bisherigen Python-Klasse AuthManager: dasselbe
Dateiformat, dieselben Regeln (mindestens vier Zeichen Passwort, der
letzte Administrator bleibt erhalten) und dieselben deutschen Texte.
"""

import json
import os

from .konfiguration import Konfiguration
from .passwort import erzeuge_hash, pruefe
from .pfade import datendatei, schreibe_atomar
from .zeit import jetzt_iso

#: Kleinste erlaubte Passwortlänge.
MINDESTLAENGE_PASSWORT = 4


def rollenname(rolle):
    """Gibt den Anzeigenamen einer Rolle zurück."""
    if rolle == "admin":
        return "Administrator"
    elif rolle == "user":
        return "Benutzer"
    return rolle


class Konto:
    """Ein einzelnes Benutzerkonto."""

    def __init__(
        self,
        benutzername="",
        passwort_hash="",
        rolle="user",
        passwortwechsel_faellig=False,
        erstellt_am="",
        letzte_anmeldung="",
    ):
        self.benutzername = benutzername
        self.passwort_hash = passwort_hash
        self.rolle = rolle
        self.passwortwechsel_faellig = passwortwechsel_faellig
        self.erstellt_am = erstellt_am
        self.letzte_anmeldung = letzte_anmeldung

    @classmethod
    def neu(cls, benutzername, passwort_klartext, rolle, wechsel):
        """Erzeugt ein Konto mit frischem Passwort-Hash."""
        return cls(
            benutzername=benutzername,
            passwort_hash=erzeuge_hash(passwort_klartext),
            rolle=rolle,
            passwortwechsel_faellig=wechsel,
            erstellt_am=jetzt_iso(),
            letzte_anmeldung="",
        )

    @classmethod
    def aus_wert(cls, benutzername, daten):
        """Liest ein Konto aus JSON-Daten; alte englische Schlüssel gelten weiter."""
        def hole(deutsch, englisch):
            if not isinstance(daten, dict):
                return None
            if deutsch in daten:
                return daten[deutsch]
            if englisch in daten:
                return daten[englisch]
            return None

        def text(deutsch, englisch):
            wert = hole(deutsch, englisch)
            if isinstance(wert, str):
                return wert
            if wert is None:
                return ""
            return str(wert)

        def wahrheit(deutsch, englisch):
            wert = hole(deutsch, englisch)
            if isinstance(wert, bool):
                return wert
            if isinstance(wert, (int, float)) and not isinstance(wert, bool):
                return wert != 0.0
            if isinstance(wert, str):
                return bool(wert) and wert != "false" and wert != "0"
            return False

        rolle = text("rolle", "role")
        return cls(
            benutzername=benutzername,
            passwort_hash=text("passwort_hash", "password_hash"),
            rolle=rolle if rolle else "user",
            passwortwechsel_faellig=wahrheit("passwortwechsel_faellig", "force_password_change"),
            erstellt_am=text("erstellt_am", "created_at"),
            letzte_anmeldung=text("letzte_anmeldung", "last_login"),
        )

    def als_wert(self):
        """Gibt das Konto als JSON-Wert zurück (ohne den Benutzernamen)."""
        return {
            "passwort_hash": self.passwort_hash,
            "rolle": self.rolle,
            "passwortwechsel_faellig": self.passwortwechsel_faellig,
            "erstellt_am": self.erstellt_am,
            "letzte_anmeldung": self.letzte_anmeldung,
        }

    def als_dict(self):
        """Gibt das Konto als vollständiges Wörterbuch zurück."""
        return {
            "benutzername": self.benutzername,
            "passwort_hash": self.passwort_hash,
            "rolle": self.rolle,
            "passwortwechsel_faellig": self.passwortwechsel_faellig,
            "erstellt_am": self.erstellt_am,
            "letzte_anmeldung": self.letzte_anmeldung,
        }

    def ist_administrator(self):
        """Ist dieses Konto ein Administrator?"""
        return self.rolle == "admin"

    def rollenname(self):
        """Gibt den Anzeigenamen der Rolle zurück."""
        return rollenname(self.rolle)


class Kontenverwaltung:
    """Verwaltet alle Benutzerkonten."""

    def __init__(self, pfad=None, standardbenutzer="Admin",
                 standardpasswort="1234", wechsel=True):
        if pfad is None:
            pfad = datendatei("users.json")
        self.pfad = pfad
        self.standardbenutzer = standardbenutzer
        self.standardpasswort = standardpasswort
        self.wechsel_erzwingen = wechsel

    @classmethod
    def aus_konfiguration(cls, konfiguration):
        """Öffnet die Verwaltung mit Werten aus der Konfiguration."""
        pfad = datendatei("users.json")
        if isinstance(konfiguration, dict):
            auth = konfiguration.get("auth", {})
            benutzer = auth.get("default_user", "Admin")
            passwort = auth.get("default_password", "1234")
            wechsel = auth.get("force_password_change", True)
        else:
            benutzer = konfiguration.text(["auth", "default_user"], "Admin")
            passwort = konfiguration.text(["auth", "default_password"], "1234")
            wechsel = konfiguration.wahrheitswert(["auth", "force_password_change"], True)
        return cls(pfad, benutzer, passwort, wechsel)

    @classmethod
    def standardpfad(cls):
        """Öffnet die Verwaltung mit der Konfiguration des Projekts."""
        return cls.aus_konfiguration(Konfiguration.lade_standardpfad())

    @classmethod
    def rollenname(cls, rolle):
        """Gibt den Anzeigenamen einer Rolle zurück."""
        return rollenname(rolle)

    def lade_benutzer(self):
        """Liest alle Konten; fehlt die Datei, wird das Standardkonto angelegt."""
        try:
            with open(self.pfad, "r", encoding="utf-8") as f:
                inhalt = f.read()
            daten = json.loads(inhalt)
        except (FileNotFoundError, json.JSONDecodeError):
            daten = {}

        if isinstance(daten, dict) and daten:
            return [
                Konto.aus_wert(name, wert).als_dict()
                for name, wert in daten.items()
            ]

        standard = [
            Konto.neu(
                self.standardbenutzer,
                self.standardpasswort,
                "admin",
                self.wechsel_erzwingen,
            ).als_dict()
        ]
        self.speichere(standard)
        return standard

    def speichere(self, konten):
        """Schreibt alle Konten in die Datei."""
        karte = {}
        for konto in konten:
            if isinstance(konto, dict):
                name = konto["benutzername"]
                karte[name] = {k: v for k, v in konto.items() if k != "benutzername"}
            else:
                karte[konto.benutzername] = konto.als_wert()
        text = json.dumps(karte, indent=2, ensure_ascii=False)
        schreibe_atomar(self.pfad, text)

    def hole(self, benutzername):
        """Gibt ein einzelnes Konto zurück."""
        for konto in self.lade_benutzer():
            if konto["benutzername"] == benutzername:
                return konto
        return None

    def liste(self):
        """Gibt alle Benutzernamen zurück."""
        return [k["benutzername"] for k in self.lade_benutzer()]

    def anzahl(self):
        """Gibt die Anzahl der Konten zurück."""
        return len(self.lade_benutzer())

    def ist_administrator(self, benutzername):
        """Ist das Konto ein Administrator?"""
        konto = self.hole(benutzername)
        return konto is not None and konto.get("rolle") == "admin"

    def passwortwechsel_faellig(self, benutzername):
        """Ist für dieses Konto ein Passwortwechsel fällig?"""
        konto = self.hole(benutzername)
        return konto is not None and konto.get("passwortwechsel_faellig", False)

    @staticmethod
    def _anzahl_administratoren(konten):
        """Anzahl der Administratorkonten."""
        return sum(1 for k in konten if k.get("rolle") == "admin")

    def pruefe_anmeldung(self, benutzername, passwort_klartext):
        """Prüft Benutzername und Passwort und merkt die Anmeldung."""
        konten = self.lade_benutzer()
        stelle = None
        for i, k in enumerate(konten):
            if k["benutzername"] == benutzername:
                stelle = i
                break
        if stelle is None:
            return None
        if not pruefe(konten[stelle]["passwort_hash"], passwort_klartext):
            return None
        konten[stelle]["letzte_anmeldung"] = jetzt_iso()
        konto = konten[stelle].copy()
        self.speichere(konten)
        return konto

    def fuege_benutzer_hinzu(self, name, passwort, rolle, wechsel_erzwingen=False):
        """Legt ein neues Konto an.

        Fehler: Name schon vergeben, Name leer oder Passwort zu kurz.
        """
        name = name.strip()
        if not name:
            raise ValueError("Bitte einen Benutzernamen eingeben.")
        if len(passwort) < MINDESTLAENGE_PASSWORT:
            raise ValueError(
                f"Das Passwort muss mindestens {MINDESTLAENGE_PASSWORT} Zeichen haben."
            )
        konten = self.lade_benutzer()
        if any(k["benutzername"] == name for k in konten):
            raise ValueError(f"Der Benutzername „{name}“ ist schon vergeben.")
        konto = Konto.neu(name, passwort, rolle, wechsel_erzwingen).als_dict()
        konten.append(konto)
        self.speichere(konten)
        return konto

    def loesche_benutzer(self, benutzername):
        """Löscht ein Konto; der letzte Administrator bleibt erhalten."""
        konten = self.lade_benutzer()
        stelle = None
        for i, k in enumerate(konten):
            if k["benutzername"] == benutzername:
                stelle = i
                break
        if stelle is None:
            raise ValueError(f"Das Konto „{benutzername}“ gibt es nicht.")
        if (
            konten[stelle].get("rolle") == "admin"
            and self._anzahl_administratoren(konten) <= 1
        ):
            raise ValueError("Der letzte Administrator kann nicht gelöscht werden.")
        konten.pop(stelle)
        self.speichere(konten)

    def aendere_passwort(self, benutzername, neues_passwort, wechsel_erzwingen=False):
        """Ändert das Passwort eines Kontos."""
        if len(neues_passwort) < MINDESTLAENGE_PASSWORT:
            raise ValueError(
                f"Das Passwort muss mindestens {MINDESTLAENGE_PASSWORT} Zeichen haben."
            )
        konten = self.lade_benutzer()
        stelle = None
        for i, k in enumerate(konten):
            if k["benutzername"] == benutzername:
                stelle = i
                break
        if stelle is None:
            raise ValueError(f"Das Konto „{benutzername}“ gibt es nicht.")
        konten[stelle]["passwort_hash"] = erzeuge_hash(neues_passwort)
        konten[stelle]["passwortwechsel_faellig"] = wechsel_erzwingen
        self.speichere(konten)

    def aendere_rolle(self, benutzername, rolle):
        """Ändert die Rolle eines Kontos; der letzte Administrator bleibt es."""
        konten = self.lade_benutzer()
        stelle = None
        for i, k in enumerate(konten):
            if k["benutzername"] == benutzername:
                stelle = i
                break
        if stelle is None:
            raise ValueError(f"Das Konto „{benutzername}“ gibt es nicht.")
        if (
            konten[stelle].get("rolle") == "admin"
            and rolle != "admin"
            and self._anzahl_administratoren(konten) <= 1
        ):
            raise ValueError("Der letzte Administrator behält seine Rolle.")
        konten[stelle]["rolle"] = rolle
        self.speichere(konten)

    def aendere_zugangsdaten(self, alter_name, neuer_name, neues_passwort):
        """Ändert Benutzernamen und Passwort in einem Schritt.

        Wird nach der ersten Anmeldung mit dem Standardkonto genutzt.
        """
        name = neuer_name.strip()
        if not name:
            raise ValueError("Bitte einen Benutzernamen eingeben.")
        if len(neues_passwort) < MINDESTLAENGE_PASSWORT:
            raise ValueError(
                f"Das Passwort muss mindestens {MINDESTLAENGE_PASSWORT} Zeichen haben."
            )
        konten = self.lade_benutzer()
        stelle = None
        for i, k in enumerate(konten):
            if k["benutzername"] == alter_name:
                stelle = i
                break
        if stelle is None:
            raise ValueError(f"Das Konto „{alter_name}“ gibt es nicht.")
        if name != alter_name and any(k["benutzername"] == name for k in konten):
            raise ValueError(f"Der Benutzername „{name}“ ist schon vergeben.")
        konten[stelle]["benutzername"] = name
        konten[stelle]["passwort_hash"] = erzeuge_hash(neues_passwort)
        konten[stelle]["passwortwechsel_faellig"] = False
        konto = konten[stelle].copy()
        self.speichere(konten)
        return konto

    def markiere_erstanmeldung_erledigt(self, benutzername):
        """Merkt, dass die Erstanmeldung erledigt ist."""
        konten = self.lade_benutzer()
        stelle = None
        for i, k in enumerate(konten):
            if k["benutzername"] == benutzername:
                stelle = i
                break
        if stelle is None:
            raise ValueError(f"Das Konto „{benutzername}“ gibt es nicht.")
        konten[stelle]["passwortwechsel_faellig"] = False
        self.speichere(konten)
