"""Entwickler-Dashboard mit CustomTkinter.

Verbindet Metrikverfolgung, Schichttraining, Benchmarks und Checkpoints
in einem Fenster mit Registerkarten. Die Metriken werden zusätzlich als
Matplotlib-Diagramme dargestellt, die sich beim Umschalten zwischen
Hell- und Dunkel-Modus neu einfärben.
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, List, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

# Projektwurzel in den Suchpfad legen, damit die Module gefunden werden.
_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WURZEL not in sys.path:
    sys.path.insert(0, _WURZEL)

from dev_tools.benchmarker import Benchmarker
from dev_tools.feedback_mode import BewertungsSpeicher
from dev_tools.metrics_tracker import MetricsTracker, hole_verfolgung
from ui.diagramme import (
    MATPLOTLIB_VERFUEGBAR,
    DiagrammKarte,
    zeichne_bewertungsverteilung,
    zeichne_genauigkeit,
    zeichne_modellvergleich,
    zeichne_verlustkurve,
    zeichne_zeit_und_tokens,
)
from ui.theme import FARBEN, SCHRIFT_MONO, SCHRIFT_TEXT, ThemeVerwaltung, hole_theme
from ui.widgets import ThemeSchalter, akzent_knopf, gefahr_knopf, neben_knopf, zentriere_fenster

#: Anzeige- und Interntexte der Lernraten-Steuerung
PLANER = {"Keiner": None, "Stufenweise": "step", "Kosinus": "cosine"}


def _lade_modellkern():
    """Lädt die torch-abhängigen Kernfunktionen verzögert.

    Rückgabe ist ein Wörterbuch mit den benötigten Funktionen oder
    ``None``, wenn torch bzw. das Modellmodul nicht verfügbar sind.
    """
    try:
        from dev_tools.layer_trainer import LayerTrainer
        from model_manager import (
            DEVICE, ToyModel, evaluate, list_checkpoints, synthetic_data,
        )
    except Exception:
        return None
    return {
        "GERAET": DEVICE,
        "ToyModel": ToyModel,
        "SchichtTrainer": LayerTrainer,
        "bewerte": evaluate,
        "checkpoints": list_checkpoints,
        "daten": synthetic_data,
    }


class DevDashboard:
    """Fenster mit allen Entwickler-Werkzeugen."""

    def __init__(
        self,
        eltern=None,
        llm_engine=None,
        konfiguration: Optional[Dict[str, Any]] = None,
        theme: Optional[ThemeVerwaltung] = None,
        verfolgung: Optional[MetricsTracker] = None,
        bewertungen: Optional[BewertungsSpeicher] = None,
        **_alt,
    ):
        self.llm = llm_engine
        self.konfiguration = konfiguration or {}
        self.theme = theme or hole_theme()
        self.metriken = verfolgung or hole_verfolgung()
        self.bewertungen = bewertungen or BewertungsSpeicher()
        self.benchmarker: Optional[Benchmarker] = None
        self.kern = _lade_modellkern()
        self.verlustverlauf: List[Dict[str, Any]] = []
        self.schicht_felder: Dict[str, ctk.CTkCheckBox] = {}
        self._gefilterte: Optional[List[Any]] = None

        if eltern is None:
            self.fenster = ctk.CTk()
        else:
            self.fenster = ctk.CTkToplevel(eltern)
            self.fenster.transient(eltern)
        self.fenster.title("Entwickler-Dashboard")
        self.fenster.configure(fg_color=FARBEN["fenster"])
        zentriere_fenster(self.fenster, 1180, 840)
        self.fenster.minsize(940, 660)
        self.fenster.grid_columnconfigure(0, weight=1)
        self.fenster.grid_rowconfigure(1, weight=1)

        self._baue_oberflaeche()
        self.aktualisiere_alles()

    # Zweitbezeichnung für älteren Code
    @property
    def win(self):
        """Gibt das Tk-Fenster zurück (alter Name)."""
        return self.fenster

    # ------------------------------------------------------------- Oberfläche
    def _baue_oberflaeche(self) -> None:
        """Baut Kopfzeile und Registerkarten auf."""
        kopf = ctk.CTkFrame(self.fenster, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=16, pady=(14, 0), sticky="ew")
        kopf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            kopf, text="Entwickler-Dashboard", font=(SCHRIFT_TEXT, 20, "bold"),
            text_color=FARBEN["text"],
        ).grid(row=0, column=0, sticky="w")
        ThemeSchalter(kopf, self.theme, kompakt=True).grid(row=0, column=2, sticky="e")

        self.register = ctk.CTkTabview(
            self.fenster, corner_radius=12, fg_color=FARBEN["flaeche"],
            segmented_button_selected_color=FARBEN["akzent"],
            segmented_button_selected_hover_color=FARBEN["akzent_hover"],
            text_color=FARBEN["text"],
        )
        self.register.grid(row=1, column=0, padx=16, pady=14, sticky="nsew")

        self.reiter_uebersicht = self.register.add("Übersicht")
        self.reiter_metriken = self.register.add("Metriken")
        self.reiter_schichten = self.register.add("Schicht-Training")
        self.reiter_benchmarks = self.register.add("Benchmarks")
        self.reiter_checkpoints = self.register.add("Checkpoints")

        self._baue_uebersicht()
        self._baue_metriken()
        self._baue_schichten()
        self._baue_benchmarks()
        self._baue_checkpoints()

    def _karte(self, eltern, titel: str, zeile: int, spalte: int, **grid) -> ctk.CTkFrame:
        """Erzeugt eine beschriftete Karte im Gitter."""
        rahmen = ctk.CTkFrame(
            eltern, corner_radius=12, fg_color=FARBEN["flaeche_erhoeht"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        rahmen.grid(row=zeile, column=spalte, padx=10, pady=10, sticky="nsew", **grid)
        ctk.CTkLabel(
            rahmen, text=titel, font=(SCHRIFT_TEXT, 15, "bold"),
            text_color=FARBEN["text"], anchor="w",
        ).pack(anchor="w", padx=16, pady=(12, 6))
        return rahmen

    def _zeile(self, eltern, text: str) -> None:
        """Fügt einer Karte eine Textzeile hinzu."""
        ctk.CTkLabel(
            eltern, text=text, font=(SCHRIFT_TEXT, 12),
            text_color=FARBEN["text_gedaempft"], anchor="w", justify="left",
        ).pack(anchor="w", padx=16, pady=2)

    # -------------------------------------------------------------- Übersicht
    def _baue_uebersicht(self) -> None:
        """Baut die Übersicht mit Modell-, Konfigurations- und Aktionskarte."""
        rahmen = self.reiter_uebersicht
        rahmen.grid_columnconfigure((0, 1), weight=1)
        # Leerzeile unten dehnt sich, damit die Karten den Inhalt umschließen.
        rahmen.grid_rowconfigure(2, weight=1)

        info = self._karte(rahmen, "Modell", 0, 0)
        if self.llm is not None:
            self._zeile(info, f"Name: {getattr(self.llm, 'model_name', 'unbekannt')}")
            self._zeile(info, f"Gerät: {str(getattr(self.llm, 'device', '?')).upper()}")
            self._zeile(
                info,
                f"4-Bit: {getattr(self.llm, 'use_4bit', False)}   ·   "
                f"Datentyp: {getattr(self.llm, 'dtype', '?')}",
            )
            self._zeile(
                info,
                f"Max. Werkzeug-Durchläufe: {getattr(self.llm, 'max_tool_iterations', '?')}",
            )
            self._zeile(
                info,
                "Geladen: ja" if getattr(self.llm, "model", None) is not None else "Geladen: nein",
            )
        else:
            self._zeile(info, "Es ist kein Sprachmodell geladen.")

        einstellung = self._karte(rahmen, "Konfiguration", 0, 1)
        hardware = self.konfiguration.get("hardware", {})
        modell = self.konfiguration.get("model", {})
        self._zeile(einstellung, f"Gerät: {hardware.get('device', 'auto')}")
        self._zeile(
            einstellung,
            f"4-Bit: {hardware.get('use_4bit', True)}   ·   FP16: {hardware.get('use_fp16', True)}",
        )
        self._zeile(einstellung, f"Max. Werkzeug-Durchläufe: {modell.get('max_tool_iterations', 5)}")
        self._zeile(
            einstellung,
            f"Protokollstufe: {self.konfiguration.get('logging', {}).get('level', 'INFO')}",
        )
        self._zeile(
            einstellung,
            "Kernmodule (torch): verfügbar" if self.kern else "Kernmodule (torch): nicht verfügbar",
        )

        aktionen = self._karte(rahmen, "Schnellaktionen", 1, 0, columnspan=2)
        reihe = ctk.CTkFrame(aktionen, fg_color="transparent")
        reihe.pack(anchor="w", padx=16, pady=(4, 12))
        akzent_knopf(reihe, "Alles aktualisieren", self.aktualisiere_alles, width=170).pack(
            side="left", padx=(0, 8)
        )
        neben_knopf(reihe, "CSV-Export", self._exportiere_csv, width=140).pack(side="left", padx=8)
        gefahr_knopf(reihe, "Alte Metriken löschen", self._loesche_alte_metriken, width=190).pack(
            side="left", padx=8
        )

        self.uebersicht_status = ctk.CTkLabel(
            aktionen, text="", font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text_gedaempft"],
            anchor="w", justify="left",
        )
        self.uebersicht_status.pack(anchor="w", padx=16, pady=(0, 14))

    # --------------------------------------------------------------- Metriken
    def _baue_metriken(self) -> None:
        """Baut die Metrik-Registerkarte mit Diagrammen und Tabelle."""
        rahmen = self.reiter_metriken
        rahmen.grid_columnconfigure(0, weight=1)
        rahmen.grid_rowconfigure(1, weight=3)
        rahmen.grid_rowconfigure(2, weight=2)

        kopf = ctk.CTkFrame(rahmen, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")
        kopf.grid_columnconfigure(0, weight=1)

        self.metrik_zusammenfassung = ctk.CTkLabel(
            kopf, text="Lade Zusammenfassung ...", font=(SCHRIFT_TEXT, 12),
            text_color=FARBEN["text"], anchor="w", justify="left",
        )
        self.metrik_zusammenfassung.grid(row=0, column=0, sticky="w", pady=(2, 4))

        filter_reihe = ctk.CTkFrame(kopf, fg_color="transparent")
        filter_reihe.grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(
            filter_reihe, text="Modell:", font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text"],
        ).pack(side="left", padx=(0, 6))
        self.filter_modell = ctk.CTkEntry(
            filter_reihe, placeholder_text="Modellname", width=150, font=(SCHRIFT_TEXT, 12),
        )
        self.filter_modell.pack(side="left", padx=4)
        neben_knopf(filter_reihe, "Filtern", self._filter_anwenden, width=90).pack(
            side="left", padx=4
        )
        neben_knopf(filter_reihe, "Zurücksetzen", self._filter_loeschen, width=120).pack(
            side="left", padx=4
        )

        diagramme = ctk.CTkFrame(rahmen, fg_color="transparent")
        diagramme.grid(row=1, column=0, padx=6, pady=2, sticky="nsew")
        diagramme.grid_columnconfigure((0, 1), weight=1)
        diagramme.grid_rowconfigure((0, 1), weight=1)

        self.diagramm_genauigkeit = DiagrammKarte(
            diagramme, self.theme, "Genauigkeit und Verlust je Lauf",
            lambda figur, farben: zeichne_genauigkeit(figur, farben, self._diagramm_eintraege()),
            hoehe=215,
        )
        self.diagramm_genauigkeit.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        self.diagramm_zeit = DiagrammKarte(
            diagramme, self.theme, "Trainingszeit und Tokens",
            lambda figur, farben: zeichne_zeit_und_tokens(figur, farben, self._diagramm_eintraege()),
            hoehe=215,
        )
        self.diagramm_zeit.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        self.diagramm_vergleich = DiagrammKarte(
            diagramme, self.theme, "Modellvergleich (Ø Genauigkeit)",
            lambda figur, farben: zeichne_modellvergleich(
                figur, farben, self.metriken.vergleich_je_modell()
            ),
            hoehe=200,
        )
        self.diagramm_vergleich.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")

        self.diagramm_bewertungen = DiagrammKarte(
            diagramme, self.theme, "Nutzerbewertungen",
            lambda figur, farben: zeichne_bewertungsverteilung(
                figur, farben, self.bewertungen.verteilung()
            ),
            hoehe=200,
        )
        self.diagramm_bewertungen.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")

        self.metrik_tabelle = ctk.CTkTextbox(
            rahmen, font=(SCHRIFT_MONO, 11), wrap="none", corner_radius=10,
            fg_color=FARBEN["flaeche"], text_color=FARBEN["text"],
            border_width=1, border_color=FARBEN["rahmen"], height=150,
        )
        self.metrik_tabelle.grid(row=2, column=0, padx=10, pady=(4, 10), sticky="nsew")
        self.metrik_tabelle.configure(state="disabled")

    def _diagramm_eintraege(self) -> List[Any]:
        """Gibt die Einträge zurück, die in den Diagrammen erscheinen."""
        if self._gefilterte is not None:
            return self._gefilterte
        return self.metriken.hole_letzte(40)

    # -------------------------------------------------------- Schicht-Training
    def _baue_schichten(self) -> None:
        """Baut die Registerkarte für das selektive Schichttraining."""
        rahmen = self.reiter_schichten
        rahmen.grid_columnconfigure(0, weight=1)
        rahmen.grid_rowconfigure(4, weight=1)

        kopf = ctk.CTkFrame(rahmen, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")
        kopf.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            kopf, text="Selektives Schicht-Training", font=(SCHRIFT_TEXT, 15, "bold"),
            text_color=FARBEN["text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")
        neben_knopf(kopf, "Alle auswählen", self._alle_schichten, width=140).grid(
            row=0, column=1, padx=4
        )
        neben_knopf(kopf, "Auswahl leeren", self._keine_schichten, width=140).grid(
            row=0, column=2, padx=4
        )

        self.schicht_liste = ctk.CTkScrollableFrame(
            rahmen, height=170, corner_radius=10, fg_color=FARBEN["flaeche"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        self.schicht_liste.grid(row=1, column=0, padx=10, pady=6, sticky="ew")
        self._fuelle_schichten()

        parameter = ctk.CTkFrame(rahmen, fg_color="transparent")
        parameter.grid(row=2, column=0, padx=10, pady=6, sticky="ew")

        def feld(text: str, breite: int, vorgabe: str) -> ctk.CTkEntry:
            """Erzeugt ein beschriftetes Eingabefeld in der Parameterzeile."""
            ctk.CTkLabel(
                parameter, text=text, font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text"],
            ).pack(side="left", padx=(0, 4))
            eingabe = ctk.CTkEntry(parameter, width=breite, font=(SCHRIFT_TEXT, 12))
            eingabe.insert(0, vorgabe)
            eingabe.pack(side="left", padx=(0, 14))
            return eingabe

        self.schicht_epochen = feld("Epochen:", 70, "10")
        self.schicht_lernrate = feld("Lernrate:", 80, "0.01")

        ctk.CTkLabel(
            parameter, text="Lernraten-Planer:", font=(SCHRIFT_TEXT, 12),
            text_color=FARBEN["text"],
        ).pack(side="left", padx=(0, 4))
        self.schicht_planer = ctk.CTkComboBox(
            parameter, values=list(PLANER), width=140, state="readonly",
            font=(SCHRIFT_TEXT, 12), dropdown_font=(SCHRIFT_TEXT, 12),
        )
        self.schicht_planer.set("Keiner")
        self.schicht_planer.pack(side="left", padx=(0, 14))

        self.schicht_geduld = feld("Frühabbruch nach:", 60, "0")

        knopfreihe = ctk.CTkFrame(rahmen, fg_color="transparent")
        knopfreihe.grid(row=3, column=0, padx=10, pady=(4, 6), sticky="ew")
        akzent_knopf(knopfreihe, "Training starten", self._starte_schichttraining, width=170).pack(
            side="left", padx=(0, 10)
        )
        self.schicht_status = ctk.CTkLabel(
            knopfreihe, text="Bereit", font=(SCHRIFT_TEXT, 12),
            text_color=FARBEN["text_gedaempft"],
        )
        self.schicht_status.pack(side="left", padx=6)

        unten = ctk.CTkFrame(rahmen, fg_color="transparent")
        unten.grid(row=4, column=0, padx=10, pady=(4, 12), sticky="nsew")
        unten.grid_columnconfigure(0, weight=3)
        unten.grid_columnconfigure(1, weight=2)
        unten.grid_rowconfigure(0, weight=1)

        self.schicht_protokoll = ctk.CTkTextbox(
            unten, font=(SCHRIFT_MONO, 11), wrap="word", corner_radius=10,
            fg_color=FARBEN["flaeche"], text_color=FARBEN["text"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        self.schicht_protokoll.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        self.schicht_protokoll.configure(state="disabled")

        self.diagramm_verlust = DiagrammKarte(
            unten, self.theme, "Verlustkurve",
            lambda figur, farben: zeichne_verlustkurve(figur, farben, self.verlustverlauf),
            hoehe=230,
        )
        self.diagramm_verlust.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

    def _fuelle_schichten(self) -> None:
        """Listet die trainierbaren Schichten als Auswahlfelder auf."""
        for widget in self.schicht_liste.winfo_children():
            widget.destroy()
        self.schicht_felder = {}

        namen: List[str] = []
        if self.kern:
            try:
                namen = self.kern["ToyModel"]().layer_names()
            except Exception:
                namen = []
        if not namen and getattr(self.llm, "model", None) is not None:
            try:
                namen = [
                    name for name, teil in self.llm.model.named_modules()
                    if not list(teil.children())
                    and any(p.requires_grad for p in teil.parameters())
                ]
            except Exception:
                namen = []

        if not namen:
            ctk.CTkLabel(
                self.schicht_liste,
                text="Keine Schichten gefunden – torch ist nicht installiert "
                     "oder es wurde kein Modell geladen.",
                font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text_gedaempft"],
                wraplength=620, justify="left",
            ).pack(anchor="w", padx=12, pady=12)
            return

        spalten = 3
        for nummer, name in enumerate(namen):
            zeile, spalte = divmod(nummer, spalten)
            feld = ctk.CTkCheckBox(
                self.schicht_liste, text=name, font=(SCHRIFT_TEXT, 11),
                text_color=FARBEN["text"], fg_color=FARBEN["akzent"],
                hover_color=FARBEN["akzent_hover"],
            )
            feld.grid(row=zeile, column=spalte, padx=10, pady=5, sticky="w")
            self.schicht_felder[name] = feld

    # ------------------------------------------------------------- Benchmarks
    def _baue_benchmarks(self) -> None:
        """Baut die Registerkarte für die Benchmark-Steuerung."""
        rahmen = self.reiter_benchmarks
        rahmen.grid_columnconfigure(0, weight=1)
        rahmen.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            rahmen, text="Benchmark-Steuerung", font=(SCHRIFT_TEXT, 15, "bold"),
            text_color=FARBEN["text"], anchor="w",
        ).grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        steuerung = ctk.CTkFrame(rahmen, fg_color="transparent")
        steuerung.grid(row=1, column=0, padx=10, pady=6, sticky="ew")

        self.bench_status = ctk.CTkLabel(
            steuerung, text="Status: gestoppt", font=(SCHRIFT_TEXT, 12),
            text_color=FARBEN["text_gedaempft"],
        )
        self.bench_status.pack(side="left", padx=(0, 16))

        self.bench_knopf = akzent_knopf(
            steuerung, "Dauerlauf starten", self._benchmark_umschalten, width=170
        )
        self.bench_knopf.pack(side="left", padx=6)
        neben_knopf(steuerung, "Einzelmessung", self._einzelbenchmark, width=150).pack(
            side="left", padx=6
        )

        ctk.CTkLabel(
            steuerung, text="Intervall (s):", font=(SCHRIFT_TEXT, 12),
            text_color=FARBEN["text"],
        ).pack(side="left", padx=(16, 4))
        self.bench_intervall = ctk.CTkEntry(steuerung, width=70, font=(SCHRIFT_TEXT, 12))
        self.bench_intervall.insert(0, "30")
        self.bench_intervall.pack(side="left")

        self.bench_protokoll = ctk.CTkTextbox(
            rahmen, font=(SCHRIFT_MONO, 11), wrap="word", corner_radius=10,
            fg_color=FARBEN["flaeche"], text_color=FARBEN["text"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        self.bench_protokoll.grid(row=2, column=0, padx=10, pady=(6, 12), sticky="nsew")
        self.bench_protokoll.configure(state="disabled")
        if not self.kern:
            self._bench_notiz(
                "Benchmarks benötigen torch und das Modul model_manager. "
                "Bitte „pip install torch“ ausführen."
            )

    # ------------------------------------------------------------ Checkpoints
    def _baue_checkpoints(self) -> None:
        """Baut die Registerkarte mit den gespeicherten Checkpoints."""
        rahmen = self.reiter_checkpoints
        rahmen.grid_columnconfigure(0, weight=1)
        rahmen.grid_rowconfigure(1, weight=1)

        kopf = ctk.CTkFrame(rahmen, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")
        kopf.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            kopf, text="Gespeicherte Checkpoints", font=(SCHRIFT_TEXT, 15, "bold"),
            text_color=FARBEN["text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")
        neben_knopf(kopf, "Aktualisieren", self._aktualisiere_checkpoints, width=140).grid(
            row=0, column=1, sticky="e"
        )

        self.checkpoint_tabelle = ctk.CTkTextbox(
            rahmen, font=(SCHRIFT_MONO, 11), wrap="none", corner_radius=10,
            fg_color=FARBEN["flaeche"], text_color=FARBEN["text"],
            border_width=1, border_color=FARBEN["rahmen"],
        )
        self.checkpoint_tabelle.grid(row=1, column=0, padx=10, pady=(6, 12), sticky="nsew")
        self.checkpoint_tabelle.configure(state="disabled")

    # ---------------------------------------------------------------- Aktionen
    def aktualisiere_alles(self) -> None:
        """Aktualisiert Metriken, Diagramme und Checkpoints."""
        self._aktualisiere_metriken()
        self._aktualisiere_checkpoints()
        anzahl = self.metriken.zusammenfassung().get("anzahl", 0)
        hinweis = "" if MATPLOTLIB_VERFUEGBAR else "  ·  Matplotlib fehlt – keine Diagramme."
        self.uebersicht_status.configure(
            text=f"{anzahl} Metrik-Einträge geladen.{hinweis}"
        )

    def _setze_text(self, feld: ctk.CTkTextbox, text: str) -> None:
        """Ersetzt den Inhalt eines schreibgeschützten Textfeldes."""
        feld.configure(state="normal")
        feld.delete("0.0", "end")
        feld.insert("0.0", text)
        feld.configure(state="disabled")

    def _tabelle(self, eintraege: List[Any]) -> str:
        """Formatiert Metrik-Einträge als feste Textspalten."""
        kopf = (
            f"{'Zeitpunkt':<17} {'Modell':<22} {'Genauigk.':>10} {'Verlust':>9} "
            f"{'Zeit (s)':>9} {'Tokens':>9} {'Epochen':>8}  Markierungen"
        )
        zeilen = [kopf, "-" * len(kopf)]
        for eintrag in eintraege:
            markierungen = ", ".join(eintrag.markierungen or [])
            zeilen.append(
                f"{eintrag.kurzzeit:<17} {str(eintrag.modell)[:22]:<22} "
                f"{eintrag.genauigkeit:>10.4f} {eintrag.verlust:>9.4f} "
                f"{eintrag.trainingszeit:>9.2f} {eintrag.tokens:>9} "
                f"{eintrag.epochen:>8}  {markierungen}"
            )
        if not eintraege:
            zeilen.append("Keine Einträge vorhanden.")
        return "\n".join(zeilen)

    def _aktualisiere_metriken(self) -> None:
        """Lädt Zusammenfassung, Tabelle und Diagramme neu."""
        zusammen = self.metriken.zusammenfassung()
        self.metrik_zusammenfassung.configure(
            text=(
                f"Einträge: {zusammen['anzahl']}   ·   "
                f"Beste Genauigkeit: {zusammen['beste_genauigkeit']:.2%}   ·   "
                f"Ø Genauigkeit: {zusammen['durchschnitt_genauigkeit']:.2%}   ·   "
                f"Ø Verlust: {zusammen['durchschnitt_verlust']:.4f}   ·   "
                f"Ø Zeit: {zusammen['durchschnitt_zeit']:.2f} s   ·   "
                f"Tokens: {zusammen['tokens_gesamt']}"
            )
        )
        eintraege = self._gefilterte if self._gefilterte is not None else self.metriken.hole_letzte(50)
        self._setze_text(self.metrik_tabelle, self._tabelle(eintraege))
        for karte in (
            self.diagramm_genauigkeit, self.diagramm_zeit,
            self.diagramm_vergleich, self.diagramm_bewertungen,
        ):
            karte.zeichne_neu()

    def _filter_anwenden(self) -> None:
        """Beschränkt Tabelle und Diagramme auf ein Modell."""
        name = self.filter_modell.get().strip()
        self._gefilterte = self.metriken.filtere(modell=name) if name else None
        self._aktualisiere_metriken()

    def _filter_loeschen(self) -> None:
        """Hebt den Modellfilter auf."""
        self.filter_modell.delete(0, "end")
        self._gefilterte = None
        self._aktualisiere_metriken()

    def _exportiere_csv(self) -> None:
        """Exportiert alle Metriken als CSV-Datei."""
        pfad = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV-Datei", "*.csv")],
            initialfile="metriken.csv",
        )
        if not pfad:
            return
        try:
            self.metriken.exportiere_csv(pfad)
            messagebox.showinfo("Export", f"Metriken exportiert nach:\n{pfad}")
        except Exception as fehler:
            messagebox.showerror("Fehler", f"Export nicht möglich: {fehler}")

    def _loesche_alte_metriken(self) -> None:
        """Fragt nach einer Tagesanzahl und löscht ältere Einträge."""
        dialog = ctk.CTkToplevel(self.fenster)
        dialog.title("Alte Metriken löschen")
        dialog.configure(fg_color=FARBEN["fenster"])
        zentriere_fenster(dialog, 380, 190)
        dialog.transient(self.fenster)
        dialog.after(120, dialog.grab_set)

        ctk.CTkLabel(
            dialog, text="Einträge löschen, die älter sind als (Tage):",
            font=(SCHRIFT_TEXT, 13), text_color=FARBEN["text"], wraplength=330,
        ).pack(pady=(20, 8), padx=20)
        eingabe = ctk.CTkEntry(dialog, width=90, font=(SCHRIFT_TEXT, 13), justify="center")
        eingabe.insert(0, "7")
        eingabe.pack(pady=4)

        def ausfuehren() -> None:
            """Führt das Löschen aus und schließt den Dialog."""
            try:
                tage = int(eingabe.get())
            except ValueError:
                messagebox.showerror("Fehler", "Bitte eine ganze Zahl eingeben.")
                return
            entfernt = self.metriken.loesche_aelter_als(tage)
            dialog.destroy()
            self._gefilterte = None
            self.aktualisiere_alles()
            messagebox.showinfo("Erfolg", f"{entfernt} Einträge gelöscht.")

        reihe = ctk.CTkFrame(dialog, fg_color="transparent")
        reihe.pack(pady=14)
        gefahr_knopf(reihe, "Löschen", ausfuehren, width=110).pack(side="left", padx=6)
        neben_knopf(reihe, "Abbrechen", dialog.destroy, width=110).pack(side="left", padx=6)

    def _aktualisiere_checkpoints(self) -> None:
        """Liest die gespeicherten Checkpoints aus."""
        if not self.kern:
            self._setze_text(
                self.checkpoint_tabelle,
                "Kernmodule nicht verfügbar – torch ist nicht installiert.",
            )
            return
        try:
            checkpoints = self.kern["checkpoints"]()
        except Exception as fehler:
            self._setze_text(self.checkpoint_tabelle, f"Fehler: {fehler}")
            return

        kopf = f"{'Kennung':<12} {'Name':<24} {'Genauigkeit':>12}  Gespeichert"
        zeilen = [kopf, "-" * len(kopf)]
        for satz in checkpoints:
            genauigkeit = satz.get("accuracy")
            anzeige = f"{genauigkeit:.2%}" if genauigkeit is not None else "-"
            zeilen.append(
                f"{str(satz.get('id', '?')):<12} {str(satz.get('name', '?'))[:24]:<24} "
                f"{anzeige:>12}  {satz.get('saved_at', '?')}"
            )
        if not checkpoints:
            zeilen.append("Keine Checkpoints vorhanden.")
        self._setze_text(self.checkpoint_tabelle, "\n".join(zeilen))

    # --------------------------------------------------------- Schichttraining
    def _alle_schichten(self) -> None:
        """Wählt alle Schichten aus."""
        for feld in self.schicht_felder.values():
            feld.select()

    def _keine_schichten(self) -> None:
        """Hebt die Auswahl aller Schichten auf."""
        for feld in self.schicht_felder.values():
            feld.deselect()

    def _schicht_protokoll(self, text: str) -> None:
        """Hängt eine Zeile an das Trainingsprotokoll an."""
        self.schicht_protokoll.configure(state="normal")
        self.schicht_protokoll.insert("end", text + "\n")
        self.schicht_protokoll.configure(state="disabled")
        try:
            self.schicht_protokoll._textbox.see("end")
        except Exception:
            pass

    def _starte_schichttraining(self) -> None:
        """Prüft die Eingaben und startet das Training in einem Thread."""
        if not self.kern:
            messagebox.showerror(
                "Fehler",
                "Für das Schicht-Training werden torch und model_manager benötigt.",
            )
            return
        ausgewaehlt = [name for name, feld in self.schicht_felder.items() if feld.get()]
        if not ausgewaehlt:
            messagebox.showwarning("Hinweis", "Bitte mindestens eine Schicht auswählen.")
            return
        try:
            epochen = int(self.schicht_epochen.get())
            lernrate = float(self.schicht_lernrate.get())
            geduld = int(self.schicht_geduld.get())
        except ValueError:
            messagebox.showerror("Fehler", "Ungültige Trainings-Parameter.")
            return
        if epochen <= 0:
            messagebox.showerror("Fehler", "Die Epochenzahl muss größer als 0 sein.")
            return
        planer = PLANER.get(self.schicht_planer.get())

        self.verlustverlauf = []
        self.schicht_status.configure(
            text=f"Training läuft: {', '.join(ausgewaehlt)}", text_color=FARBEN["info"]
        )
        self._setze_text(self.schicht_protokoll, "")

        def arbeite() -> None:
            """Führt das Training im Hintergrund aus."""
            try:
                merkmale, ziele = self.kern["daten"]()
                modell = self.kern["ToyModel"]().to(self.kern["GERAET"])
                trainer = self.kern["SchichtTrainer"](modell, device=self.kern["GERAET"])

                def fortschritt(epoche: int, gesamt: int, verlust: float) -> None:
                    """Meldet den Fortschritt an die Oberfläche."""
                    self.verlustverlauf.append({"epoch": epoche, "loss": verlust})
                    self.fenster.after(
                        0,
                        lambda: (
                            self._schicht_protokoll(
                                f"Epoche {epoche}/{gesamt} – Verlust: {verlust:.4f}"
                            ),
                            self.diagramm_verlust.zeichne_neu(),
                        ),
                    )

                ergebnis = trainer.train(
                    merkmale, ziele, layer_names=ausgewaehlt, epochs=epochen,
                    lr=lernrate, scheduler_type=planer,
                    early_stop_patience=geduld if geduld > 0 else None,
                    progress_callback=fortschritt,
                )
                self.fenster.after(0, lambda: self._training_fertig(ergebnis))
            except Exception as fehler:
                meldung = str(fehler)
                self.fenster.after(
                    0,
                    lambda: self.schicht_status.configure(
                        text=f"Fehler: {meldung}", text_color=FARBEN["fehler"]
                    ),
                )

        threading.Thread(target=arbeite, daemon=True).start()

    def _training_fertig(self, ergebnis: Dict[str, Any]) -> None:
        """Zeigt das Trainingsergebnis an und speichert es als Metrik."""
        genauigkeit = float(ergebnis.get("accuracy", 0.0))
        dauer = float(ergebnis.get("train_time", 0.0))
        epochen = int(ergebnis.get("epochs_trained", 0))
        verlust = float(ergebnis.get("final_loss", 0.0))
        self.schicht_status.configure(
            text=(
                f"Fertig – Genauigkeit: {genauigkeit:.2%}   ·   "
                f"Zeit: {dauer:.2f} s   ·   Epochen: {epochen}"
            ),
            text_color=FARBEN["erfolg"],
        )
        self._schicht_protokoll("")
        self._schicht_protokoll("Training abgeschlossen.")
        self._schicht_protokoll(f"   Genauigkeit: {genauigkeit:.4f}")
        self._schicht_protokoll(f"   Endverlust:  {verlust:.4f}")
        self._schicht_protokoll(f"   Dauer:       {dauer:.2f} s")
        self.metriken.add(
            modell=f"schicht_{ergebnis.get('layers_trained', 'alle')}",
            genauigkeit=genauigkeit, verlust=verlust, trainingszeit=dauer,
            tokens=0, epochen=epochen, markierungen=["schicht_training"],
        )
        self._gefilterte = None
        self._aktualisiere_metriken()

    # -------------------------------------------------------------- Benchmarks
    def _bench_notiz(self, text: str) -> None:
        """Hängt eine Zeile an das Benchmark-Protokoll an."""
        self.bench_protokoll.configure(state="normal")
        self.bench_protokoll.insert("end", text + "\n")
        self.bench_protokoll.configure(state="disabled")
        try:
            self.bench_protokoll._textbox.see("end")
        except Exception:
            pass

    def _hole_benchmarker(self) -> Benchmarker:
        """Erzeugt den Benchmarker bei Bedarf."""
        if self.benchmarker is None:
            self.benchmarker = Benchmarker(
                modellfabrik=self.kern["ToyModel"],
                datenfabrik=self.kern["daten"],
                metrikverfolgung=self.metriken,
                geraet=self.kern["GERAET"],
            )
        return self.benchmarker

    def _einzelbenchmark(self) -> None:
        """Führt eine einzelne Messung im Hintergrund aus."""
        if not self.kern:
            messagebox.showerror("Fehler", "Benchmarks benötigen torch und model_manager.")
            return
        self._bench_notiz("Einzelmessung läuft ...")

        def arbeite() -> None:
            """Misst einmal und meldet das Ergebnis."""
            try:
                ergebnis = self._hole_benchmarker().fuehre_einzeln_aus()
                self.fenster.after(
                    0,
                    lambda: (
                        self._bench_notiz(
                            f"Ergebnis: Genauigkeit {ergebnis.genauigkeit:.4f}   ·   "
                            f"Dauer {ergebnis.dauer:.3f} s"
                        ),
                        self._aktualisiere_metriken(),
                    ),
                )
            except Exception as fehler:
                meldung = str(fehler)
                self.fenster.after(0, lambda: self._bench_notiz(f"Fehler: {meldung}"))

        threading.Thread(target=arbeite, daemon=True).start()

    def _benchmark_umschalten(self) -> None:
        """Startet oder stoppt den wiederkehrenden Benchmark."""
        if not self.kern:
            messagebox.showerror("Fehler", "Benchmarks benötigen torch und model_manager.")
            return
        if self.benchmarker is not None and self.benchmarker.laeuft():
            self.benchmarker.stoppe()
            self.bench_status.configure(
                text="Status: gestoppt", text_color=FARBEN["text_gedaempft"]
            )
            self.bench_knopf.configure(text="Dauerlauf starten")
            self._bench_notiz("Dauerlauf gestoppt.")
            return

        try:
            intervall = max(1, int(self.bench_intervall.get()))
        except ValueError:
            intervall = 30
            self.bench_intervall.delete(0, "end")
            self.bench_intervall.insert(0, "30")

        def rueckmeldung(ergebnis) -> None:
            """Trägt jedes Messergebnis in das Protokoll ein."""
            self.fenster.after(
                0,
                lambda: (
                    self._bench_notiz(
                        f"[{ergebnis.zeitstempel}] Genauigkeit {ergebnis.genauigkeit:.4f}"
                        f"   ·   {ergebnis.dauer:.3f} s"
                    ),
                    self._aktualisiere_metriken(),
                ),
            )

        self._hole_benchmarker().starte_wiederkehrend(
            intervall=intervall, rueckmeldung=rueckmeldung
        )
        self.bench_status.configure(text="Status: läuft", text_color=FARBEN["erfolg"])
        self.bench_knopf.configure(text="Dauerlauf stoppen")
        self._bench_notiz(f"Dauerlauf gestartet (Intervall: {intervall} s).")

    # ----------------------------------------------------------------- Fenster
    def schliessen(self) -> None:
        """Beendet laufende Benchmarks und schließt das Fenster."""
        if self.benchmarker is not None:
            self.benchmarker.stoppe()
        self.fenster.destroy()

    def zeige_modal(self) -> None:
        """Zeigt das Fenster und wartet, bis es geschlossen wird."""
        self.fenster.protocol("WM_DELETE_WINDOW", self.schliessen)
        self.fenster.after(150, lambda: self.fenster.grab_set())
        self.fenster.wait_window()


if __name__ == "__main__":  # pragma: no cover - manueller Test
    DevDashboard().fenster.mainloop()
