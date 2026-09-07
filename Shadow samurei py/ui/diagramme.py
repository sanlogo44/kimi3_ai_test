"""Matplotlib-Diagramme für die Metrikanzeige.

:class:`DiagrammKarte` bettet eine Matplotlib-Grafik in CustomTkinter ein
und zeichnet sie beim Wechsel zwischen Hell- und Dunkel-Modus neu. Die
Zeichenfunktionen erwarten Einträge vom Typ
``dev_tools.metrics_tracker.MetricEntry``.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

import customtkinter as ctk

from ui.theme import FARBEN, SCHRIFT_TEXT, ThemeVerwaltung

try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    MATPLOTLIB_VERFUEGBAR = True
except Exception:  # pragma: no cover - abhängig von der Installation
    MATPLOTLIB_VERFUEGBAR = False


class DiagrammKarte(ctk.CTkFrame):
    """Rahmen mit Titel und eingebettetem Matplotlib-Diagramm."""

    def __init__(
        self,
        master,
        theme: ThemeVerwaltung,
        titel: str,
        zeichner: Callable[[Any, dict[str, str]], None],
        hoehe: int = 240,
        **kwargs,
    ) -> None:
        kwargs.setdefault("fg_color", FARBEN["flaeche"])
        kwargs.setdefault("corner_radius", 12)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", FARBEN["rahmen"])
        super().__init__(master, **kwargs)
        self.theme = theme
        self.zeichner = zeichner
        self._hoehe = hoehe

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=titel, font=(SCHRIFT_TEXT, 13, "bold"),
            text_color=FARBEN["text"], anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="ew")

        if not MATPLOTLIB_VERFUEGBAR:
            ctk.CTkLabel(
                self,
                text="Matplotlib ist nicht installiert – bitte „pip install matplotlib“.",
                font=(SCHRIFT_TEXT, 12), text_color=FARBEN["text_gedaempft"],
                wraplength=320, justify="left",
            ).grid(row=1, column=0, padx=14, pady=(4, 12), sticky="nsew")
            self.figur = None
            self.leinwand = None
            return

        self.figur = Figure(figsize=(4.6, hoehe / 100), dpi=100)
        self.leinwand = FigureCanvasTkAgg(self.figur, master=self)
        widget = self.leinwand.get_tk_widget()
        widget.configure(highlightthickness=0, bd=0)
        widget.grid(row=1, column=0, padx=10, pady=(2, 10), sticky="nsew")

        theme.registriere_beobachter(lambda _modus: self.zeichne_neu())
        self.zeichne_neu()

    def zeichne_neu(self) -> None:
        """Zeichnet das Diagramm mit den aktuellen Themenfarben neu."""
        if not MATPLOTLIB_VERFUEGBAR or self.figur is None:
            return
        farben = self.theme.diagramm_farben()
        self.figur.clear()
        self.figur.patch.set_facecolor(farben["hintergrund"])
        try:
            self.configure(fg_color=FARBEN["flaeche"], border_color=FARBEN["rahmen"])
            self.leinwand.get_tk_widget().configure(bg=farben["hintergrund"])
        except Exception:
            pass
        try:
            self.zeichner(self.figur, farben)
        except Exception as fehler:  # pragma: no cover - Laufzeitschutz
            achse = self.figur.add_subplot(111)
            _leere_achse(achse, farben, f"Diagramm nicht möglich: {fehler}")
        self.leinwand.draw_idle()


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _stil_achse(achse, farben: dict[str, str], titel: str = "") -> None:
    """Setzt Farben, Gitter und Rahmen einer Achse passend zum Theme."""
    achse.set_facecolor(farben["hintergrund"])
    achse.tick_params(colors=farben["text"], labelsize=8)
    for rand in achse.spines.values():
        rand.set_color(farben["gitter"])
    achse.grid(True, color=farben["gitter"], alpha=0.5, linewidth=0.6)
    achse.set_axisbelow(True)
    if titel:
        achse.set_title(titel, color=farben["text"], fontsize=10)


def _leere_achse(achse, farben: dict[str, str], text: str = "Keine Daten vorhanden") -> None:
    """Zeigt einen Hinweis, wenn keine Daten zur Verfügung stehen."""
    achse.set_facecolor(farben["hintergrund"])
    achse.axis("off")
    achse.text(
        0.5, 0.5, text, ha="center", va="center",
        color=farben["text"], fontsize=10, wrap=True,
    )


def _beschriftungen(eintraege: Sequence[Any], hoechstens: int = 6) -> tuple[list[int], list[str]]:
    """Berechnet gleichmäßig verteilte X-Beschriftungen.

    Sind alle Zeitstempel gleich (z. B. mehrere Läufe in derselben
    Minute), werden stattdessen die Laufnummern angezeigt.
    """
    anzahl = len(eintraege)
    if anzahl == 0:
        return [], []
    schritt = max(1, anzahl // hoechstens)
    stellen = list(range(0, anzahl, schritt))
    zeiten = [getattr(eintraege[i], "kurzzeit", "") for i in stellen]
    if len(set(zeiten)) <= 1 and anzahl > 1:
        return stellen, [f"Lauf {i + 1}" for i in stellen]
    return stellen, zeiten


# ---------------------------------------------------------------------------
# Zeichenfunktionen
# ---------------------------------------------------------------------------
def zeichne_genauigkeit(figur, farben: dict[str, str], eintraege: Sequence[Any]) -> None:
    """Zeichnet Genauigkeit und Verlust über die Läufe."""
    achse = figur.add_subplot(111)
    if not eintraege:
        _leere_achse(achse, farben)
        return

    x = list(range(len(eintraege)))
    genauigkeit = [e.genauigkeit for e in eintraege]
    achse.plot(
        x, genauigkeit, marker="o", markersize=4, linewidth=2,
        color=farben["reihe1"], label="Genauigkeit",
    )
    achse.set_ylabel("Genauigkeit", color=farben["reihe1"], fontsize=9)
    achse.set_ylim(0, max(1.0, max(genauigkeit) * 1.1))
    _stil_achse(achse, farben)

    verlust = [e.verlust for e in eintraege]
    griffe, namen_reihen = achse.get_legend_handles_labels()
    if any(wert > 0 for wert in verlust):
        zweite = achse.twinx()
        linien = zweite.plot(
            x, verlust, marker="s", markersize=3, linewidth=1.6, linestyle="--",
            color=farben["reihe2"], label="Verlust",
        )
        zweite.set_ylabel("Verlust", color=farben["reihe2"], fontsize=9)
        zweite.tick_params(colors=farben["text"], labelsize=8)
        for rand in zweite.spines.values():
            rand.set_color(farben["gitter"])
        griffe += linien
        namen_reihen.append("Verlust")

    stellen, namen = _beschriftungen(eintraege)
    achse.set_xticks(stellen)
    achse.set_xticklabels(namen, rotation=20, ha="right", fontsize=7)
    legende = achse.legend(
        griffe, namen_reihen, loc="lower center", ncol=2, fontsize=8, framealpha=0.15
    )
    for text in legende.get_texts():
        text.set_color(farben["text"])
    figur.tight_layout()


def zeichne_zeit_und_tokens(figur, farben: dict[str, str], eintraege: Sequence[Any]) -> None:
    """Zeichnet Trainingszeit als Balken und Tokens als Linie."""
    achse = figur.add_subplot(111)
    if not eintraege:
        _leere_achse(achse, farben)
        return

    x = list(range(len(eintraege)))
    achse.bar(
        x, [e.trainingszeit for e in eintraege], color=farben["reihe4"],
        alpha=0.85, label="Trainingszeit (s)", width=0.6,
    )
    achse.set_ylabel("Sekunden", color=farben["reihe4"], fontsize=9)
    _stil_achse(achse, farben)

    tokens = [e.tokens for e in eintraege]
    if any(tokens):
        zweite = achse.twinx()
        zweite.plot(
            x, tokens, marker="o", markersize=3, linewidth=1.6,
            color=farben["reihe3"], label="Tokens",
        )
        zweite.set_ylabel("Tokens", color=farben["reihe3"], fontsize=9)
        zweite.tick_params(colors=farben["text"], labelsize=8)
        for rand in zweite.spines.values():
            rand.set_color(farben["gitter"])

    stellen, namen = _beschriftungen(eintraege)
    achse.set_xticks(stellen)
    achse.set_xticklabels(namen, rotation=20, ha="right", fontsize=7)
    figur.tight_layout()


def zeichne_modellvergleich(figur, farben: dict[str, str], vergleich: dict[str, dict[str, float]]) -> None:
    """Zeichnet die durchschnittliche Genauigkeit je Modell als Balken."""
    achse = figur.add_subplot(111)
    if not vergleich:
        _leere_achse(achse, farben)
        return

    namen = list(vergleich.keys())[:8]
    werte = [vergleich[name]["genauigkeit"] for name in namen]
    farbreihe = [farben[f"reihe{i}"] for i in range(1, 6)]
    balken = achse.barh(
        range(len(namen)), werte,
        color=[farbreihe[i % len(farbreihe)] for i in range(len(namen))],
        height=0.6,
    )
    achse.set_yticks(range(len(namen)))
    achse.set_yticklabels(
        [name[:18] for name in namen], fontsize=8, color=farben["text"]
    )
    achse.set_xlim(0, 1.05)
    achse.set_xlabel("Ø Genauigkeit", color=farben["text"], fontsize=9)
    _stil_achse(achse, farben)
    achse.grid(True, axis="x", color=farben["gitter"], alpha=0.5, linewidth=0.6)
    for balkenobjekt, wert in zip(balken, werte):
        achse.text(
            min(wert + 0.02, 0.98), balkenobjekt.get_y() + balkenobjekt.get_height() / 2,
            f"{wert:.1%}", va="center", fontsize=8, color=farben["text"],
        )
    figur.tight_layout()


def zeichne_verlustkurve(figur, farben: dict[str, str], verlauf: Sequence[dict[str, Any]]) -> None:
    """Zeichnet die Verlustkurve eines Trainingslaufs."""
    achse = figur.add_subplot(111)
    if not verlauf:
        _leere_achse(achse, farben, "Noch kein Training in dieser Sitzung")
        return

    epochen = [eintrag.get("epoch", nummer + 1) for nummer, eintrag in enumerate(verlauf)]
    verluste = [eintrag.get("loss", 0.0) for eintrag in verlauf]
    achse.plot(epochen, verluste, linewidth=2, color=farben["reihe1"], label="Verlust")
    achse.fill_between(epochen, verluste, color=farben["reihe1"], alpha=0.15)
    achse.set_xlabel("Epoche", color=farben["text"], fontsize=9)
    achse.set_ylabel("Verlust", color=farben["text"], fontsize=9)
    _stil_achse(achse, farben)

    lernraten = [eintrag.get("lr") for eintrag in verlauf if eintrag.get("lr") is not None]
    if len(lernraten) == len(verlauf) and len(set(lernraten)) > 1:
        zweite = achse.twinx()
        zweite.plot(
            epochen, lernraten, linewidth=1.4, linestyle=":",
            color=farben["reihe2"], label="Lernrate",
        )
        zweite.set_ylabel("Lernrate", color=farben["reihe2"], fontsize=9)
        zweite.tick_params(colors=farben["text"], labelsize=8)
        for rand in zweite.spines.values():
            rand.set_color(farben["gitter"])
    figur.tight_layout()


def zeichne_bewertungsverteilung(figur, farben: dict[str, str], verteilung: dict[str, int]) -> None:
    """Zeichnet die Verteilung der Nutzerbewertungen als Ringdiagramm."""
    achse = figur.add_subplot(111)
    werte = [wert for wert in verteilung.values() if wert]
    if not werte:
        _leere_achse(achse, farben, "Noch keine Bewertungen")
        return

    namen = [name for name, wert in verteilung.items() if wert]
    farbzuordnung = {
        "Hilfreich": farben["reihe3"],
        "Nicht hilfreich": farben["reihe1"],
        "Ohne Bewertung": farben["gitter"],
    }
    _, _, prozente = achse.pie(
        werte,
        labels=namen,
        autopct=lambda anteil: f"{anteil:.0f}%",
        colors=[farbzuordnung.get(name, farben["reihe2"]) for name in namen],
        wedgeprops={"width": 0.45, "edgecolor": farben["hintergrund"]},
        textprops={"fontsize": 8, "color": farben["text"]},
        startangle=90,
    )
    for text in prozente:
        text.set_color(farben["text"])
    achse.set_facecolor(farben["hintergrund"])
    figur.tight_layout()
