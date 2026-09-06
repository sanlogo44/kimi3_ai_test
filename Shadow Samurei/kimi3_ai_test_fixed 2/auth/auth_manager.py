"""Benutzerverwaltung mit CustomTkinter-Oberfläche.

Das Modul stellt zwei Ebenen bereit:

* :class:`AuthManager` – schmale Hülle um ``kimi3_kern.Kontenverwaltung``
  (Anmeldung, Konten, Passwörter), ohne jede Abhängigkeit zur Oberfläche.
* :class:`AuthManagerUI`, :class:`AnmeldeFenster`,
  :class:`PasswortAendernFenster` – CustomTkinter-Fenster, die die Logik
  bedienen und dem gemeinsamen Farbschema der Anwendung folgen.

Die gesamte Datenhaltung (``data/users.json``, Passwort-Hashes, Regeln wie
„der letzte Administrator bleibt erhalten“) liegt im Rust-Kern. Fehlerhafte
Eingaben meldet der Kern als :class:`ValueError` mit fertiger deutscher
Meldung; die Oberfläche zeigt diese Meldungen unverändert an.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable

# Der Rust-Kern liegt im Projektordner, dieses Modul im Unterordner ``auth``.
_PROJEKTORDNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJEKTORDNER not in sys.path:
    sys.path.insert(0, _PROJEKTORDNER)

from kern_modul import kern

try:  # Oberfläche ist optional – die Logik läuft auch ohne Tkinter
    import customtkinter as ctk

    CTK_VERFUEGBAR = True
except Exception:  # pragma: no cover - nur ohne Tkinter relevant
    ctk = None  # type: ignore[assignment]
    CTK_VERFUEGBAR = False

# Rückwärtskompatibler Name
CTk_AVAILABLE = CTK_VERFUEGBAR

DATEN_ORDNER = kern.datenordner()
BENUTZER_DATEI = kern.datendatei("users.json")


def _standardwerte_aus_konfiguration() -> tuple[str, str, bool]:
    """Liest Standardkonto und Passwortzwang aus ``config.yaml``.

    Die Konfiguration wird vom Rust-Kern gelesen; fehlen Angaben, gelten
    dessen eingebaute Werte.
    """
    bereich = kern.lade_konfiguration().get("auth") or {}
    return (
        str(bereich.get("default_user") or "Admin"),
        str(bereich.get("default_password") or "1234"),
        bool(bereich.get("force_password_change", True)),
    )


STANDARD_BENUTZER, STANDARD_PASSWORT, PASSWORTWECHSEL_ERZWINGEN = (
    _standardwerte_aus_konfiguration()
)
#: Kleinste erlaubte Passwortlänge (kommt aus dem Rust-Kern)
MINDESTLAENGE_PASSWORT = kern.MINDESTLAENGE_PASSWORT

#: Anzeigetexte der Rollen
ROLLEN_ANZEIGE = {
    "admin": kern.Kontenverwaltung.rollenname("admin"),
    "user": kern.Kontenverwaltung.rollenname("user"),
}
#: Umkehrung für Auswahlfelder
ANZEIGE_ROLLEN = {anzeige: schluessel for schluessel, anzeige in ROLLEN_ANZEIGE.items()}


class AuthManager:
    """Verwaltet Konten, Anmeldungen und Passwörter über den Rust-Kern.

    Alle Konten stehen in einer JSON-Datei (Standard: ``data/users.json``).
    Die Methoden geben bei Erfolg ``True`` beziehungsweise das Konto zurück
    und lösen bei unzulässigen Eingaben :class:`ValueError` mit deutscher
    Meldung aus.
    """

    def __init__(self, dateipfad: str | None = None) -> None:
        self.dateipfad = dateipfad or BENUTZER_DATEI
        ordner = os.path.dirname(os.path.abspath(self.dateipfad))
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        #: Konten im Rust-Kern
        self.konten = kern.Kontenverwaltung(
            pfad=self.dateipfad,
            standardbenutzer=STANDARD_BENUTZER,
            standardpasswort=STANDARD_PASSWORT,
            wechsel=PASSWORTWECHSEL_ERZWINGEN,
        )

    # ------------------------------------------------------------ Persistenz
    def lade_benutzer(self) -> dict[str, dict[str, Any]]:
        """Lädt alle Konten und legt bei Bedarf das Standardkonto an."""
        return {
            konto["benutzername"]: konto for konto in self.konten.lade_benutzer()
        }

    # -------------------------------------------------------------- Abfragen
    def hole_benutzer(self, benutzername: str) -> dict[str, Any] | None:
        """Gibt ein einzelnes Konto zurück oder ``None``."""
        return self.konten.hole(benutzername)

    def liste_benutzer(self) -> dict[str, dict[str, Any]]:
        """Gibt alle Konten zurück."""
        return self.lade_benutzer()

    def anzahl_benutzer(self) -> int:
        """Gibt die Anzahl der Konten zurück."""
        return self.konten.anzahl()

    def ist_administrator(self, benutzername: str) -> bool:
        """Prüft, ob ein Konto Administratorrechte besitzt."""
        return self.konten.ist_administrator(benutzername)

    def passwortwechsel_faellig(self, benutzername: str) -> bool:
        """Prüft, ob das Passwort geändert werden muss."""
        return self.konten.passwortwechsel_faellig(benutzername)

    # ------------------------------------------------------------- Anmeldung
    def pruefe_anmeldung(self, benutzername: str, passwort: str) -> dict[str, Any] | None:
        """Prüft die Zugangsdaten und liefert das Konto bei Erfolg."""
        return self.konten.pruefe_anmeldung(benutzername, passwort)

    # -------------------------------------------------------- Kontenpflege
    def fuege_benutzer_hinzu(
        self, benutzername: str, passwort: str, rolle: str = "user"
    ) -> bool:
        """Legt ein neues Konto an.

        Löst :class:`ValueError` aus, wenn der Name leer oder schon vergeben
        ist oder das Passwort zu kurz ist.
        """
        self.konten.fuege_benutzer_hinzu(
            benutzername,
            passwort,
            rolle if rolle in ROLLEN_ANZEIGE else "user",
            False,
        )
        return True

    def loesche_benutzer(self, benutzername: str) -> bool:
        """Löscht ein Konto. Das letzte Administratorkonto bleibt erhalten."""
        self.konten.loesche_benutzer(benutzername)
        return True

    def aendere_passwort(self, benutzername: str, neues_passwort: str) -> bool:
        """Setzt ein neues Passwort für ein Konto."""
        self.konten.aendere_passwort(benutzername, neues_passwort, False)
        return True

    def aendere_rolle(self, benutzername: str, rolle: str) -> bool:
        """Ändert die Rolle eines Kontos."""
        if rolle not in ROLLEN_ANZEIGE:
            raise ValueError(f"Die Rolle „{rolle}“ ist unbekannt.")
        self.konten.aendere_rolle(benutzername, rolle)
        return True

    def aendere_zugangsdaten(
        self, alter_benutzer: str, neuer_benutzer: str, neues_passwort: str
    ) -> bool:
        """Ändert Benutzername und Passwort in einem Schritt."""
        self.konten.aendere_zugangsdaten(alter_benutzer, neuer_benutzer, neues_passwort)
        return True

    def markiere_erstanmeldung_erledigt(self, benutzername: str | None = None) -> None:
        """Entfernt die Pflicht zum Passwortwechsel.

        Ohne Namen gilt der Aufruf für alle Konten.
        """
        namen = [benutzername] if benutzername is not None else self.konten.liste()
        for name in namen:
            try:
                self.konten.markiere_erstanmeldung_erledigt(name)
            except (KeyError, ValueError):
                # Unbekannte Konten werden wie bisher stillschweigend übergangen.
                pass

    # ------------------------------------- Rückwärtskompatible Aliasnamen
    authenticate = pruefe_anmeldung
    list_users = liste_benutzer
    add_user = fuege_benutzer_hinzu
    delete_user = loesche_benutzer
    change_password = aendere_passwort
    change_credentials = aendere_zugangsdaten
    mark_first_login_done = markiere_erstanmeldung_erledigt


# ---------------------------------------------------------------------------
# Oberfläche
# ---------------------------------------------------------------------------
def _theme_bausteine():
    """Lädt Farbschema und Hilfswidgets; fällt notfalls auf Standardwerte zurück."""
    try:
        from ui.theme import FARBEN, SCHRIFT_TEXT, hole_theme
        from ui.widgets import Hinweis, akzent_knopf, gefahr_knopf, neben_knopf, zentriere_fenster

        return FARBEN, SCHRIFT_TEXT, hole_theme(), Hinweis, akzent_knopf, neben_knopf, gefahr_knopf, zentriere_fenster
    except Exception:  # pragma: no cover - nur ohne ui-Paket relevant
        return None, "Helvetica", None, None, None, None, None, None


class _ThemenFenster:
    """Gemeinsame Basis: erzeugt ein Fenster im Farbschema der Anwendung."""

    def __init__(self, eltern, titel: str, breite: int, hoehe: int) -> None:
        if not CTK_VERFUEGBAR:
            raise ImportError("CustomTkinter ist nicht installiert.")
        (
            self.FARBEN,
            self.SCHRIFT,
            self.theme,
            self.Hinweis,
            self.akzent_knopf,
            self.neben_knopf,
            self.gefahr_knopf,
            self._zentriere,
        ) = _theme_bausteine()

        if eltern is None:
            self.fenster = ctk.CTk()
            self.eigenstaendig = True
        else:
            self.fenster = ctk.CTkToplevel(eltern)
            self.eigenstaendig = False
            self.fenster.transient(eltern)
        self.fenster.title(titel)
        self.fenster.geometry(f"{breite}x{hoehe}")
        self.fenster.minsize(breite, hoehe)
        if self.FARBEN is not None:
            self.fenster.configure(fg_color=self.FARBEN["fenster"])
        if self._zentriere:
            self._zentriere(self.fenster, breite, hoehe)

    def _farbe(self, name: str, ersatz: str) -> Any:
        """Gibt eine Themenfarbe oder einen Ersatzwert zurück."""
        if self.FARBEN is None:
            return ersatz
        return self.FARBEN.get(name, ersatz)

    def _knopf(self, eltern, text, befehl, art: str = "akzent", **kwargs):
        """Erzeugt einen Knopf – bevorzugt über die Themen-Hilfsfunktionen."""
        erzeuger = {
            "akzent": self.akzent_knopf,
            "neben": self.neben_knopf,
            "gefahr": self.gefahr_knopf,
        }.get(art)
        if erzeuger is not None:
            return erzeuger(eltern, text, befehl, **kwargs)
        return ctk.CTkButton(eltern, text=text, command=befehl, **kwargs)

    def zeige_modal(self) -> None:
        """Zeigt das Fenster modal an."""
        self.fenster.after(120, self.fenster.grab_set)
        if self.eigenstaendig:
            self.fenster.mainloop()
        else:
            self.fenster.wait_window()


class AnmeldeFenster(_ThemenFenster):
    """Anmeldedialog im Erscheinungsbild der Anwendung."""

    def __init__(
        self,
        eltern=None,
        verwaltung: AuthManager | None = None,
        auf_erfolg: Callable[[dict[str, Any]], None] | None = None,
        titel: str = "Anmeldung",
        letzter_benutzer: str = "",
    ) -> None:
        super().__init__(eltern, titel, 420, 420)
        self.verwaltung = verwaltung or AuthManager()
        self.auf_erfolg = auf_erfolg
        self.konto: dict[str, Any] | None = None
        self._baue_oberflaeche(letzter_benutzer)
        self.fenster.protocol("WM_DELETE_WINDOW", self._abbrechen)

    def _baue_oberflaeche(self, letzter_benutzer: str) -> None:
        """Baut Eingabefelder und Knöpfe auf."""
        huelle = ctk.CTkFrame(self.fenster, fg_color="transparent")
        huelle.pack(fill="both", expand=True, padx=34, pady=30)

        ctk.CTkLabel(
            huelle, text="Kimi3", font=(self.SCHRIFT, 26, "bold"),
            text_color=self._farbe("akzent", "#c96442"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            huelle, text="Bitte melde dich an, um fortzufahren.",
            font=(self.SCHRIFT, 12),
            text_color=self._farbe("text_gedaempft", "gray"),
        ).pack(anchor="w", pady=(2, 22))

        ctk.CTkLabel(
            huelle, text="Benutzername", font=(self.SCHRIFT, 12),
            text_color=self._farbe("text", "black"),
        ).pack(anchor="w")
        self.feld_benutzer = ctk.CTkEntry(huelle, height=38, placeholder_text="Benutzername")
        self.feld_benutzer.pack(fill="x", pady=(4, 14))
        if letzter_benutzer:
            self.feld_benutzer.insert(0, letzter_benutzer)

        ctk.CTkLabel(
            huelle, text="Passwort", font=(self.SCHRIFT, 12),
            text_color=self._farbe("text", "black"),
        ).pack(anchor="w")
        self.feld_passwort = ctk.CTkEntry(huelle, height=38, show="*", placeholder_text="Passwort")
        self.feld_passwort.pack(fill="x", pady=(4, 6))

        self.meldung = ctk.CTkLabel(
            huelle, text="", font=(self.SCHRIFT, 12), wraplength=330, justify="left",
            text_color=self._farbe("fehler", "#dc2626"),
        )
        self.meldung.pack(anchor="w", pady=(2, 10))

        self._knopf(huelle, "Anmelden", self._anmelden, "akzent", height=40).pack(fill="x")
        self._knopf(huelle, "Abbrechen", self._abbrechen, "neben", height=36).pack(
            fill="x", pady=(8, 0)
        )

        self.feld_passwort.bind("<Return>", lambda _e: self._anmelden())
        self.feld_benutzer.bind("<Return>", lambda _e: self.feld_passwort.focus_set())
        self.fenster.after(200, self.feld_benutzer.focus_set)

    def _anmelden(self) -> None:
        """Prüft die Eingaben und meldet den Benutzer an."""
        benutzername = self.feld_benutzer.get().strip()
        passwort = self.feld_passwort.get()
        if not benutzername or not passwort:
            self.meldung.configure(text="Bitte Benutzername und Passwort eingeben.")
            return
        konto = self.verwaltung.pruefe_anmeldung(benutzername, passwort)
        if konto is None:
            self.meldung.configure(text="Ungültige Zugangsdaten.")
            self.feld_passwort.delete(0, "end")
            return
        if konto.get("passwortwechsel_faellig"):
            self.meldung.configure(
                text="Bitte lege zuerst ein neues Passwort fest.",
                text_color=self._farbe("warnung", "#d97706"),
            )
            dialog = PasswortAendernFenster(
                self.fenster, self.verwaltung, benutzername, erstanmeldung=True
            )
            dialog.zeige_modal()
            if not dialog.erfolgreich:
                self.meldung.configure(
                    text="Passwortwechsel abgebrochen.",
                    text_color=self._farbe("fehler", "#dc2626"),
                )
                return
            konto = self.verwaltung.hole_benutzer(dialog.neuer_name or benutzername) or konto
        self.konto = konto
        if self.auf_erfolg:
            self.auf_erfolg(konto)
        self.fenster.destroy()

    def _abbrechen(self) -> None:
        """Bricht die Anmeldung ab."""
        self.konto = None
        self.fenster.destroy()


class PasswortAendernFenster(_ThemenFenster):
    """Dialog zum Ändern von Passwort und optional Benutzername."""

    def __init__(
        self,
        eltern,
        verwaltung: AuthManager,
        benutzername: str,
        erstanmeldung: bool = False,
    ) -> None:
        super().__init__(eltern, "Passwort ändern", 420, 440 if erstanmeldung else 380)
        self.verwaltung = verwaltung
        self.benutzername = benutzername
        self.erstanmeldung = erstanmeldung
        self.erfolgreich = False
        self.neuer_name: str | None = None
        self._baue_oberflaeche()

    def _baue_oberflaeche(self) -> None:
        """Baut die Eingabemaske auf."""
        huelle = ctk.CTkFrame(self.fenster, fg_color="transparent")
        huelle.pack(fill="both", expand=True, padx=30, pady=26)

        ctk.CTkLabel(
            huelle, text="Passwort ändern", font=(self.SCHRIFT, 19, "bold"),
            text_color=self._farbe("text", "black"),
        ).pack(anchor="w")
        untertitel = (
            "Beim ersten Anmelden muss ein eigenes Passwort gesetzt werden."
            if self.erstanmeldung
            else f"Neues Passwort für „{self.benutzername}“."
        )
        ctk.CTkLabel(
            huelle, text=untertitel, font=(self.SCHRIFT, 12), wraplength=340,
            justify="left", text_color=self._farbe("text_gedaempft", "gray"),
        ).pack(anchor="w", pady=(2, 18))

        self.feld_name: Any = None
        if self.erstanmeldung:
            ctk.CTkLabel(
                huelle, text="Benutzername", font=(self.SCHRIFT, 12),
                text_color=self._farbe("text", "black"),
            ).pack(anchor="w")
            self.feld_name = ctk.CTkEntry(huelle, height=36)
            self.feld_name.insert(0, self.benutzername)
            self.feld_name.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(
            huelle, text="Neues Passwort", font=(self.SCHRIFT, 12),
            text_color=self._farbe("text", "black"),
        ).pack(anchor="w")
        self.feld_passwort = ctk.CTkEntry(huelle, height=36, show="*")
        self.feld_passwort.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(
            huelle, text="Neues Passwort wiederholen", font=(self.SCHRIFT, 12),
            text_color=self._farbe("text", "black"),
        ).pack(anchor="w")
        self.feld_wiederholung = ctk.CTkEntry(huelle, height=36, show="*")
        self.feld_wiederholung.pack(fill="x", pady=(4, 8))

        self.meldung = ctk.CTkLabel(
            huelle, text="", font=(self.SCHRIFT, 12), wraplength=340, justify="left",
            text_color=self._farbe("fehler", "#dc2626"),
        )
        self.meldung.pack(anchor="w", pady=(0, 10))

        self._knopf(huelle, "Speichern", self._speichern, "akzent", height=38).pack(fill="x")
        if not self.erstanmeldung:
            self._knopf(huelle, "Abbrechen", self.fenster.destroy, "neben", height=34).pack(
                fill="x", pady=(8, 0)
            )
        self.feld_wiederholung.bind("<Return>", lambda _e: self._speichern())
        self.fenster.after(200, self.feld_passwort.focus_set)

    def _speichern(self) -> None:
        """Validiert die Eingaben und speichert das neue Passwort."""
        passwort = self.feld_passwort.get()
        wiederholung = self.feld_wiederholung.get()
        if passwort != wiederholung:
            self.meldung.configure(text="Die Passwörter stimmen nicht überein.")
            return
        if passwort == STANDARD_PASSWORT:
            self.meldung.configure(text="Bitte wähle ein anderes als das Standardpasswort.")
            return

        neuer_name = self.benutzername
        if self.feld_name is not None:
            neuer_name = self.feld_name.get().strip() or self.benutzername

        try:
            if neuer_name != self.benutzername:
                self.verwaltung.aendere_zugangsdaten(
                    self.benutzername, neuer_name, passwort
                )
            else:
                self.verwaltung.aendere_passwort(self.benutzername, passwort)
        except ValueError as fehler:
            # Der Rust-Kern liefert eine fertige deutsche Meldung.
            self.meldung.configure(text=str(fehler))
            return
        self.erfolgreich = True
        self.neuer_name = neuer_name
        self.fenster.destroy()


class AuthManagerUI(_ThemenFenster):
    """Fenster zur Verwaltung aller Konten."""

    def __init__(self, eltern=None, verwaltung: AuthManager | None = None) -> None:
        super().__init__(eltern, "Benutzerverwaltung", 620, 620)
        self.verwaltung = verwaltung or AuthManager()
        self.fenster.grid_columnconfigure(0, weight=1)
        self.fenster.grid_rowconfigure(1, weight=1)
        self._baue_oberflaeche()
        self.aktualisiere_liste()
        if self.theme is not None:
            self.theme.registriere_beobachter(self._theme_gewechselt)

    # Rückwärtskompatibler Name
    @property
    def win(self):
        """Alias für ``self.fenster`` (ältere Aufrufer)."""
        return self.fenster

    def _baue_oberflaeche(self) -> None:
        """Legt Kopfzeile, Reiter und Fußzeile an."""
        kopf = ctk.CTkFrame(self.fenster, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="ew")
        ctk.CTkLabel(
            kopf, text="Benutzerverwaltung", font=(self.SCHRIFT, 20, "bold"),
            text_color=self._farbe("text", "black"),
        ).pack(side="left")
        self.zaehler = ctk.CTkLabel(
            kopf, text="", font=(self.SCHRIFT, 12),
            text_color=self._farbe("text_gedaempft", "gray"),
        )
        self.zaehler.pack(side="right")

        self.reiter = ctk.CTkTabview(
            self.fenster, corner_radius=12,
            fg_color=self._farbe("flaeche", "#ffffff"),
            segmented_button_selected_color=self._farbe("akzent", "#c96442"),
            segmented_button_selected_hover_color=self._farbe("akzent_hover", "#b1553a"),
        )
        self.reiter.grid(row=1, column=0, padx=20, pady=6, sticky="nsew")
        self.reiter_liste = self.reiter.add("Konten")
        self.reiter_neu = self.reiter.add("Neues Konto")
        self._baue_liste()
        self._baue_formular()

        fuss = ctk.CTkFrame(self.fenster, fg_color="transparent")
        fuss.grid(row=2, column=0, padx=20, pady=(6, 18), sticky="ew")
        self._knopf(fuss, "Aktualisieren", self.aktualisiere_liste, "neben", width=130).pack(
            side="left"
        )
        self._knopf(fuss, "Schließen", self.fenster.destroy, "akzent", width=120).pack(
            side="right"
        )

    def _baue_liste(self) -> None:
        """Baut den Reiter mit der Kontenliste."""
        rahmen = self.reiter_liste
        rahmen.grid_columnconfigure(0, weight=1)
        rahmen.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            rahmen, text="Registrierte Konten", font=(self.SCHRIFT, 13, "bold"),
            text_color=self._farbe("text", "black"),
        ).grid(row=0, column=0, padx=6, pady=(8, 4), sticky="w")
        self.liste = ctk.CTkScrollableFrame(
            rahmen, corner_radius=10, fg_color=self._farbe("fenster", "#f5f5f5")
        )
        self.liste.grid(row=1, column=0, padx=4, pady=(0, 8), sticky="nsew")
        self.liste.grid_columnconfigure(0, weight=1)

    def _baue_formular(self) -> None:
        """Baut den Reiter zum Anlegen neuer Konten."""
        rahmen = self.reiter_neu
        rahmen.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            rahmen, text="Neues Konto anlegen", font=(self.SCHRIFT, 15, "bold"),
            text_color=self._farbe("text", "black"),
        ).grid(row=0, column=0, columnspan=2, padx=8, pady=(14, 12), sticky="w")

        def zeile(nummer: int, beschriftung: str, **kwargs):
            ctk.CTkLabel(
                rahmen, text=beschriftung, font=(self.SCHRIFT, 12),
                text_color=self._farbe("text", "black"),
            ).grid(row=nummer, column=0, padx=8, pady=6, sticky="w")
            feld = ctk.CTkEntry(rahmen, height=34, **kwargs)
            feld.grid(row=nummer, column=1, padx=8, pady=6, sticky="ew")
            return feld

        self.feld_name = zeile(1, "Benutzername")
        self.feld_passwort = zeile(2, "Passwort", show="*")
        self.feld_wiederholung = zeile(3, "Passwort wiederholen", show="*")

        ctk.CTkLabel(
            rahmen, text="Rolle", font=(self.SCHRIFT, 12),
            text_color=self._farbe("text", "black"),
        ).grid(row=4, column=0, padx=8, pady=6, sticky="w")
        self.feld_rolle = ctk.CTkComboBox(
            rahmen, values=list(ROLLEN_ANZEIGE.values()), width=170, state="readonly"
        )
        self.feld_rolle.set(ROLLEN_ANZEIGE["user"])
        self.feld_rolle.grid(row=4, column=1, padx=8, pady=6, sticky="w")

        self.formular_meldung = ctk.CTkLabel(
            rahmen, text="", font=(self.SCHRIFT, 12), wraplength=420, justify="left",
            text_color=self._farbe("text_gedaempft", "gray"),
        )
        self.formular_meldung.grid(row=5, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        self._knopf(rahmen, "Konto erstellen", self._konto_erstellen, "akzent", width=170).grid(
            row=6, column=0, columnspan=2, padx=8, pady=(10, 14), sticky="w"
        )
        self.feld_wiederholung.bind("<Return>", lambda _e: self._konto_erstellen())

    # ------------------------------------------------------------- Aktionen
    def aktualisiere_liste(self) -> None:
        """Zeichnet die Kontenliste neu."""
        for kind in self.liste.winfo_children():
            kind.destroy()

        konten = self.verwaltung.liste_benutzer()
        self.zaehler.configure(
            text=f"{len(konten)} Konto" if len(konten) == 1 else f"{len(konten)} Konten"
        )
        if not konten:
            ctk.CTkLabel(
                self.liste, text="Keine Konten vorhanden.", font=(self.SCHRIFT, 12),
                text_color=self._farbe("text_gedaempft", "gray"),
            ).grid(row=0, column=0, pady=20)
            return

        for zeile, (name, konto) in enumerate(sorted(konten.items())):
            self._zeichne_konto(zeile, name, konto)

    def _zeichne_konto(self, zeile: int, name: str, konto: dict[str, Any]) -> None:
        """Zeichnet eine Kontenkarte."""
        karte = ctk.CTkFrame(
            self.liste, corner_radius=10, fg_color=self._farbe("flaeche", "#ffffff"),
            border_width=1, border_color=self._farbe("rahmen", "#e0e0e0"),
        )
        karte.grid(row=zeile, column=0, padx=4, pady=4, sticky="ew")
        karte.grid_columnconfigure(0, weight=1)

        kopf = ctk.CTkFrame(karte, fg_color="transparent")
        kopf.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="ew")
        ctk.CTkLabel(
            kopf, text=name, font=(self.SCHRIFT, 13, "bold"),
            text_color=self._farbe("text", "black"),
        ).pack(side="left")
        rolle = konto.get("rolle", "user")
        ctk.CTkLabel(
            kopf, text=ROLLEN_ANZEIGE.get(rolle, "Benutzer"), font=(self.SCHRIFT, 11, "bold"),
            text_color=self._farbe("akzent" if rolle == "admin" else "info", "#3b82f6"),
        ).pack(side="right")

        letzte = konto.get("letzte_anmeldung") or "noch nie"
        hinweis = f"Angelegt: {str(konto.get('erstellt_am', 'unbekannt'))[:16].replace('T', ' ')}"
        hinweis += f"   ·   Letzte Anmeldung: {str(letzte)[:16].replace('T', ' ')}"
        if konto.get("passwortwechsel_faellig"):
            hinweis += "   ·   Passwortwechsel fällig"
        ctk.CTkLabel(
            karte, text=hinweis, font=(self.SCHRIFT, 11),
            text_color=self._farbe("text_gedaempft", "gray"),
        ).grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

        knopfreihe = ctk.CTkFrame(karte, fg_color="transparent")
        knopfreihe.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")
        self._knopf(
            knopfreihe, "Passwort ändern", lambda n=name: self._passwort_dialog(n),
            "neben", width=140, height=30,
        ).pack(side="left", padx=(0, 6))
        neue_rolle = "user" if rolle == "admin" else "admin"
        self._knopf(
            knopfreihe, f"Zu {ROLLEN_ANZEIGE[neue_rolle]}",
            lambda n=name, r=neue_rolle: self._rolle_wechseln(n, r),
            "neben", width=150, height=30,
        ).pack(side="left", padx=(0, 6))
        self._knopf(
            knopfreihe, "Löschen", lambda n=name: self._konto_loeschen(n),
            "gefahr", width=90, height=30,
        ).pack(side="left")

    def _konto_erstellen(self) -> None:
        """Legt ein Konto anhand des Formulars an."""
        name = self.feld_name.get().strip()
        passwort = self.feld_passwort.get()
        wiederholung = self.feld_wiederholung.get()
        rolle = ANZEIGE_ROLLEN.get(self.feld_rolle.get(), "user")

        def fehler(text: str) -> None:
            self.formular_meldung.configure(
                text=text, text_color=self._farbe("fehler", "#dc2626")
            )

        if not name or not passwort:
            fehler("Benutzername und Passwort sind erforderlich.")
            return
        if passwort != wiederholung:
            fehler("Die Passwörter stimmen nicht überein.")
            return
        try:
            self.verwaltung.fuege_benutzer_hinzu(name, passwort, rolle)
        except ValueError as ursache:
            # Meldung des Rust-Kerns unverändert anzeigen.
            fehler(str(ursache))
            return

        self.formular_meldung.configure(
            text=f"Konto „{name}“ wurde angelegt.",
            text_color=self._farbe("erfolg", "#16a34a"),
        )
        for feld in (self.feld_name, self.feld_passwort, self.feld_wiederholung):
            feld.delete(0, "end")
        self.aktualisiere_liste()

    def _konto_loeschen(self, name: str) -> None:
        """Löscht ein Konto nach Rückfrage."""
        if not self._bestaetige(
            "Konto löschen", f"Soll das Konto „{name}“ wirklich gelöscht werden?"
        ):
            return
        try:
            self.verwaltung.loesche_benutzer(name)
        except ValueError as ursache:
            self._melde(str(ursache))
            return
        self.aktualisiere_liste()

    def _rolle_wechseln(self, name: str, rolle: str) -> None:
        """Wechselt die Rolle eines Kontos."""
        try:
            self.verwaltung.aendere_rolle(name, rolle)
        except ValueError as ursache:
            self._melde(str(ursache))
            return
        self.aktualisiere_liste()

    def _passwort_dialog(self, name: str) -> None:
        """Öffnet den Passwortdialog für ein Konto."""
        dialog = PasswortAendernFenster(self.fenster, self.verwaltung, name)
        dialog.zeige_modal()
        if dialog.erfolgreich:
            self.aktualisiere_liste()

    # ------------------------------------------------------------- Hilfsmittel
    def _bestaetige(self, titel: str, frage: str) -> bool:
        """Zeigt eine Rückfrage und gibt die Antwort zurück."""
        from tkinter import messagebox

        return bool(messagebox.askyesno(titel, frage, parent=self.fenster))

    def _melde(self, text: str) -> None:
        """Zeigt einen Hinweis als Meldungsfenster."""
        from tkinter import messagebox

        messagebox.showinfo("Hinweis", text, parent=self.fenster)

    def _theme_gewechselt(self, _ist_dunkel: bool) -> None:
        """Zeichnet die Liste nach einem Themenwechsel neu."""
        try:
            self.fenster.configure(fg_color=self.FARBEN["fenster"])
            self.aktualisiere_liste()
        except Exception:
            pass


def zeige_anmeldung(
    eltern=None, verwaltung: AuthManager | None = None, letzter_benutzer: str = ""
) -> dict[str, Any] | None:
    """Öffnet den Anmeldedialog und gibt das angemeldete Konto zurück."""
    fenster = AnmeldeFenster(
        eltern, verwaltung or AuthManager(), letzter_benutzer=letzter_benutzer
    )
    fenster.zeige_modal()
    return fenster.konto


if __name__ == "__main__":  # pragma: no cover - manueller Test
    print("Angemeldet als:", zeige_anmeldung())
