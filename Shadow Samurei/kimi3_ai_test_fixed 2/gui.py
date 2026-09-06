#!/usr/bin/env python3
"""Desktop-Oberfläche für den werkzeugfähigen Sprachassistenten.

Das Fenster besteht aus einer schmalen Kopfleiste (Anmeldung, Theme,
Entwickler-Werkzeuge) und der Chat-Oberfläche aus :mod:`ui.chat_interface`,
die dem Aussehen von Claude nachempfunden ist. Das Sprachmodell wird im
Hintergrund geladen; solange es fehlt, bleibt die Oberfläche bedienbar und
weist auf den Grund hin.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from tkinter import messagebox

from auth.auth_manager import AuthManager, AuthManagerUI, AnmeldeFenster
from config_loader import load_config
from dev_tools.dev_dashboard import DevDashboard
from dev_tools.feedback_mode import BewertungsFenster, BewertungsSpeicher
from logger import get_logger
from mcp_protocol import MCPClient
from settings_store import hole_einstellungen
from tools import create_math_tools
from ui.chat_interface import ChatOberflaeche
from ui.gespraech_speicher import GespraechSpeicher
from ui.theme import FARBEN, SCHRIFT_TEXT, hole_theme
from ui.widgets import akzent_knopf, neben_knopf


class ChatFenster:
    """Hauptfenster der Anwendung."""

    def __init__(self) -> None:
        self.konfiguration = load_config()
        self.protokoll = get_logger(self.konfiguration)
        self.einstellungen = hole_einstellungen()
        self.theme = hole_theme()

        self.server = create_math_tools()
        self.client = MCPClient(self.server)
        self.llm = None
        self.llm_fehler: Optional[str] = None
        self.schwarm = None  # wird erzeugt, sobald das Modell bereit ist
        self.schwarm_aktiv = bool(self.einstellungen.hole("schwarm_aktiv", False))

        self.verwaltung = AuthManager()
        self.bewertungen = BewertungsSpeicher()
        self.gespraeche = GespraechSpeicher()

        self.benutzer: Optional[str] = None
        self.ist_administrator = False
        self.bewertungsmodus = False
        self.dashboard: Optional[DevDashboard] = None

        self.fenster = ctk.CTk()
        self.fenster.title("Kimi3 – Werkzeugfähiger Assistent")
        self.fenster.configure(fg_color=FARBEN["fenster"])
        breite, hoehe = self.einstellungen.fenstergroesse(1220, 860)
        self.fenster.geometry(f"{breite}x{hoehe}")
        self.fenster.minsize(940, 640)
        self.fenster.grid_columnconfigure(0, weight=1)
        self.fenster.grid_rowconfigure(1, weight=1)

        self._baue_kopfleiste()
        self._baue_chat()

        self.fenster.protocol("WM_DELETE_WINDOW", self._beim_schliessen)
        self.theme.registriere_beobachter(self._auf_theme_wechsel)
        self._lade_modell_im_hintergrund()

    # ------------------------------------------------------------- Oberfläche
    def _baue_kopfleiste(self) -> None:
        """Erstellt die obere Leiste mit Anmeldung und Werkzeugen."""
        leiste = ctk.CTkFrame(
            self.fenster, fg_color=FARBEN["seitenleiste"], corner_radius=0, height=58
        )
        leiste.grid(row=0, column=0, sticky="ew")
        leiste.grid_columnconfigure(1, weight=1)

        titel = ctk.CTkFrame(leiste, fg_color="transparent")
        titel.grid(row=0, column=0, padx=(18, 10), pady=10, sticky="w")
        ctk.CTkLabel(
            titel, text="Kimi3", font=(SCHRIFT_TEXT, 18, "bold"),
            text_color=FARBEN["akzent"],
        ).pack(side="left")
        self.benutzer_label = ctk.CTkLabel(
            titel, text="nicht angemeldet", font=(SCHRIFT_TEXT, 11),
            text_color=FARBEN["text_gedaempft"],
        )
        self.benutzer_label.pack(side="left", padx=(12, 0))

        knoepfe = ctk.CTkFrame(leiste, fg_color="transparent")
        knoepfe.grid(row=0, column=2, padx=(10, 18), pady=10, sticky="e")

        # Schwarm-Umschalter: aktiviert mehrere Agenten und Subagents
        # fuer die Beantwortung jeder Frage.
        schwarm_rahmen = ctk.CTkFrame(knoepfe, fg_color="transparent")
        schwarm_rahmen.pack(side="left", padx=(0, 10))
        self.schwarm_schalter = ctk.CTkSwitch(
            schwarm_rahmen,
            text="Schwarm",
            command=self._schwarm_umschalten,
            font=(SCHRIFT_TEXT, 11),
            width=44,
            height=22,
        )
        self.schwarm_schalter.pack(side="left")
        if self.schwarm_aktiv:
            self.schwarm_schalter.select()

        # Ziel-Umschalter: arbeitet autonom so lange, bis das Ziel erreicht
        # ist. Hat Vorrang vor dem Schwarm, nutzt ihn aber intern.
        ziel_rahmen = ctk.CTkFrame(knoepfe, fg_color="transparent")
        ziel_rahmen.pack(side="left", padx=(0, 10))
        self.ziel_schalter = ctk.CTkSwitch(
            ziel_rahmen,
            text="Ziel",
            command=self._ziel_umschalten,
            font=(SCHRIFT_TEXT, 11),
            width=44,
            height=22,
        )
        self.ziel_schalter.pack(side="left")
        if self.ziel_aktiv:
            self.ziel_schalter.select()

        # Der Umschalter fuer Hell/Dunkel sitzt in der Seitenleiste des Chats,
        # deshalb erscheint er hier nicht noch einmal.
        self.anmelde_knopf = akzent_knopf(
            knoepfe, "Anmelden", self._anmelden, width=110, height=32
        )
        self.anmelde_knopf.pack(side="left", padx=4)

        self.bewertungs_knopf = neben_knopf(
            knoepfe, "Bewertungen", self._zeige_bewertungen, width=130, height=32
        )
        self.bewertungs_knopf.pack(side="left", padx=4)

        self.entwickler_knopf = neben_knopf(
            knoepfe, "Entwickler", self._oeffne_dashboard, width=120, height=32
        )
        self.entwickler_knopf.pack(side="left", padx=4)

        self.benutzer_knopf = neben_knopf(
            knoepfe, "Benutzer", self._oeffne_benutzerverwaltung, width=110, height=32
        )
        self.benutzer_knopf.pack(side="left", padx=4)

        self._setze_rechte(False)

    def _baue_chat(self) -> None:
        """Setzt die Chat-Oberfläche in das Fenster ein."""
        self.chat = ChatOberflaeche(
            self.fenster,
            theme=self.theme,
            antwort_funktion=self._beantworte,
            modell_name=self.konfiguration.get("model", {}).get("name", "unbekannt"),
            speicher=self.gespraeche,
            auf_bewertung=self._bewertung_speichern,
        )
        self.chat.grid(row=1, column=0, sticky="nsew")
        self.chat.setze_bereit(False, "Modell wird geladen ...")

    def _setze_rechte(self, administrator: bool) -> None:
        """Schaltet die Entwickler-Knöpfe je nach Rolle frei."""
        zustand = "normal" if administrator else "disabled"
        self.entwickler_knopf.configure(state=zustand)
        self.benutzer_knopf.configure(state=zustand)

    def _auf_theme_wechsel(self, _modus: str) -> None:
        """Färbt das Fenster nach einem Theme-Wechsel neu ein."""
        try:
            self.fenster.configure(fg_color=FARBEN["fenster"])
        except Exception:
            pass

    def _schwarm_umschalten(self) -> None:
        """Schaltet den Schwarm-Modus an oder aus und speichert die Wahl."""
        aktiv = self.schwarm_schalter.get() == 1
        self.schwarm_aktiv = aktiv
        self.einstellungen.setze("schwarm_aktiv", aktiv)
        if aktiv:
            if self.llm is None:
                self.chat.zeige_systemmeldung(
                    "Schwarm aktiviert – startet, sobald das Modell geladen ist.",
                    "info",
                )
            else:
                self.chat.zeige_systemmeldung(
                    "Schwarm aktiviert: mehrere Agenten bearbeiten jede Frage.",
                    "info",
                )
        else:
            self.chat.zeige_systemmeldung(
                "Schwarm deaktiviert – einzelner Assistent.", "info"
            )

    def _ziel_umschalten(self) -> None:
        """Schaltet den Ziel-Modus an oder aus und speichert die Wahl."""
        aktiv = self.ziel_schalter.get() == 1
        self.ziel_aktiv = aktiv
        self.einstellungen.setze("ziel_aktiv", aktiv)
        if aktiv:
            if self.llm is None:
                self.chat.zeige_systemmeldung(
                    "Ziel-Modus aktiviert – startet, sobald das Modell geladen ist.",
                    "info",
                )
            else:
                self.chat.zeige_systemmeldung(
                    "Ziel-Modus aktiviert: arbeitet so lange, bis das Ziel "
                    "erreicht ist.",
                    "info",
                )
        else:
            self.chat.zeige_systemmeldung(
                "Ziel-Modus deaktiviert.", "info"
            )

    # ---------------------------------------------------------------- Anmeldung
    def _anmelden(self) -> None:
        """Zeigt das Anmeldefenster und übernimmt das Ergebnis."""
        if self.benutzer:
            self._abmelden()
            return
        fenster = AnmeldeFenster(
            eltern=self.fenster, verwaltung=self.verwaltung,
            letzter_benutzer=self.einstellungen.hole("letzter_benutzer", ""),
        )
        fenster.zeige_modal()
        konto = getattr(fenster, "konto", None)
        if not konto:
            return
        benutzername = konto.get("benutzername", "")
        self.benutzer = benutzername
        self.ist_administrator = konto.get("rolle") == "admin"
        rolle = "Administrator" if self.ist_administrator else "Benutzer"
        self.benutzer_label.configure(text=f"{benutzername} ({rolle})")
        self.anmelde_knopf.configure(text="Abmelden")
        self._setze_rechte(self.ist_administrator)
        self.einstellungen.setze("letzter_benutzer", benutzername)
        self.chat.zeige_systemmeldung(f"Angemeldet als {benutzername}.", "erfolg")
        self.protokoll.info(f"Benutzer angemeldet: {benutzername}")

    def _abmelden(self) -> None:
        """Meldet den aktuellen Benutzer ab."""
        self.protokoll.info(f"Benutzer abgemeldet: {self.benutzer}")
        self.benutzer = None
        self.ist_administrator = False
        self.benutzer_label.configure(text="nicht angemeldet")
        self.anmelde_knopf.configure(text="Anmelden")
        self._setze_rechte(False)
        self.chat.zeige_systemmeldung("Abgemeldet.", "info")

    # ------------------------------------------------------------ Nebenfenster
    def _oeffne_dashboard(self) -> None:
        """Öffnet das Entwickler-Dashboard."""
        if not self.ist_administrator:
            messagebox.showwarning(
                "Kein Zugriff", "Nur Administratoren dürfen das Dashboard öffnen."
            )
            return
        self.dashboard = DevDashboard(
            eltern=self.fenster, llm_engine=self.llm,
            konfiguration=self.konfiguration, theme=self.theme,
            bewertungen=self.bewertungen,
        )
        self.dashboard.zeige_modal()

    def _oeffne_benutzerverwaltung(self) -> None:
        """Öffnet die Benutzerverwaltung."""
        if not self.ist_administrator:
            messagebox.showwarning(
                "Kein Zugriff", "Nur Administratoren dürfen Benutzer verwalten."
            )
            return
        AuthManagerUI(eltern=self.fenster, verwaltung=self.verwaltung).zeige_modal()

    def _zeige_bewertungen(self) -> None:
        """Öffnet die Übersicht der gesammelten Bewertungen."""
        BewertungsFenster(
            eltern=self.fenster, speicher=self.bewertungen, theme=self.theme
        ).zeige_modal()

    def _bewertung_speichern(self, frage: str, antwort: str, wert: int) -> None:
        """Nimmt eine Bewertung aus der Chat-Oberfläche auf."""
        self.bewertungen.fuege_hinzu(
            frage=frage, antwort=antwort, bewertung=wert,
            modell=self.konfiguration.get("model", {}).get("name", "unbekannt"),
            markierungen=[self.benutzer] if self.benutzer else [],
        )

    # ------------------------------------------------------------------ Modell
    def _lade_modell_im_hintergrund(self) -> None:
        """Lädt das Sprachmodell in einem eigenen Thread."""

        def arbeite() -> None:
            """Importiert und initialisiert das Modell."""
            try:
                from llm_engine import ToolAugmentedLLM

                llm = ToolAugmentedLLM(config=self.konfiguration)
                llm.load_model()
            except Exception as fehler:
                meldung = str(fehler)
                self.protokoll.error(f"Modell konnte nicht geladen werden: {meldung}")
                self.fenster.after(0, lambda: self._modell_fehlt(meldung))
                return
            self.fenster.after(0, lambda: self._modell_bereit(llm))

        threading.Thread(target=arbeite, daemon=True).start()

    def _modell_bereit(self, llm: Any) -> None:
        """Übernimmt das geladene Modell und richtet Schwarm und Ziel-Modus ein."""
        self.llm = llm
        self.llm_fehler = None
        try:
            from schwarm import SchwarmOrchester

            self.schwarm = SchwarmOrchester(llm=self.llm, server=self.server)
        except Exception as fehler:  # Schwarm ist optional, nicht fatal
            self.protokoll.warning(f"Schwarm konnte nicht erzeugt werden: {fehler}")
            self.schwarm = None
        try:
            from ziel_modus import ZielModus

            self.ziel_modus = ZielModus(llm=self.llm, server=self.server)
        except Exception as fehler:  # Ziel-Modus ist optional, nicht fatal
            self.protokoll.warning(f"Ziel-Modus konnte nicht erzeugt werden: {fehler}")
            self.ziel_modus = None
        self.chat.setze_modell_name(getattr(llm, "model_name", "Modell"))
        self.chat.setze_bereit(True, "Bereit")
        self.chat.zeige_systemmeldung("Modell geladen.", "erfolg")
        if self.ziel_aktiv and self.ziel_modus is not None:
            self.chat.zeige_systemmeldung(
                "Ziel-Modus ist aktiv: arbeitet bis zum Ziel.", "info"
            )
        elif self.schwarm_aktiv and self.schwarm is not None:
            self.chat.zeige_systemmeldung(
                "Schwarm ist aktiv: mehrere Agenten bearbeiten jede Frage.", "info"
            )

    def _modell_fehlt(self, meldung: str) -> None:
        """Meldet, dass kein Modell verfügbar ist."""
        self.llm = None
        self.llm_fehler = meldung
        self.chat.setze_bereit(True, "Kein Modell geladen")
        self.chat.zeige_status("Kein Modell geladen", "warnung")
        self.chat.zeige_systemmeldung(
            "Das Sprachmodell ist nicht verfügbar: " + meldung, "warnung"
        )

    # ---------------------------------------------------------------- Antworten
    def _schwarm_status(self, meldung: str) -> None:
        """Zeigt den Fortschritt des Schwarms im Chat an (thread-sicher)."""
        # Der Schwarm läuft in einem Hintergrundthread; Tkinter darf nur
        # vom Hauptthread aus geändert werden.
        try:
            self.fenster.after(0, lambda m=meldung: self.chat.zeige_status(m, "info"))
        except Exception:
            pass

    def _beantworte(
        self,
        frage: str,
        verlauf: List[Dict[str, str]],
        melde_teilstueck: Callable[[str], None],
        abbruch: threading.Event,
    ) -> Dict[str, Any]:
        """Erzeugt die Antwort des Assistenten für die Chat-Oberfläche."""
        if self.llm is None:
            grund = self.llm_fehler or "Es ist kein Sprachmodell geladen."
            raise RuntimeError(
                "Antwort nicht möglich – " + grund
                + "\nBitte torch und transformers installieren "
                  "(siehe INSTALL.md) und die Anwendung neu starten."
            )

        if self.ziel_aktiv and self.ziel_modus is not None:
            # Ziel-Modus hat Vorrang: autonomes Arbeiten bis zum Ziel.
            ergebnis = self.ziel_modus.arbeite_bis_ziel(
                frage,
                verlauf=verlauf,
                teilstueck_rueckmeldung=melde_teilstueck,
                abbruch=abbruch,
                status_rueckmeldung=self._schwarm_status,
            )
            werkzeuge = [
                getattr(aufruf, "tool_name", str(aufruf))
                for aufruf in ergebnis.get("tool_calls", [])
            ]
            erreicht = ergebnis.get("ziel_erreicht", False)
            vorspann = (
                "Ziel erreicht." if erreicht
                else "Ziel nicht sicher erreicht."
            )
            antwort_text = ergebnis.get("response", "")
            return {
                "antwort": f"{vorspann} ({ergebnis.get('versuche', 0)} Versuche)\n\n{antwort_text}",
                "werkzeuge": werkzeuge,
            }

        if self.schwarm_aktiv and self.schwarm is not None:
            # Schwarm: mehrere Agenten und Subagents lösen die Aufgabe.
            ergebnis = self.schwarm.beantworte(
                frage,
                verlauf=verlauf,
                teilstueck_rueckmeldung=melde_teilstueck,
                abbruch=abbruch,
                status_rueckmeldung=self._schwarm_status,
            )
            werkzeuge = [
                getattr(aufruf, "tool_name", str(aufruf))
                for aufruf in ergebnis.get("tool_calls", [])
            ]
            return {"antwort": ergebnis.get("response", ""), "werkzeuge": werkzeuge}

        ergebnis = self.llm.chat_with_tools(
            frage,
            self.client,
            conversation_history=verlauf,
            teilstueck_rueckmeldung=melde_teilstueck,
            abbruch=abbruch,
        )
        werkzeuge = [
            getattr(aufruf, "tool_name", str(aufruf))
            for aufruf in ergebnis.get("tool_calls", [])
        ]
        return {"antwort": ergebnis.get("response", ""), "werkzeuge": werkzeuge}

    # ----------------------------------------------------------------- Schließen
    def _beim_schliessen(self) -> None:
        """Speichert die Fenstergröße und beendet die Anwendung."""
        try:
            self.chat.abbrechen()
        except Exception:
            pass
        try:
            self.einstellungen.setze_fenstergroesse(
                self.fenster.winfo_width(), self.fenster.winfo_height()
            )
        except Exception:
            pass
        if self.dashboard is not None:
            try:
                self.dashboard.schliessen()
            except Exception:
                pass
        self.fenster.destroy()

    def starte(self) -> None:
        """Startet die Ereignisschleife."""
        self.fenster.mainloop()


def run_gui() -> None:
    """Startet die Desktop-Oberfläche (Einstiegspunkt für main.py)."""
    ChatFenster().starte()


# Rückwärtskompatibler Name für älteren Code
ChatGUI = ChatFenster


if __name__ == "__main__":
    run_gui()
