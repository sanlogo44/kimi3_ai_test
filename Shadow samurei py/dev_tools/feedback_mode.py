"""Bewertungsspeicher und Bewertungsfenster mit CustomTkinter.

Sammelt Rückmeldungen zu Modellantworten (hilfreich / nicht hilfreich)
und zeigt sie in einem eigenen Fenster mit Filter und Zusammenfassung an.

Gespeichert wird über den Rust-Kern (``kimi3_kern.BewertungsSpeicher``,
Datei ``data/bewertungen.json``). Alte Dateien (``data/feedback.json``) und
alte englische Feldnamen liest der Kern weiterhin.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import customtkinter as ctk
from tkinter import messagebox

# Der Rust-Kern liegt im Projektordner, dieses Modul im Unterordner ``dev_tools``.
_PROJEKTORDNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJEKTORDNER not in sys.path:
    sys.path.insert(0, _PROJEKTORDNER)

from kern_modul import kern

from ui.theme import FARBEN, SCHRIFT_TEXT, ThemeVerwaltung, hole_theme
from ui.widgets import gefahr_knopf, neben_knopf, zentriere_fenster

DATEN_ORDNER = kern.datenordner()
BEWERTUNGS_DATEI = kern.datendatei("bewertungen.json")
ALTE_DATEI = kern.datendatei("feedback.json")

#: Anzeigetexte der drei möglichen Bewertungen (aus dem Rust-Kern)
BEWERTUNG_TEXT = {
    1: kern.BewertungsSpeicher.bewertungstext(1),
    -1: kern.BewertungsSpeicher.bewertungstext(-1),
    0: kern.BewertungsSpeicher.bewertungstext(0),
}


@dataclass
class BewertungsEintrag:
    """Eine einzelne Rückmeldung zu einer Modellantwort.

    Der Eintrag ist nur die Sicht der Oberfläche auf einen Datensatz des
    Rust-Kerns; gespeichert wird ausschließlich dort.
    """

    zeitstempel: str = ""
    modell: str = "unbekannt"
    frage: str = ""
    antwort: str = ""
    bewertung: int = 0  # +1 = hilfreich, -1 = nicht hilfreich, 0 = neutral
    markierungen: List[str] = field(default_factory=list)

    # ------------------------------------------------------------- Umwandlung
    def to_dict(self) -> Dict[str, Any]:
        """Gibt den Eintrag als Wörterbuch zurück."""
        return asdict(self)

    @property
    def text_bewertung(self) -> str:
        """Gibt die Bewertung als deutschen Text zurück."""
        return kern.BewertungsSpeicher.bewertungstext(self.bewertung)

    @classmethod
    def from_dict(cls, daten: Dict[str, Any]) -> "BewertungsEintrag":
        """Erzeugt einen Eintrag aus gespeicherten Daten.

        Alte englische Schlüssel (``ts``, ``model``, ``prompt`` ...) werden
        automatisch übernommen.
        """
        uebersetzung = {
            "ts": "zeitstempel",
            "model": "modell",
            "prompt": "frage",
            "response": "antwort",
            "rating": "bewertung",
            "tags": "markierungen",
        }
        bereinigt: Dict[str, Any] = {}
        for schluessel, wert in (daten or {}).items():
            name = uebersetzung.get(schluessel, schluessel)
            if name in cls.__dataclass_fields__:
                bereinigt[name] = wert
        eintrag = cls(**bereinigt)
        if eintrag.markierungen is None:
            eintrag.markierungen = []
        try:
            eintrag.bewertung = int(eintrag.bewertung)
        except (TypeError, ValueError):
            eintrag.bewertung = 0
        return eintrag


# Rückwärtskompatibler Name für älteren Code
FeedbackEntry = BewertungsEintrag


class BewertungsSpeicher:
    """Hülle um den Bewertungsspeicher des Rust-Kerns."""

    def __init__(self, dateipfad: str = BEWERTUNGS_DATEI):
        self._dateipfad = dateipfad
        self._speicher = kern.BewertungsSpeicher(pfad=dateipfad)

    # ------------------------------------------------------------------ Zugriff
    def fuege_hinzu(
        self,
        frage: str,
        antwort: str,
        bewertung: int,
        modell: str = "unbekannt",
        markierungen: Optional[List[str]] = None,
        **englische_namen: Any,
    ) -> BewertungsEintrag:
        """Fügt eine neue Bewertung hinzu und speichert sie.

        Aus Rückwärtskompatibilität werden auch die alten englischen
        Schlüsselwörter ``model_name`` und ``tags`` akzeptiert.
        """
        modell = englische_namen.get("model_name") or modell
        markierungen = englische_namen.get("tags") or markierungen
        gespeichert = self._speicher.fuege_hinzu(
            {
                "modell": modell or "unbekannt",
                "frage": frage or "",
                "antwort": antwort or "",
                "bewertung": int(bewertung),
                "markierungen": list(markierungen or []),
            }
        )
        return BewertungsEintrag.from_dict(gespeichert)

    def hole_alle(self) -> List[BewertungsEintrag]:
        """Gibt alle Bewertungen zurück."""
        return [BewertungsEintrag.from_dict(satz) for satz in self._speicher.hole_alle()]

    def je_modell(self, modell: str) -> List[BewertungsEintrag]:
        """Filtert die Bewertungen nach Modellname."""
        return [eintrag for eintrag in self.hole_alle() if eintrag.modell == modell]

    def zusammenfassung(self) -> Dict[str, Any]:
        """Erstellt eine Kurzstatistik über alle Bewertungen."""
        return self._speicher.zusammenfassung()

    def verteilung(self) -> Dict[str, int]:
        """Gibt die Verteilung für das Ringdiagramm zurück."""
        zusammen = self.zusammenfassung()
        return {
            BEWERTUNG_TEXT[1]: zusammen.get("positiv", 0),
            BEWERTUNG_TEXT[-1]: zusammen.get("negativ", 0),
            BEWERTUNG_TEXT[0]: zusammen.get("neutral", 0),
        }

    def leeren(self) -> None:
        """Löscht alle Bewertungen."""
        self._speicher.leere()

    # --------------------------------------------- englische Zweitbezeichnungen
    add_feedback = fuege_hinzu
    get_all = hole_alle
    get_by_model = je_modell
    get_summary = zusammenfassung
    clear = leeren


# Rückwärtskompatibler Name für älteren Code
FeedbackStore = BewertungsSpeicher


class BewertungsFenster:
    """Fenster mit allen gesammelten Bewertungen."""

    FILTER = ("Alle", "Nur hilfreich", "Nur nicht hilfreich")

    def __init__(self, eltern=None, speicher: Optional[BewertungsSpeicher] = None,
                 theme: Optional[ThemeVerwaltung] = None):
        self.speicher = speicher or BewertungsSpeicher()
        self.theme = theme or hole_theme()

        if eltern is None:
            self.fenster = ctk.CTk()
        else:
            self.fenster = ctk.CTkToplevel(eltern)
            self.fenster.transient(eltern)
        self.fenster.title("Bewertungen")
        self.fenster.configure(fg_color=FARBEN["fenster"])
        zentriere_fenster(self.fenster, 820, 600)
        self.fenster.minsize(640, 420)

        self.fenster.grid_columnconfigure(0, weight=1)
        self.fenster.grid_rowconfigure(2, weight=1)
        self._baue_oberflaeche()
        self._aktualisieren()

    # Zweitbezeichnung für älteren Code
    @property
    def win(self):
        """Gibt das Tk-Fenster zurück (alter Name)."""
        return self.fenster

    # ------------------------------------------------------------- Oberfläche
    def _baue_oberflaeche(self) -> None:
        """Baut Kopfzeile, Filterleiste, Liste und Fußzeile auf."""
        kopf = ctk.CTkFrame(self.fenster, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=18, pady=(16, 4), sticky="ew")
        kopf.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            kopf, text="Gesammelte Bewertungen", font=(SCHRIFT_TEXT, 20, "bold"),
            text_color=FARBEN["text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.zusammenfassung_label = ctk.CTkLabel(
            kopf, text="", font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text_gedaempft"],
            anchor="w", justify="left",
        )
        self.zusammenfassung_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        leiste = ctk.CTkFrame(self.fenster, fg_color="transparent")
        leiste.grid(row=1, column=0, padx=18, pady=(6, 4), sticky="ew")
        ctk.CTkLabel(
            leiste, text="Filter:", font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text"],
        ).pack(side="left", padx=(0, 6))
        self.filter_auswahl = ctk.CTkComboBox(
            leiste, values=list(self.FILTER), width=180, state="readonly",
            command=lambda _wert: self._aktualisieren(),
            font=(SCHRIFT_TEXT, 12), dropdown_font=(SCHRIFT_TEXT, 12),
        )
        self.filter_auswahl.set(self.FILTER[0])
        self.filter_auswahl.pack(side="left", padx=4)
        neben_knopf(leiste, "Aktualisieren", self._aktualisieren, width=120).pack(
            side="left", padx=4
        )

        self.liste = ctk.CTkScrollableFrame(
            self.fenster, corner_radius=12, fg_color=FARBEN["flaeche"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        self.liste.grid(row=2, column=0, padx=18, pady=6, sticky="nsew")
        self.liste.grid_columnconfigure(0, weight=1)

        fuss = ctk.CTkFrame(self.fenster, fg_color="transparent")
        fuss.grid(row=3, column=0, padx=18, pady=(6, 16), sticky="e")
        gefahr_knopf(fuss, "Alle löschen", self._alle_loeschen, width=130).pack(
            side="left", padx=4
        )
        neben_knopf(fuss, "Schließen", self.fenster.destroy, width=110).pack(
            side="left", padx=4
        )

    # ---------------------------------------------------------------- Aktionen
    def _gefilterte_eintraege(self) -> List[BewertungsEintrag]:
        """Gibt die Einträge passend zum gewählten Filter zurück."""
        eintraege = self.speicher.hole_alle()
        gewaehlt = self.filter_auswahl.get()
        if gewaehlt == self.FILTER[1]:
            return [e for e in eintraege if e.bewertung > 0]
        if gewaehlt == self.FILTER[2]:
            return [e for e in eintraege if e.bewertung < 0]
        return eintraege

    def _aktualisieren(self) -> None:
        """Baut die Liste und die Zusammenfassung neu auf."""
        zusammen = self.speicher.zusammenfassung()
        self.zusammenfassung_label.configure(
            text=(
                f"Gesamt: {zusammen['gesamt']}   ·   Hilfreich: {zusammen['positiv']}"
                f"   ·   Nicht hilfreich: {zusammen['negativ']}"
                f"   ·   Ohne Bewertung: {zusammen['neutral']}"
                f"   ·   Zustimmung: {zusammen['anteil']:.0%}"
            )
        )

        for widget in self.liste.winfo_children():
            widget.destroy()

        eintraege = self._gefilterte_eintraege()
        if not eintraege:
            ctk.CTkLabel(
                self.liste, text="Keine Bewertungen für diese Auswahl.",
                font=(SCHRIFT_TEXT, 13), text_color=FARBEN["text_gedaempft"],
            ).grid(row=0, column=0, pady=24)
            return

        for zeile, eintrag in enumerate(reversed(eintraege)):
            self._baue_karte(zeile, eintrag)

    def _baue_karte(self, zeile: int, eintrag: BewertungsEintrag) -> None:
        """Stellt eine einzelne Bewertung als Karte dar."""
        if eintrag.bewertung > 0:
            farbe_name = "erfolg"
        elif eintrag.bewertung < 0:
            farbe_name = "fehler"
        else:
            farbe_name = "text_gedaempft"

        karte = ctk.CTkFrame(
            self.liste, corner_radius=10, fg_color=FARBEN["flaeche_erhoeht"],
        )
        karte.grid(row=zeile, column=0, padx=8, pady=5, sticky="ew")
        karte.grid_columnconfigure(0, weight=1)

        kopf = ctk.CTkFrame(karte, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="ew")
        kopf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            kopf, text=eintrag.text_bewertung, font=(SCHRIFT_TEXT, 12, "bold"),
            text_color=FARBEN[farbe_name],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            kopf, text=f"{self._zeitpunkt(eintrag.zeitstempel)}   ·   Modell: {eintrag.modell}",
            font=(SCHRIFT_TEXT, 11), text_color=FARBEN["text_gedaempft"],
        ).grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(
            karte, text=f"Frage: {self._kurz(eintrag.frage)}",
            font=(SCHRIFT_TEXT, 11), text_color=FARBEN["text"],
            wraplength=680, justify="left", anchor="w",
        ).grid(row=1, column=0, padx=12, pady=2, sticky="ew")
        ctk.CTkLabel(
            karte, text=f"Antwort: {self._kurz(eintrag.antwort)}",
            font=(SCHRIFT_TEXT, 11), text_color=FARBEN["text_gedaempft"],
            wraplength=680, justify="left", anchor="w",
        ).grid(row=2, column=0, padx=12, pady=(2, 10), sticky="ew")

    @staticmethod
    def _zeitpunkt(zeitstempel: str) -> str:
        """Zeigt den Zeitstempel des Kerns ohne das trennende „T“ an."""
        return str(zeitstempel or "")[:19].replace("T", " ")

    @staticmethod
    def _kurz(text: str, laenge: int = 200) -> str:
        """Kürzt einen Text für die Kartenansicht."""
        text = (text or "").replace("\n", " ").strip()
        return text if len(text) <= laenge else text[:laenge] + " ..."

    def _alle_loeschen(self) -> None:
        """Löscht alle Bewertungen nach Rückfrage."""
        if messagebox.askyesno(
            "Löschen", "Sollen wirklich alle Bewertungen gelöscht werden?"
        ):
            self.speicher.leeren()
            self._aktualisieren()

    def zeige_modal(self) -> None:
        """Zeigt das Fenster und wartet, bis es geschlossen wird."""
        self.fenster.after(120, lambda: self.fenster.grab_set())
        self.fenster.wait_window()


# Rückwärtskompatibler Name für älteren Code
FeedbackViewer = BewertungsFenster


if __name__ == "__main__":  # pragma: no cover - manueller Test
    speicher = BewertungsSpeicher()
    if not speicher.hole_alle():
        speicher.fuege_hinzu("Was ist 2+2?", "Das Ergebnis ist 4.", 1, "Testmodell")
        speicher.fuege_hinzu("Erzähle einen Witz.", "Kein Witz gefunden.", -1, "Testmodell")
    BewertungsFenster(speicher=speicher).fenster.mainloop()
