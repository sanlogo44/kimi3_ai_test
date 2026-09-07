"""Zentrale Theme-Verwaltung für Hell-/Dunkel-Modus.

Alle Farben werden als ``(hell, dunkel)``-Tupel definiert. CustomTkinter
wählt daraus automatisch den passenden Wert, sobald das Erscheinungsbild
umgeschaltet wird. Für Matplotlib-Diagramme, die keine Tupel verstehen,
liefert :meth:`ThemeVerwaltung.diagramm_farben` die aktuell gültigen
Einzelfarben, und registrierte Beobachter werden beim Umschalten
benachrichtigt, damit sie sich neu zeichnen können.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import customtkinter as ctk

from settings_store import hole_einstellungen

# ---------------------------------------------------------------- Farbpalette
# Warme, an Claude angelehnte Palette: (hell, dunkel)
FARBEN: Dict[str, Tuple[str, str]] = {
    "fenster":          ("#faf9f5", "#1f1e1d"),
    "flaeche":          ("#ffffff", "#262624"),
    "flaeche_erhoeht":  ("#f0eee6", "#30302e"),
    "seitenleiste":     ("#f0eee6", "#1a1a19"),
    "rahmen":           ("#e5e2d9", "#3a3a37"),
    "text":             ("#141413", "#f5f4ef"),
    "text_gedaempft":   ("#6b6a63", "#a3a19a"),
    "akzent":           ("#c96442", "#c96442"),
    "akzent_hover":     ("#b05637", "#d97757"),
    "blase_benutzer":   ("#eeece4", "#333331"),
    "blase_assistent":  ("#ffffff", "#262624"),
    "code_hintergrund": ("#f5f3ec", "#141413"),
    "erfolg":           ("#15803d", "#4ade80"),
    "warnung":          ("#b45309", "#fbbf24"),
    "fehler":           ("#b91c1c", "#f87171"),
    "info":             ("#1d4ed8", "#60a5fa"),
}

# Schriftfamilien mit Rückfallebene für Linux/Windows/macOS.
SCHRIFT_TEXT = "Helvetica"
SCHRIFT_MONO = "Courier"

# Übersetzung der Modus-Namen in die CustomTkinter-Bezeichner.
MODI: Dict[str, str] = {"System": "System", "Hell": "Light", "Dunkel": "Dark"}
MODI_UMGEKEHRT: Dict[str, str] = {v: k for k, v in MODI.items()}


def farbe(name: str) -> Tuple[str, str]:
    """Gibt das Farbtupel zu einem Palettennamen zurück."""
    return FARBEN.get(name, FARBEN["text"])


class ThemeVerwaltung:
    """Verwaltet das Erscheinungsbild der gesamten Anwendung."""

    def __init__(self, farbschema: str | None = None):
        self._einstellungen = hole_einstellungen()
        self._beobachter: List[Callable[[str], None]] = []
        schema = farbschema or self._einstellungen.hole("farbschema", "blue")
        try:
            ctk.set_default_color_theme(schema)
        except Exception:
            ctk.set_default_color_theme("blue")
        self._modus = self._einstellungen.hole("erscheinungsbild", "System")
        if self._modus not in MODI:
            self._modus = "System"
        ctk.set_appearance_mode(MODI[self._modus])

    # ----------------------------------------------------------------- Modus
    @property
    def modus(self) -> str:
        """Aktueller Modus als deutscher Name ("System", "Hell", "Dunkel")."""
        return self._modus

    def ist_dunkel(self) -> bool:
        """Prüft, ob aktuell dunkle Farben dargestellt werden."""
        return ctk.get_appearance_mode().lower() == "dark"

    def index(self) -> int:
        """Index des aktuellen Modus (0 = System, 1 = Hell, 2 = Dunkel)."""
        return list(MODI).index(self._modus)

    def setze_modus(self, modus: str) -> None:
        """Setzt das Erscheinungsbild und benachrichtigt alle Beobachter."""
        if modus not in MODI:
            modus = "System"
        self._modus = modus
        ctk.set_appearance_mode(MODI[modus])
        self._einstellungen.setze("erscheinungsbild", modus)
        self._benachrichtige()

    def umschalten(self) -> str:
        """Schaltet zyklisch zwischen System, Hell und Dunkel um."""
        reihenfolge = list(MODI)
        naechster = reihenfolge[(reihenfolge.index(self._modus) + 1) % len(reihenfolge)]
        self.setze_modus(naechster)
        return naechster

    def setze_farbschema(self, schema: str) -> None:
        """Wechselt das Farbschema (wirkt erst nach einem Neustart voll)."""
        try:
            ctk.set_default_color_theme(schema)
            self._einstellungen.setze("farbschema", schema)
        except Exception:
            pass

    # ------------------------------------------------------------ Beobachter
    def registriere_beobachter(self, rueckruf: Callable[[str], None]) -> None:
        """Registriert eine Funktion, die bei Theme-Wechsel aufgerufen wird."""
        if rueckruf not in self._beobachter:
            self._beobachter.append(rueckruf)

    def entferne_beobachter(self, rueckruf: Callable[[str], None]) -> None:
        """Entfernt einen registrierten Beobachter."""
        if rueckruf in self._beobachter:
            self._beobachter.remove(rueckruf)

    def _benachrichtige(self) -> None:
        """Ruft alle Beobachter auf; Fehler einzelner Beobachter werden ignoriert."""
        for rueckruf in list(self._beobachter):
            try:
                rueckruf(self._modus)
            except Exception:
                self._beobachter.remove(rueckruf)

    # -------------------------------------------------------------- Diagramme
    def einzelfarbe(self, name: str) -> str:
        """Gibt die aktuell gültige Einzelfarbe eines Palettennamens zurück."""
        hell, dunkel = farbe(name)
        return dunkel if self.ist_dunkel() else hell

    def diagramm_farben(self) -> Dict[str, str]:
        """Liefert die Farbwerte für Matplotlib-Diagramme."""
        dunkel = self.ist_dunkel()
        return {
            "hintergrund": self.einzelfarbe("flaeche"),
            "text": self.einzelfarbe("text"),
            "gitter": "#4a4a46" if dunkel else "#d6d3c9",
            "rahmen": self.einzelfarbe("rahmen"),
            "reihe1": "#d97757" if dunkel else "#c96442",
            "reihe2": "#60a5fa" if dunkel else "#2563eb",
            "reihe3": "#4ade80" if dunkel else "#15803d",
            "reihe4": "#fbbf24" if dunkel else "#b45309",
            "reihe5": "#c084fc" if dunkel else "#7c3aed",
        }

    def reihenfarben(self) -> List[str]:
        """Gibt die Farbreihenfolge für mehrere Datenreihen zurück."""
        farben = self.diagramm_farben()
        return [farben[f"reihe{i}"] for i in range(1, 6)]


_theme: ThemeVerwaltung | None = None


def hole_theme() -> ThemeVerwaltung:
    """Gibt die global genutzte Theme-Verwaltung zurück."""
    global _theme
    if _theme is None:
        _theme = ThemeVerwaltung()
    return _theme
