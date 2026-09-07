"""Chat-Oberfläche im Claude-Stil auf Basis von CustomTkinter.

Enthält Seitenleiste mit Gesprächsliste, Nachrichtenblasen mit
Markdown-Darstellung, mehrzeiliges Eingabefeld, Streaming-Ausgabe,
Abbruch-Knopf, Kopier- und Wiederholen-Aktionen sowie einen
Hell-/Dunkel-Umschalter.

Die Oberfläche ist unabhängig vom Sprachmodell: Der Aufrufer übergibt
eine Antwortfunktion. Ohne Antwortfunktion läuft ein Demo-Modus, der
zum Testen der Darstellung genutzt werden kann.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ui.gespraech_speicher import Gespraech, GespraechSpeicher, Nachricht
from ui.markdown_ansicht import MarkdownAnsicht
from ui.theme import FARBEN, SCHRIFT_TEXT, ThemeVerwaltung, hole_theme
from ui.widgets import Hinweis, ThemeSchalter, akzent_knopf, neben_knopf

# Typ der Antwortfunktion:
# (Nachricht, Verlauf, Teilstück-Rückruf, Abbruch-Ereignis) -> Antwort
AntwortFunktion = Callable[[str, List[Dict[str, str]], Callable[[str], None], threading.Event], object]


class NachrichtBlase(ctk.CTkFrame):
    """Eine Nachricht im Chatverlauf."""

    def __init__(self, master, theme: ThemeVerwaltung, rolle: str, inhalt: str = "",
                 auf_kopieren: Optional[Callable[[str], None]] = None,
                 auf_wiederholen: Optional[Callable[[], None]] = None,
                 auf_bewertung: Optional[Callable[[int], None]] = None):
        super().__init__(master, fg_color="transparent")
        self._theme = theme
        self.rolle = rolle
        self._auf_kopieren = auf_kopieren
        self._auf_wiederholen = auf_wiederholen
        self._auf_bewertung = auf_bewertung
        self._fusszeile: Optional[ctk.CTkFrame] = None

        ist_benutzer = rolle == "benutzer"
        self.grid_columnconfigure(0, weight=1)

        huelle = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color=FARBEN["blase_benutzer"] if ist_benutzer else "transparent",
            border_width=0,
        )
        huelle.grid(
            row=0, column=0,
            sticky="e" if ist_benutzer else "ew",
            padx=(60, 4) if ist_benutzer else (0, 40),
            pady=(6, 2),
        )
        huelle.grid_columnconfigure(1, weight=1)

        if not ist_benutzer:
            self._zeichne_avatar(huelle)

        kopf_spalte = 1 if not ist_benutzer else 0
        inhalt_rahmen = ctk.CTkFrame(huelle, fg_color="transparent")
        inhalt_rahmen.grid(row=0, column=kopf_spalte, sticky="ew",
                           padx=(4, 14) if not ist_benutzer else (14, 14),
                           pady=(10, 8))
        inhalt_rahmen.grid_columnconfigure(0, weight=1)

        if not ist_benutzer:
            ctk.CTkLabel(
                inhalt_rahmen, text="Assistent",
                font=(SCHRIFT_TEXT, 11, "bold"),
                text_color=FARBEN["text_gedaempft"], anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        self.ansicht = MarkdownAnsicht(
            inhalt_rahmen, theme,
            grundschrift=13,
            hintergrund_name="blase_benutzer" if ist_benutzer else "fenster",
            zeichen_breite=self._breite_fuer(inhalt) if ist_benutzer else None,
        )
        self.ansicht.grid(row=1, column=0, sticky="ew")
        self.ansicht.setze_text(inhalt)

        self._inhalt_rahmen = inhalt_rahmen
        if not ist_benutzer and inhalt:
            self.zeige_aktionen()

    @staticmethod
    def _breite_fuer(inhalt: str) -> int:
        """Schätzt die nötige Feldbreite einer Benutzernachricht in Zeichen."""
        laengste = max((len(zeile) for zeile in (inhalt or " ").split("\n")), default=10)
        return max(12, min(62, laengste + 1))

    def _zeichne_avatar(self, eltern) -> None:
        """Zeichnet das runde Assistenten-Symbol."""
        avatar = ctk.CTkLabel(
            eltern, text="✳", width=30, height=30, corner_radius=15,
            fg_color=FARBEN["akzent"], text_color="#ffffff",
            font=(SCHRIFT_TEXT, 15, "bold"),
        )
        avatar.grid(row=0, column=0, sticky="nw", padx=(2, 6), pady=(12, 0))

    # ---------------------------------------------------------------- Inhalte
    @property
    def text(self) -> str:
        """Gibt den Markdown-Quelltext der Nachricht zurück."""
        return self.ansicht.quelltext

    def setze_text(self, inhalt: str) -> None:
        """Ersetzt den Nachrichtentext."""
        self.ansicht.setze_text(inhalt)

    def haenge_an(self, teilstueck: str) -> None:
        """Fügt ein Teilstück an (Streaming)."""
        self.ansicht.haenge_text_an(teilstueck)

    def zeige_werkzeuge(self, namen: List[str]) -> None:
        """Zeigt die verwendeten Werkzeuge unterhalb der Nachricht an."""
        if not namen:
            return
        ctk.CTkLabel(
            self._inhalt_rahmen,
            text="🔧  " + ", ".join(namen),
            font=(SCHRIFT_TEXT, 11),
            text_color=FARBEN["text_gedaempft"],
            anchor="w",
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

    def zeige_aktionen(self) -> None:
        """Zeigt die Aktionsleiste (Kopieren, Wiederholen, Bewerten)."""
        if self._fusszeile is not None:
            return
        self._fusszeile = ctk.CTkFrame(self._inhalt_rahmen, fg_color="transparent")
        self._fusszeile.grid(row=3, column=0, sticky="w", pady=(6, 0))

        def klein(text: str, befehl, breite: int = 90):
            return ctk.CTkButton(
                self._fusszeile, text=text, command=befehl, width=breite, height=26,
                corner_radius=8, fg_color="transparent",
                hover_color=FARBEN["flaeche_erhoeht"],
                text_color=FARBEN["text_gedaempft"], font=(SCHRIFT_TEXT, 11),
            )

        if self._auf_kopieren:
            klein("Kopieren", lambda: self._auf_kopieren(self.text), 76).pack(side="left", padx=(0, 2))
        if self._auf_wiederholen:
            klein("Neu erzeugen", self._auf_wiederholen, 98).pack(side="left", padx=2)
        if self._auf_bewertung:
            self._daumen_hoch = klein("Hilfreich", lambda: self._bewerte(1), 74)
            self._daumen_hoch.pack(side="left", padx=2)
            self._daumen_runter = klein("Nicht hilfreich", lambda: self._bewerte(-1), 104)
            self._daumen_runter.pack(side="left", padx=2)

    def _bewerte(self, wert: int) -> None:
        """Leitet eine Bewertung weiter und blendet die Knöpfe aus."""
        if self._auf_bewertung:
            self._auf_bewertung(wert)
        for knopf in (getattr(self, "_daumen_hoch", None), getattr(self, "_daumen_runter", None)):
            if knopf is not None:
                knopf.configure(state="disabled")


class SystemZeile(ctk.CTkFrame):
    """Dezente Systemmeldung im Chatverlauf."""

    def __init__(self, master, text: str, stufe: str = "info"):
        super().__init__(master, fg_color="transparent")
        farbe = {
            "info": "text_gedaempft",
            "fehler": "fehler",
            "erfolg": "erfolg",
            "warnung": "warnung",
        }.get(stufe, "text_gedaempft")
        ctk.CTkLabel(
            self, text=text, font=(SCHRIFT_TEXT, 11, "italic"),
            text_color=FARBEN[farbe], wraplength=760, justify="center",
        ).pack(pady=6)


class TippAnzeige(ctk.CTkFrame):
    """Animierte Punkte, während die Antwort erzeugt wird."""

    def __init__(self, master, theme: ThemeVerwaltung):
        super().__init__(master, fg_color="transparent")
        self._laeuft = True
        self._schritt = 0
        self._label = ctk.CTkLabel(
            self, text="✳  denkt nach", font=(SCHRIFT_TEXT, 12, "italic"),
            text_color=FARBEN["text_gedaempft"], anchor="w",
        )
        self._label.pack(anchor="w", padx=(8, 0), pady=4)
        self._animiere()

    def _animiere(self) -> None:
        """Aktualisiert die Punkt-Animation."""
        if not self._laeuft:
            return
        punkte = "." * (self._schritt % 4)
        try:
            self._label.configure(text=f"✳  denkt nach{punkte}")
        except Exception:
            return
        self._schritt += 1
        self.after(400, self._animiere)

    def stoppen(self) -> None:
        """Beendet die Animation."""
        self._laeuft = False


class ChatOberflaeche(ctk.CTkFrame):
    """Vollständige Chat-Oberfläche mit Seitenleiste und Eingabezeile."""

    def __init__(self, master, theme: Optional[ThemeVerwaltung] = None,
                 antwort_funktion: Optional[AntwortFunktion] = None,
                 modell_name: str = "Demo-Modell",
                 speicher: Optional[GespraechSpeicher] = None,
                 auf_bewertung: Optional[Callable[[str, str, int], None]] = None,
                 kopf_knoepfe: Optional[List[tuple]] = None,
                 **kwargs):
        kwargs.setdefault("fg_color", FARBEN["fenster"])
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)

        self._theme = theme or hole_theme()
        self._antwort_funktion = antwort_funktion or self._demo_antwort
        self._modell_name = modell_name
        self._speicher = speicher or GespraechSpeicher()
        self._auf_bewertung = auf_bewertung
        self._kopf_knoepfe = kopf_knoepfe or []

        self._abbruch = threading.Event()
        self._erzeugt = False
        self._eingabe_bereit = True
        self._aktuelle_blase: Optional[NachrichtBlase] = None
        self._tipp_anzeige: Optional[TippAnzeige] = None
        self._gespraech: Gespraech = self._speicher.alle()[0] if self._speicher.alle() else self._speicher.neues()
        self._seitenleiste_sichtbar = True

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._baue_seitenleiste()
        self._baue_hauptbereich()
        self._zeichne_gespraech()
        self._aktualisiere_gespraechsliste()

    # ============================================================ Seitenleiste
    def _baue_seitenleiste(self) -> None:
        """Erstellt die Seitenleiste mit Gesprächsliste."""
        self.seitenleiste = ctk.CTkFrame(
            self, width=250, corner_radius=0, fg_color=FARBEN["seitenleiste"],
        )
        self.seitenleiste.grid(row=0, column=0, sticky="nsw")
        self.seitenleiste.grid_propagate(False)
        self.seitenleiste.grid_rowconfigure(2, weight=1)
        self.seitenleiste.grid_columnconfigure(0, weight=1)

        kopf = ctk.CTkFrame(self.seitenleiste, fg_color="transparent")
        kopf.grid(row=0, column=0, sticky="ew", padx=14, pady=(16, 8))
        ctk.CTkLabel(
            kopf, text="✳  Kimi3", font=(SCHRIFT_TEXT, 17, "bold"),
            text_color=FARBEN["text"],
        ).pack(side="left")

        akzent_knopf(
            self.seitenleiste, "+   Neues Gespräch", self._neues_gespraech, height=38,
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 10))

        self.gespraechsliste = ctk.CTkScrollableFrame(
            self.seitenleiste, fg_color="transparent", corner_radius=0,
            label_text="Verlauf", label_font=(SCHRIFT_TEXT, 11, "bold"),
            label_text_color=FARBEN["text_gedaempft"],
        )
        self.gespraechsliste.grid(row=2, column=0, sticky="nsew", padx=8, pady=0)
        self.gespraechsliste.grid_columnconfigure(0, weight=1)

        fuss = ctk.CTkFrame(self.seitenleiste, fg_color="transparent")
        fuss.grid(row=3, column=0, sticky="ew", padx=14, pady=(8, 14))
        fuss.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            fuss, text="Erscheinungsbild", font=(SCHRIFT_TEXT, 11),
            text_color=FARBEN["text_gedaempft"], anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ThemeSchalter(fuss, self._theme, kompakt=True).grid(row=1, column=0, sticky="ew")

    def _aktualisiere_gespraechsliste(self) -> None:
        """Baut die Liste der gespeicherten Gespräche neu auf."""
        for kind in self.gespraechsliste.winfo_children():
            kind.destroy()

        for gespraech in self._speicher.alle():
            aktiv = gespraech.kennung == self._gespraech.kennung
            zeile = ctk.CTkFrame(
                self.gespraechsliste, corner_radius=10,
                fg_color=FARBEN["flaeche"] if aktiv else "transparent",
            )
            zeile.pack(fill="x", pady=2, padx=2)
            zeile.grid_columnconfigure(0, weight=1)

            ctk.CTkButton(
                zeile, text=gespraech.titel, anchor="w", height=30,
                corner_radius=8, fg_color="transparent",
                hover_color=FARBEN["rahmen"],
                text_color=FARBEN["text"] if aktiv else FARBEN["text_gedaempft"],
                font=(SCHRIFT_TEXT, 12, "bold" if aktiv else "normal"),
                command=lambda k=gespraech.kennung: self._waehle_gespraech(k),
            ).grid(row=0, column=0, sticky="ew", padx=(4, 0), pady=2)

            ctk.CTkButton(
                zeile, text="✕", width=26, height=26, corner_radius=8,
                fg_color="transparent", hover_color=FARBEN["rahmen"],
                text_color=FARBEN["text_gedaempft"], font=(SCHRIFT_TEXT, 11),
                command=lambda k=gespraech.kennung: self._loesche_gespraech(k),
            ).grid(row=0, column=1, padx=(0, 4))

    # =========================================================== Hauptbereich
    def _baue_hauptbereich(self) -> None:
        """Erstellt Kopfzeile, Verlauf und Eingabebereich."""
        haupt = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        haupt.grid(row=0, column=1, sticky="nsew")
        haupt.grid_rowconfigure(1, weight=1)
        haupt.grid_columnconfigure(0, weight=1)

        # -------------------------------------------------------- Kopfzeile
        kopf = ctk.CTkFrame(haupt, fg_color="transparent", height=56)
        kopf.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 4))
        kopf.grid_columnconfigure(1, weight=1)

        neben_knopf(kopf, "Menü", self._seitenleiste_umschalten, width=62, height=32).grid(
            row=0, column=0, padx=(0, 10)
        )

        titel_bereich = ctk.CTkFrame(kopf, fg_color="transparent")
        titel_bereich.grid(row=0, column=1, sticky="w")
        self.titel_label = ctk.CTkLabel(
            titel_bereich, text=self._gespraech.titel,
            font=(SCHRIFT_TEXT, 15, "bold"), text_color=FARBEN["text"], anchor="w",
        )
        self.titel_label.pack(anchor="w")
        self.modell_label = ctk.CTkLabel(
            titel_bereich, text=self._modell_name, font=(SCHRIFT_TEXT, 11),
            text_color=FARBEN["text_gedaempft"], anchor="w",
        )
        self.modell_label.pack(anchor="w")

        knopf_leiste = ctk.CTkFrame(kopf, fg_color="transparent")
        knopf_leiste.grid(row=0, column=2, sticky="e")
        self.kopf_knopf_leiste = knopf_leiste
        for text, befehl in self._kopf_knoepfe:
            neben_knopf(knopf_leiste, text, befehl, width=120).pack(side="left", padx=4)

        # ---------------------------------------------------------- Verlauf
        self.verlauf = ctk.CTkScrollableFrame(
            haupt, fg_color="transparent", corner_radius=0,
        )
        self.verlauf.grid(row=1, column=0, sticky="nsew", padx=(18, 10), pady=(4, 0))
        self.verlauf.grid_columnconfigure(0, weight=1)

        # -------------------------------------------------------- Eingabe
        eingabe_huelle = ctk.CTkFrame(
            haupt, corner_radius=18, fg_color=FARBEN["flaeche"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        eingabe_huelle.grid(row=2, column=0, sticky="ew", padx=18, pady=(10, 4))
        eingabe_huelle.grid_columnconfigure(0, weight=1)

        self.eingabe = ctk.CTkTextbox(
            eingabe_huelle, height=52, corner_radius=14, wrap="word",
            font=(SCHRIFT_TEXT, 13), fg_color="transparent",
            text_color=FARBEN["text"], border_width=0, activate_scrollbars=False,
        )
        self.eingabe.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=(12, 6))
        self.eingabe.bind("<Return>", self._auf_eingabetaste)
        self.eingabe.bind("<Shift-Return>", lambda e: None)
        self.eingabe.bind("<KeyRelease>", self._passe_eingabehoehe_an)
        self._platzhalter_setzen()

        knopf_spalte = ctk.CTkFrame(eingabe_huelle, fg_color="transparent")
        knopf_spalte.grid(row=0, column=1, sticky="se", padx=(0, 12), pady=(0, 10))

        self.senden_knopf = ctk.CTkButton(
            knopf_spalte, text="Senden", width=96, height=40, corner_radius=20,
            fg_color=FARBEN["akzent"], hover_color=FARBEN["akzent_hover"],
            text_color="#ffffff", font=(SCHRIFT_TEXT, 13, "bold"),
            command=self._senden,
        )
        self.senden_knopf.pack(side="right")

        self.stopp_knopf = ctk.CTkButton(
            knopf_spalte, text="Stopp", width=86, height=40, corner_radius=20,
            fg_color=FARBEN["flaeche_erhoeht"], hover_color=FARBEN["rahmen"],
            text_color=FARBEN["text"], font=(SCHRIFT_TEXT, 13, "bold"),
            command=self.abbrechen,
        )

        werkzeug_leiste = ctk.CTkFrame(eingabe_huelle, fg_color="transparent")
        werkzeug_leiste.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkLabel(
            werkzeug_leiste,
            text="Eingabetaste sendet  ·  Umschalt+Eingabetaste für neue Zeile",
            font=(SCHRIFT_TEXT, 11), text_color=FARBEN["text_gedaempft"],
        ).pack(side="left")
        self.zeichen_label = ctk.CTkLabel(
            werkzeug_leiste, text="", font=(SCHRIFT_TEXT, 11),
            text_color=FARBEN["text_gedaempft"],
        )
        self.zeichen_label.pack(side="right")

        # --------------------------------------------------------- Statuszeile
        self.status = Hinweis(haupt, font=(SCHRIFT_TEXT, 11))
        self.status.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))
        self.status.zeige("Bereit", "neutral")

    # ================================================================ Eingabe
    def _platzhalter_setzen(self) -> None:
        """Zeigt den Platzhaltertext im leeren Eingabefeld."""
        self.eingabe.delete("1.0", "end")
        self.eingabe.insert("1.0", "Frag mich etwas ...")
        self.eingabe.configure(text_color=FARBEN["text_gedaempft"])
        self._platzhalter_aktiv = True
        self.eingabe.bind("<FocusIn>", self._platzhalter_entfernen)

    def _platzhalter_entfernen(self, _ereignis=None) -> None:
        """Entfernt den Platzhalter, sobald das Feld fokussiert wird."""
        if getattr(self, "_platzhalter_aktiv", False):
            self.eingabe.delete("1.0", "end")
            self.eingabe.configure(text_color=FARBEN["text"])
            self._platzhalter_aktiv = False

    def _eingabe_text(self) -> str:
        """Gibt den aktuellen Eingabetext zurück."""
        if getattr(self, "_platzhalter_aktiv", False):
            return ""
        return self.eingabe.get("1.0", "end").strip()

    def _auf_eingabetaste(self, _ereignis):
        """Sendet die Nachricht bei Eingabetaste ohne Umschalt."""
        self._senden()
        return "break"

    def _passe_eingabehoehe_an(self, _ereignis=None) -> None:
        """Vergrößert das Eingabefeld mit dem Text (max. sechs Zeilen)."""
        text = self.eingabe.get("1.0", "end-1c")
        zeilen = max(1, min(6, text.count("\n") + 1 + len(text) // 90))
        self.eingabe.configure(height=32 + 20 * (zeilen - 1) + 20)
        self.zeichen_label.configure(text=f"{len(text)} Zeichen" if text.strip() else "")

    # ================================================================ Verlauf
    def _leere_verlauf_ansicht(self) -> None:
        """Entfernt alle Widgets aus dem Verlauf."""
        for kind in self.verlauf.winfo_children():
            kind.destroy()

    def _zeichne_gespraech(self) -> None:
        """Stellt das aktuell gewählte Gespräch dar."""
        self._leere_verlauf_ansicht()
        self.titel_label.configure(text=self._gespraech.titel)

        if not self._gespraech.nachrichten:
            self._zeige_begruessung()
            return

        for nachricht in self._gespraech.nachrichten:
            if nachricht.rolle == "system":
                SystemZeile(self.verlauf, nachricht.inhalt).pack(fill="x")
                continue
            blase = self._erzeuge_blase(nachricht.rolle, nachricht.inhalt)
            if nachricht.werkzeuge:
                blase.zeige_werkzeuge(nachricht.werkzeuge)
        self._nach_unten_rollen()

    def _zeige_begruessung(self) -> None:
        """Zeigt den Begrüßungsschirm für leere Gespräche."""
        huelle = ctk.CTkFrame(self.verlauf, fg_color="transparent")
        huelle.pack(fill="both", expand=True, pady=(70, 20))
        ctk.CTkLabel(
            huelle, text="✳", font=(SCHRIFT_TEXT, 40, "bold"),
            text_color=FARBEN["akzent"],
        ).pack()
        ctk.CTkLabel(
            huelle, text="Wie kann ich helfen?",
            font=(SCHRIFT_TEXT, 22, "bold"), text_color=FARBEN["text"],
        ).pack(pady=(10, 6))
        ctk.CTkLabel(
            huelle, text="Stelle eine Frage oder wähle einen Vorschlag.",
            font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text_gedaempft"],
        ).pack()

        vorschlaege = [
            "Erkläre mir das MCP-Protokoll",
            "Berechne 17 * 23 + 42",
            "Wie ist das Wetter in Hamburg?",
            "Wie viel Uhr ist es?",
        ]
        raster = ctk.CTkFrame(huelle, fg_color="transparent")
        raster.pack(pady=18)
        for i, vorschlag in enumerate(vorschlaege):
            neben_knopf(
                raster, vorschlag, lambda v=vorschlag: self._vorschlag_nutzen(v),
                width=240, height=40,
            ).grid(row=i // 2, column=i % 2, padx=6, pady=6)

    def _vorschlag_nutzen(self, text: str) -> None:
        """Übernimmt einen Vorschlag in die Eingabe und sendet ihn."""
        self._platzhalter_entfernen()
        self.eingabe.delete("1.0", "end")
        self.eingabe.insert("1.0", text)
        self._senden()

    def _erzeuge_blase(self, rolle: str, inhalt: str) -> NachrichtBlase:
        """Erzeugt eine Nachrichtenblase im Verlauf."""
        blase = NachrichtBlase(
            self.verlauf, self._theme, rolle, inhalt,
            auf_kopieren=self._in_ablage_kopieren,
            auf_wiederholen=self._wiederholen if rolle == "assistent" else None,
            auf_bewertung=(lambda wert, b=None: self._bewerten(wert)) if (rolle == "assistent" and self._auf_bewertung) else None,
        )
        blase.pack(fill="x", pady=1)
        return blase

    def _nach_unten_rollen(self) -> None:
        """Rollt den Verlauf an das Ende."""
        def rollen():
            try:
                self.verlauf.update_idletasks()
                self.verlauf._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass
        self.after(60, rollen)
        self.after(260, rollen)

    # =============================================================== Aktionen
    def _in_ablage_kopieren(self, text: str) -> None:
        """Kopiert einen Text in die Systemablage."""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status.zeige("In die Zwischenablage kopiert.", "erfolg")
        except Exception:
            self.status.zeige("Kopieren nicht möglich.", "fehler")

    def _bewerten(self, wert: int) -> None:
        """Leitet eine Bewertung an den Aufrufer weiter."""
        if not self._auf_bewertung:
            return
        frage = ""
        for nachricht in reversed(self._gespraech.nachrichten):
            if nachricht.rolle == "benutzer":
                frage = nachricht.inhalt
                break
        antwort = self._gespraech.nachrichten[-1].inhalt if self._gespraech.nachrichten else ""
        self._auf_bewertung(frage, antwort, wert)
        self.status.zeige("Danke für die Rückmeldung.", "erfolg")

    def _wiederholen(self) -> None:
        """Erzeugt die letzte Antwort erneut."""
        if self._erzeugt:
            return
        letzte_frage = ""
        for nachricht in reversed(self._gespraech.nachrichten):
            if nachricht.rolle == "benutzer":
                letzte_frage = nachricht.inhalt
                break
        if not letzte_frage:
            return
        while self._gespraech.nachrichten and self._gespraech.nachrichten[-1].rolle != "benutzer":
            self._gespraech.nachrichten.pop()
        if self._gespraech.nachrichten:
            self._gespraech.nachrichten.pop()
        self._speicher.speichern()
        self._zeichne_gespraech()
        self._starte_antwort(letzte_frage)

    def _neues_gespraech(self) -> None:
        """Beginnt ein neues Gespräch."""
        if self._erzeugt:
            self.status.zeige("Bitte warten, bis die Antwort fertig ist.", "warnung")
            return
        # Leeres Gespräch nicht doppelt anlegen.
        if not self._gespraech.nachrichten:
            self._zeichne_gespraech()
            return
        self._gespraech = self._speicher.neues()
        self._zeichne_gespraech()
        self._aktualisiere_gespraechsliste()

    def _waehle_gespraech(self, kennung: str) -> None:
        """Wechselt zu einem gespeicherten Gespräch."""
        if self._erzeugt:
            self.status.zeige("Bitte warten, bis die Antwort fertig ist.", "warnung")
            return
        gespraech = self._speicher.hole(kennung)
        if gespraech:
            self._gespraech = gespraech
            self._zeichne_gespraech()
            self._aktualisiere_gespraechsliste()

    def _loesche_gespraech(self, kennung: str) -> None:
        """Löscht ein Gespräch aus dem Verlauf."""
        self._speicher.loesche(kennung)
        if self._gespraech.kennung == kennung:
            vorhandene = self._speicher.alle()
            self._gespraech = vorhandene[0] if vorhandene else self._speicher.neues()
            self._zeichne_gespraech()
        self._aktualisiere_gespraechsliste()

    def _seitenleiste_umschalten(self) -> None:
        """Blendet die Seitenleiste ein oder aus."""
        if self._seitenleiste_sichtbar:
            self.seitenleiste.grid_remove()
        else:
            self.seitenleiste.grid(row=0, column=0, sticky="nsw")
        self._seitenleiste_sichtbar = not self._seitenleiste_sichtbar

    def leere_aktuelles_gespraech(self) -> None:
        """Löscht alle Nachrichten des aktuellen Gesprächs."""
        self._gespraech.nachrichten.clear()
        self._gespraech.titel = "Neues Gespräch"
        self._speicher.speichern()
        self._zeichne_gespraech()
        self._aktualisiere_gespraechsliste()

    # ============================================================== Erzeugung
    def setze_modell_name(self, name: str) -> None:
        """Aktualisiert die Modellanzeige in der Kopfzeile."""
        self._modell_name = name
        self.modell_label.configure(text=name)

    def setze_antwort_funktion(self, funktion: AntwortFunktion) -> None:
        """Hinterlegt die Funktion, die Antworten erzeugt."""
        self._antwort_funktion = funktion

    def zeige_status(self, text: str, stufe: str = "neutral") -> None:
        """Setzt den Text der Statuszeile."""
        self.status.zeige(text, stufe)

    def zeige_systemmeldung(self, text: str, stufe: str = "info") -> None:
        """Fügt eine Systemmeldung in den Verlauf ein."""
        SystemZeile(self.verlauf, text, stufe).pack(fill="x")
        self._nach_unten_rollen()

    def _senden(self) -> None:
        """Verarbeitet den Sende-Knopf."""
        if self._erzeugt:
            return
        text = self._eingabe_text()
        if not text:
            return
        if not self._eingabe_bereit:
            self.status.zeige("Das Modell ist noch nicht bereit.", "warnung")
            return
        self.eingabe.delete("1.0", "end")
        self._passe_eingabehoehe_an()
        self._starte_antwort(text)

    def _starte_antwort(self, frage: str) -> None:
        """Legt die Frage im Verlauf ab und startet die Antworterzeugung."""
        if not self._gespraech.nachrichten:
            self._leere_verlauf_ansicht()

        self._gespraech.fuege_hinzu("benutzer", frage)
        self._speicher.speichern()
        self._erzeuge_blase("benutzer", frage)
        self.titel_label.configure(text=self._gespraech.titel)
        self._aktualisiere_gespraechsliste()

        self._tipp_anzeige = TippAnzeige(self.verlauf, self._theme)
        self._tipp_anzeige.pack(fill="x", padx=8)
        self._nach_unten_rollen()

        self._abbruch = threading.Event()
        self._setze_erzeugung(True)
        verlauf = self._gespraech.verlauf_fuer_modell()[:-1]

        def arbeiten():
            try:
                ergebnis = self._antwort_funktion(frage, verlauf, self._melde_teilstueck, self._abbruch)
                if isinstance(ergebnis, dict):
                    antwort = str(ergebnis.get("antwort", ""))
                    werkzeuge = list(ergebnis.get("werkzeuge", []))
                else:
                    antwort, werkzeuge = str(ergebnis or ""), []
                self.after(0, lambda: self._antwort_fertig(antwort, werkzeuge))
            except Exception as fehler:
                meldung = str(fehler)
                self.after(0, lambda: self._antwort_fehler(meldung))

        threading.Thread(target=arbeiten, daemon=True).start()

    def _melde_teilstueck(self, teilstueck: str) -> None:
        """Nimmt ein Teilstück der Antwort auf (aus dem Arbeitsthread)."""
        def anzeigen():
            if self._abbruch.is_set():
                return
            if self._tipp_anzeige is not None:
                self._tipp_anzeige.stoppen()
                self._tipp_anzeige.destroy()
                self._tipp_anzeige = None
            if self._aktuelle_blase is None:
                self._aktuelle_blase = self._erzeuge_blase("assistent", "")
            self._aktuelle_blase.haenge_an(teilstueck)
            self._nach_unten_rollen()
        self.after(0, anzeigen)

    def _antwort_fertig(self, antwort: str, werkzeuge: List[str]) -> None:
        """Schließt eine erzeugte Antwort ab."""
        if self._tipp_anzeige is not None:
            self._tipp_anzeige.stoppen()
            self._tipp_anzeige.destroy()
            self._tipp_anzeige = None

        if self._abbruch.is_set():
            antwort = (self._aktuelle_blase.text if self._aktuelle_blase else "") or "*Abgebrochen.*"

        if self._aktuelle_blase is None:
            blase = self._erzeuge_blase("assistent", antwort)
        else:
            blase = self._aktuelle_blase
            if antwort and antwort != blase.text:
                blase.setze_text(antwort)
        blase.zeige_werkzeuge(werkzeuge)
        blase.zeige_aktionen()

        self._gespraech.fuege_hinzu("assistent", antwort, werkzeuge)
        self._speicher.speichern()
        self._aktuelle_blase = None
        self._setze_erzeugung(False)
        self.status.zeige("Bereit", "neutral")
        self._aktualisiere_gespraechsliste()
        self._nach_unten_rollen()

    def _antwort_fehler(self, meldung: str) -> None:
        """Zeigt einen Fehler bei der Antworterzeugung an."""
        if self._tipp_anzeige is not None:
            self._tipp_anzeige.stoppen()
            self._tipp_anzeige.destroy()
            self._tipp_anzeige = None
        self._aktuelle_blase = None
        self.zeige_systemmeldung(f"Fehler: {meldung}", "fehler")
        self._setze_erzeugung(False)
        self.status.zeige("Fehler bei der Antworterzeugung", "fehler")

    def abbrechen(self) -> None:
        """Bricht die laufende Antworterzeugung ab."""
        if not self._erzeugt:
            return
        self._abbruch.set()
        self.status.zeige("Abbruch angefordert ...", "warnung")

    def abbruch_ereignis(self) -> threading.Event:
        """Gibt das aktuelle Abbruch-Ereignis zurück."""
        return self._abbruch

    def setze_bereit(self, bereit: bool, status: str = "") -> None:
        """Schaltet die Eingabe frei oder sperrt sie (z. B. beim Modellladen)."""
        self._eingabe_bereit = bereit
        zustand = "normal" if bereit and not self._erzeugt else "disabled"
        self.senden_knopf.configure(state=zustand)
        if status:
            self.status.zeige(status, "erfolg" if bereit else "warnung")

    def _setze_erzeugung(self, laeuft: bool) -> None:
        """Wechselt zwischen Sende- und Stopp-Knopf."""
        self._erzeugt = laeuft
        if laeuft:
            self.senden_knopf.pack_forget()
            self.stopp_knopf.pack(side="right")
            self.status.zeige("Antwort wird erzeugt ...", "info")
        else:
            self.stopp_knopf.pack_forget()
            self.senden_knopf.pack(side="right")
            self.senden_knopf.configure(state="normal" if self._eingabe_bereit else "disabled")

    # ================================================================== Demo
    @staticmethod
    def _demo_antwort(frage: str, verlauf: List[Dict[str, str]],
                      melde_teilstueck: Callable[[str], None],
                      abbruch: threading.Event) -> Dict[str, object]:
        """Erzeugt eine Beispielantwort ohne Sprachmodell (Demo-Modus)."""
        antwort = (
            f"Du hast gefragt: **{frage.strip()}**\n\n"
            "Dies ist der Demo-Modus der Chat-Oberfläche. Angebunden an die "
            "LLM-Engine erscheint hier die echte Antwort des Modells.\n\n"
            "## Was die Oberfläche kann\n"
            "- Markdown mit Überschriften, Listen und `Inline-Code`\n"
            "- Code-Blöcke mit eigener Hintergrundfarbe\n"
            "- Streaming, Abbruch, Kopieren und Neu-Erzeugen\n\n"
            "```python\n"
            "def begruessung(name: str) -> str:\n"
            "    return f\"Hallo, {name}!\"\n"
            "```\n\n"
            "> Tipp: Der Hell-/Dunkel-Umschalter sitzt unten in der Seitenleiste."
        )
        for stueck in antwort.split(" "):
            if abbruch.is_set():
                break
            melde_teilstueck(stueck + " ")
            time.sleep(0.012)
        return {"antwort": antwort, "werkzeuge": []}


def starte_demo() -> None:
    """Startet die Chat-Oberfläche im Demo-Modus (ohne Sprachmodell)."""
    theme = hole_theme()
    fenster = ctk.CTk()
    fenster.title("Kimi3 – Chat (Demo)")
    fenster.geometry("1180x820")
    fenster.minsize(900, 620)
    fenster.configure(fg_color=FARBEN["fenster"])
    fenster.grid_rowconfigure(0, weight=1)
    fenster.grid_columnconfigure(0, weight=1)
    chat = ChatOberflaeche(fenster, theme, modell_name="Demo-Modus (kein Modell geladen)")
    chat.grid(row=0, column=0, sticky="nsew")
    fenster.mainloop()


if __name__ == "__main__":
    starte_demo()
