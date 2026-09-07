"""Wiederverwendbare Oberflächen-Bausteine im Claude-Stil."""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from ui.theme import FARBEN, MODI, SCHRIFT_TEXT, ThemeVerwaltung


class Karte(ctk.CTkFrame):
    """Abgerundete Inhaltskarte mit dezentem Rahmen."""

    def __init__(self, master, titel: str = "", **kwargs):
        kwargs.setdefault("corner_radius", 14)
        kwargs.setdefault("fg_color", FARBEN["flaeche"])
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", FARBEN["rahmen"])
        super().__init__(master, **kwargs)
        self.titel_label: Optional[ctk.CTkLabel] = None
        if titel:
            self.titel_label = ctk.CTkLabel(
                self,
                text=titel,
                font=(SCHRIFT_TEXT, 15, "bold"),
                text_color=FARBEN["text"],
                anchor="w",
            )
            self.titel_label.pack(fill="x", padx=16, pady=(14, 6))


class ThemeSchalter(ctk.CTkFrame):
    """Segmentierter Schalter für System-, Hell- und Dunkel-Modus."""

    SYMBOLE = {"System": "🖥 System", "Hell": "☀ Hell", "Dunkel": "🌙 Dunkel"}

    def __init__(self, master, theme: ThemeVerwaltung, kompakt: bool = False, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._theme = theme

        werte = [self.SYMBOLE[m] for m in MODI]
        self._schalter = ctk.CTkSegmentedButton(
            self,
            values=werte,
            command=self._auf_auswahl,
            font=(SCHRIFT_TEXT, 11 if kompakt else 12),
            corner_radius=9,
            selected_color=FARBEN["akzent"],
            selected_hover_color=FARBEN["akzent_hover"],
            unselected_color=FARBEN["flaeche_erhoeht"],
            unselected_hover_color=FARBEN["rahmen"],
            text_color=FARBEN["text"],
            height=30 if kompakt else 34,
        )
        self._schalter.set(self.SYMBOLE[theme.modus])
        self._schalter.pack(fill="x")
        theme.registriere_beobachter(self._auf_theme_wechsel)

    def _auf_auswahl(self, wert: str) -> None:
        """Setzt den vom Benutzer gewählten Modus."""
        for modus, beschriftung in self.SYMBOLE.items():
            if beschriftung == wert:
                self._theme.setze_modus(modus)
                return

    def _auf_theme_wechsel(self, modus: str) -> None:
        """Hält den Schalter mit dem globalen Modus synchron."""
        try:
            self._schalter.set(self.SYMBOLE.get(modus, self.SYMBOLE["System"]))
        except Exception:
            pass


class ThemeKnopf(ctk.CTkButton):
    """Kompakter Knopf, der zyklisch durch die drei Theme-Modi schaltet."""

    SYMBOLE = {"System": "🖥", "Hell": "☀", "Dunkel": "🌙"}

    def __init__(self, master, theme: ThemeVerwaltung, **kwargs):
        self._theme = theme
        kwargs.setdefault("width", 42)
        kwargs.setdefault("height", 34)
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("fg_color", FARBEN["flaeche_erhoeht"])
        kwargs.setdefault("hover_color", FARBEN["rahmen"])
        kwargs.setdefault("text_color", FARBEN["text"])
        kwargs.setdefault("font", (SCHRIFT_TEXT, 15))
        super().__init__(master, text=self.SYMBOLE[theme.modus], command=self._umschalten, **kwargs)
        theme.registriere_beobachter(self._auf_theme_wechsel)

    def _umschalten(self) -> None:
        """Schaltet auf den nächsten Modus weiter."""
        self._theme.umschalten()

    def _auf_theme_wechsel(self, modus: str) -> None:
        """Aktualisiert das Symbol nach einem Theme-Wechsel."""
        try:
            self.configure(text=self.SYMBOLE.get(modus, "🖥"))
        except Exception:
            pass


class Hinweis(ctk.CTkLabel):
    """Einzeiliger Status- oder Fehlerhinweis mit Farbcodierung."""

    STUFEN = {
        "info": "info",
        "erfolg": "erfolg",
        "warnung": "warnung",
        "fehler": "fehler",
        "neutral": "text_gedaempft",
    }

    def __init__(self, master, **kwargs):
        kwargs.setdefault("text", "")
        kwargs.setdefault("font", (SCHRIFT_TEXT, 12))
        kwargs.setdefault("anchor", "w")
        kwargs.setdefault("justify", "left")
        kwargs.setdefault("text_color", FARBEN["text_gedaempft"])
        super().__init__(master, **kwargs)

    def zeige(self, text: str, stufe: str = "info") -> None:
        """Zeigt eine Meldung in der passenden Farbe an."""
        self.configure(text=text, text_color=FARBEN[self.STUFEN.get(stufe, "info")])

    def leeren(self) -> None:
        """Entfernt die aktuelle Meldung."""
        self.configure(text="")


def akzent_knopf(master, text: str, befehl: Callable[[], None], **kwargs) -> ctk.CTkButton:
    """Erzeugt einen Knopf in Akzentfarbe."""
    kwargs.setdefault("corner_radius", 10)
    kwargs.setdefault("height", 36)
    kwargs.setdefault("font", (SCHRIFT_TEXT, 13, "bold"))
    kwargs.setdefault("fg_color", FARBEN["akzent"])
    kwargs.setdefault("hover_color", FARBEN["akzent_hover"])
    kwargs.setdefault("text_color", "#ffffff")
    return ctk.CTkButton(master, text=text, command=befehl, **kwargs)


def neben_knopf(master, text: str, befehl: Callable[[], None], **kwargs) -> ctk.CTkButton:
    """Erzeugt einen zurückhaltenden Sekundär-Knopf."""
    kwargs.setdefault("corner_radius", 10)
    kwargs.setdefault("height", 34)
    kwargs.setdefault("font", (SCHRIFT_TEXT, 12))
    kwargs.setdefault("fg_color", FARBEN["flaeche_erhoeht"])
    kwargs.setdefault("hover_color", FARBEN["rahmen"])
    kwargs.setdefault("text_color", FARBEN["text"])
    # Rahmen, damit der Knopf auch auf gleichfarbigen Karten sichtbar bleibt
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("border_color", FARBEN["rahmen"])
    return ctk.CTkButton(master, text=text, command=befehl, **kwargs)


def gefahr_knopf(master, text: str, befehl: Callable[[], None], **kwargs) -> ctk.CTkButton:
    """Erzeugt einen Knopf für löschende Aktionen."""
    kwargs.setdefault("corner_radius", 10)
    kwargs.setdefault("height", 34)
    kwargs.setdefault("font", (SCHRIFT_TEXT, 12))
    kwargs.setdefault("fg_color", ("#b91c1c", "#7f1d1d"))
    kwargs.setdefault("hover_color", ("#991b1b", "#991b1b"))
    kwargs.setdefault("text_color", "#ffffff")
    return ctk.CTkButton(master, text=text, command=befehl, **kwargs)


def zentriere_fenster(fenster, breite: int, hoehe: int) -> None:
    """Platziert ein Fenster mittig auf dem Bildschirm."""
    fenster.update_idletasks()
    x = max(0, (fenster.winfo_screenwidth() - breite) // 2)
    y = max(0, (fenster.winfo_screenheight() - hoehe) // 3)
    fenster.geometry(f"{breite}x{hoehe}+{x}+{y}")
