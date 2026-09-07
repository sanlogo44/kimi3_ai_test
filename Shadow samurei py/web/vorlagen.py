"""Seitenvorlagen der Weboberfläche – geschrieben in reinem Python.

Statt Vorlagendateien erzeugen diese Funktionen den HTML-Text als
Zeichenkette. Alle Werte, die aus Daten stammen, laufen über ``sicher``
und werden maskiert. Nur bewusst als ``RohHtml`` gekennzeichneter Text
wird unverändert eingesetzt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ------------------------------------------------------------------ Typen

@dataclass
class Schalter:
    """Die vier globalen Schalter der Verwaltung."""

    bewertungsmodus: bool = False
    zeige_diagramm: bool = True
    schicht_training: bool = False
    auto_benchmarks: bool = False


@dataclass
class Checkpoint:
    """Ein gespeicherter Modellstand."""

    kennung: str = ""
    name: str = ""
    genauigkeit: float | None = None
    gespeichert_am: str = ""


@dataclass
class Metrik:
    """Ein einzelner Metrik-Eintrag eines Trainingslaufs."""

    zeitstempel: str = ""
    modell: str = ""
    genauigkeit: float = 0.0
    verlust: float = 0.0
    trainingszeit: float = 0.0
    tokens: int = 0
    epochen: int = 0


@dataclass
class Zusammenfassung:
    """Zusammenfassung über alle Metrik-Einträge."""

    anzahl: int = 0
    beste_genauigkeit: float = 0.0
    tokens_gesamt: int = 0


@dataclass
class Adressen:
    """Die Adressen, auf die die Navigation und die Formulare zeigen."""

    training: str = "/"
    verwaltung: str = "/admin"
    anmeldung: str = "/login"
    abmeldung: str = "/logout"
    zugangsdaten: str = "/change-credentials"


# ------------------------------------------------------------- RohHtml

class RohHtml:
    """Zeichenkette, die unverändert in die Seite geschrieben wird."""

    __slots__ = ("_text",)

    def __init__(self, text: str = "") -> None:
        self._text = text

    def als_text(self) -> str:
        return self._text

    def ist_leer(self) -> bool:
        return not self._text

    def __str__(self) -> str:
        return self._text

    def __repr__(self) -> str:
        return f"RohHtml({self._text!r})"


def roh(text: str = "") -> RohHtml:
    """Markiert fertigen HTML-Text als „nicht mehr maskieren“."""
    return RohHtml(text)


def leer() -> RohHtml:
    """Erzeugt einen leeren Baustein."""
    return RohHtml("")


def sicher(wert: str) -> str:
    """Maskiert einen Wert für die Ausgabe in HTML.

    Maskiert werden ``&``, ``<``, ``>``, ``"`` und ``'``.
    """
    ausgabe = []
    for zeichen in wert:
        if zeichen == "&":
            ausgabe.append("&amp;")
        elif zeichen == "<":
            ausgabe.append("&lt;")
        elif zeichen == ">":
            ausgabe.append("&gt;")
        elif zeichen == '"':
            ausgabe.append("&quot;")
        elif zeichen == "'":
            ausgabe.append("&#x27;")
        else:
            ausgabe.append(zeichen)
    return "".join(ausgabe)


def sicher_wahl(wert: str | None) -> str:
    """Maskiert einen wahlweisen Wert; ``None`` wird zu einem Gedankenstrich."""
    if wert is None:
        return "–"
    return sicher(wert)


def wahrheit(wert: bool) -> str:
    """Gibt einen Wahrheitswert als „ja“ oder „nein“ aus."""
    return "ja" if wert else "nein"


def text(wert: str) -> RohHtml:
    """Erzeugt einen maskierten Textknoten."""
    return roh(sicher(wert))


def text_wahl(wert: str | None) -> RohHtml:
    """Erzeugt einen maskierten Textknoten; ``None`` wird zu einem Gedankenstrich."""
    return roh(sicher_wahl(wert))


# ------------------------------------------------------------- Attribute

LEERE_ELEMENTE = ("input", "meta", "br", "hr", "img", "link")


def _attribut_als_text(name: str, wert: Any) -> str | None:
    """Gibt die Textdarstellung eines Attributs zurück oder ``None``."""
    if wert is True:
        return name
    if wert is False or wert is None:
        return None
    if isinstance(wert, str):
        if not wert:
            return None
        return f'{name}="{sicher(wert)}"'
    return f'{name}="{sicher(str(wert))}"'


def _attribute(angaben: list[tuple[str, Any]]) -> str:
    """Baut eine Attributliste für ein HTML-Element."""
    teile = []
    for name, wert in angaben:
        dargestellt = _attribut_als_text(name, wert)
        if dargestellt is not None:
            teile.append(dargestellt)
    if not teile:
        return ""
    return " " + " ".join(teile)


def element(
    marke: str,
    angaben: list[tuple[str, Any]] | None = None,
    inhalt: list[RohHtml] | None = None,
) -> RohHtml:
    """Erzeugt ein HTML-Element mit Attributen und Inhalt."""
    if angaben is None:
        angaben = []
    if inhalt is None:
        inhalt = []
    kopf = f"<{marke}{_attribute(angaben)}>"
    if marke in LEERE_ELEMENTE:
        return roh(kopf)
    ausgabe = [kopf]
    for teil in inhalt:
        ausgabe.append(teil.als_text())
    ausgabe.append(f"</{marke}>")
    return roh("".join(ausgabe))


def verbinde(teile: list[RohHtml], trenner: str = "\n") -> RohHtml:
    """Fügt mehrere Bausteine mit einem Trenner zusammen."""
    return roh(trenner.join(t.als_text() for t in teile))


# ------------------------------------------------------------- Formatierung

def prozent(anteil: float | None, stellen: int = 2) -> str:
    """Formatiert einen Anteil zwischen 0 und 1 als Prozentangabe."""
    if anteil is None:
        return "–"
    try:
        if anteil != anteil:  # NaN
            return "–"
        return f"{anteil * 100.0:.{stellen}f} %"
    except (TypeError, ValueError):
        return "–"


def kommazahl(zahl: float | None, stellen: int = 2, einheit: str = "") -> str:
    """Formatiert eine Zahl mit fester Nachkommastellenzahl."""
    if zahl is None:
        sicherer_wert = 0.0
    else:
        try:
            sicherer_wert = float(zahl)
            if sicherer_wert != sicherer_wert:  # NaN
                return "–"
        except (TypeError, ValueError):
            return "–"
    text = f"{sicherer_wert:.{stellen}f}"
    if einheit:
        return f"{text} {einheit}"
    return text


def zeitpunkt(wert: str) -> str:
    """Wandelt einen ISO-Zeitstempel in eine lesbare Form."""
    if not wert:
        return "–"
    return wert.replace("T", " ")[:19]


# ------------------------------------------------------------- Sammelbausteine

def hinweis(inhalt: str, stufe: str = "info") -> RohHtml:
    """Erzeugt einen farbigen Hinweiskasten."""
    return element(
        "div",
        [("class", f"hinweis hinweis-{stufe}")],
        [text(inhalt)],
    )


def karte(
    titel: str,
    inhalt: list[RohHtml],
    kopf_zusatz: RohHtml | None = None,
    stil: str = "",
) -> RohHtml:
    """Erzeugt eine Karte mit Überschrift und beliebigem Inhalt."""
    kopf = element(
        "div",
        [("class", "card-header")],
        [
            element("span", [("class", "card-title")], [text(titel)]),
            kopf_zusatz if kopf_zusatz is not None else leer(),
        ],
    )
    teile = [kopf] + inhalt
    angaben = [("class", "card")]
    if stil:
        angaben.append(("style", stil))
    return element("div", angaben, teile)


def knopf(
    beschriftung: str,
    klasse: str,
    angaben: list[tuple[str, Any]] | None = None,
) -> RohHtml:
    """Erzeugt eine Schaltfläche.

    Fehlt in ``angaben`` ein ``type``, wird ``type="button"`` ergänzt.
    """
    if angaben is None:
        angaben = []
    alle = [("class", klasse)] + list(angaben)
    if not any(name == "type" for name, _ in angaben):
        alle.append(("type", "button"))
    return element("button", alle, [text(beschriftung)])


def tabelle(spalten: list[str], zeilen: list[list[RohHtml]]) -> RohHtml:
    """Erzeugt eine Tabelle aus Spaltentiteln und Zeileninhalten."""
    kopfzellen = [element("th", [], [text(name)]) for name in spalten]
    kopf = element("thead", [], [element("tr", [], [verbinde(kopfzellen, "")])])
    koerperzeilen = []
    for zeile in zeilen:
        zellen = [element("td", [], [feld]) for feld in zeile]
        koerperzeilen.append(element("tr", [], [verbinde(zellen, "")]))
    koerper = element("tbody", [], [verbinde(koerperzeilen, "\n")])
    return element("table", [], [kopf, koerper])


def leermeldung(inhalt: str) -> RohHtml:
    """Erzeugt den Hinweis „noch keine Daten vorhanden“."""
    return element(
        "p",
        [("style", "color:var(--gedaempft);text-align:center;padding:20px;")],
        [text(inhalt)],
    )


def kachel(anzeigewert: str, beschreibung: str, wert_stil: str = "") -> RohHtml:
    """Erzeugt eine Kennzahlkachel."""
    angaben = [("class", "kennzahl")]
    if wert_stil:
        angaben.append(("style", wert_stil))
    return element(
        "div",
        [("class", "kachel")],
        [
            element("div", angaben, [text(anzeigewert)]),
            element("div", [("class", "kennzahl-text")], [text(beschreibung)]),
        ],
    )


def eingabefeld(
    kennung: str,
    beschriftung: str,
    typ: str,
    hinweistext: str | None = None,
    angaben: list[tuple[str, Any]] | None = None,
) -> RohHtml:
    """Erzeugt ein beschriftetes Eingabefeld."""
    if angaben is None:
        angaben = []
    feldname = kennung
    for name, wert in angaben:
        if name == "name" and isinstance(wert, str):
            feldname = wert
            break
    alle = [
        ("type", typ),
        ("id", kennung),
        ("name", feldname),
    ]
    for name, wert in angaben:
        if name != "name":
            alle.append((name, wert))
    fusszeile = leer()
    if hinweistext and hinweistext:
        fusszeile = element(
            "p",
            [("style", "color:var(--gedaempft);font-size:0.82rem;margin-top:6px;")],
            [text(hinweistext)],
        )
    return element(
        "div",
        [("class", "form-group")],
        [
            element("label", [("for", kennung)], [text(beschriftung)]),
            element("input", alle, []),
            fusszeile,
        ],
    )


def schieber(kennung: str, aktiv: bool = False) -> RohHtml:
    """Erzeugt einen Schiebeschalter."""
    return element(
        "label",
        [("class", "schalter")],
        [
            element(
                "input",
                [
                    ("type", "checkbox"),
                    ("id", kennung),
                    ("checked", aktiv),
                ],
                [],
            ),
            element("span", [("class", "regler")], []),
        ],
    )


def schalterzeile(
    kennung: str,
    titel: str,
    beschreibung: str,
    aktiv: bool = False,
) -> RohHtml:
    """Erzeugt eine Zeile aus Titel, Beschreibung und Schiebeschalter."""
    return element(
        "div",
        [("style", "display:flex;justify-content:space-between;align-items:center;gap:12px;")],
        [
            element(
                "div",
                [],
                [
                    element("strong", [], [text(titel)]),
                    element(
                        "p",
                        [("style", "color:var(--gedaempft);font-size:0.85rem;")],
                        [text(beschreibung)],
                    ),
                ],
            ),
            schieber(kennung, aktiv),
        ],
    )


def auswahlkasten(
    kastenwert: str,
    beschriftung: str,
    name: str | None = None,
) -> RohHtml:
    """Erzeugt ein Ankreuzfeld mit Beschriftung."""
    namensangabe = name if name else False
    return element(
        "label",
        [("class", "auswahl")],
        [
            element(
                "input",
                [
                    ("type", "checkbox"),
                    ("value", kastenwert),
                    ("name", namensangabe),
                ],
                [],
            ),
            roh(f" {sicher(beschriftung)}"),
        ],
    )


# ------------------------------------------------------------- Grundgerüst

STILANGABEN = """
        /* Farbwerte für den Dunkelmodus (Standard) */
        :root,
        html[data-erscheinungsbild="dunkel"] {
            --hintergrund: #1c1a17;
            --flaeche: #26241f;
            --text: #f2efe9;
            --gedaempft: #a8a29a;
            --akzent: #c96442;
            --akzent-hover: #b5563a;
            --gefahr: #ef4444;
            --erfolg: #22c55e;
            --warnung: #f59e0b;
            --rahmen: #3a3630;
            --radius: 12px;
            --schatten: 0 4px 10px -2px rgba(0, 0, 0, 0.45);
        }
        /* Farbwerte für den Hellmodus */
        html[data-erscheinungsbild="hell"] {
            --hintergrund: #f7f5f2;
            --flaeche: #ffffff;
            --text: #24211d;
            --gedaempft: #6f6a62;
            --akzent: #c96442;
            --akzent-hover: #b5563a;
            --gefahr: #dc2626;
            --erfolg: #15803d;
            --warnung: #b45309;
            --rahmen: #e3ded6;
            --schatten: 0 4px 10px -4px rgba(0, 0, 0, 0.18);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, sans-serif;
            background: var(--hintergrund);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.5;
        }
        a { color: var(--akzent); text-decoration: none; }
        a:hover { text-decoration: underline; }
        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
        .card {
            background: var(--flaeche);
            border: 1px solid var(--rahmen);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: var(--schatten);
            margin-bottom: 20px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--rahmen);
        }
        .card-title { font-size: 1.2rem; font-weight: 600; }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 18px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.15s;
            color: #ffffff;
        }
        .btn[disabled] { opacity: 0.6; cursor: not-allowed; }
        .btn-primaer { background: var(--akzent); }
        .btn-primaer:hover { background: var(--akzent-hover); }
        .btn-gefahr { background: var(--gefahr); }
        .btn-erfolg { background: var(--erfolg); }
        .btn-klein { padding: 6px 12px; font-size: 0.85rem; }
        .btn-neben {
            background: transparent;
            color: var(--text);
            border: 1px solid var(--rahmen);
        }
        .form-group { margin-bottom: 16px; }
        label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            color: var(--gedaempft);
            font-size: 0.9rem;
        }
        input[type="text"], input[type="password"], input[type="number"], select {
            width: 100%;
            padding: 10px 14px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 8px;
            color: var(--text);
            font-size: 1rem;
        }
        input:focus, select:focus { outline: none; border-color: var(--akzent); }
        .hinweis {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 0.95rem;
            border: 1px solid var(--rahmen);
        }
        .hinweis-fehler { background: rgba(239, 68, 68, 0.14); color: var(--gefahr); }
        .hinweis-erfolg { background: rgba(34, 197, 94, 0.14); color: var(--erfolg); }
        .hinweis-info { background: rgba(201, 100, 66, 0.14); color: var(--akzent); }
        .hinweis-warnung { background: rgba(245, 158, 11, 0.14); color: var(--warnung); }
        .raster-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .raster-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        @media (max-width: 768px) {
            .raster-2, .raster-3 { grid-template-columns: 1fr; }
            .container { padding: 16px; }
        }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--rahmen); }
        th {
            color: var(--gedaempft);
            font-weight: 600;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .marke {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid var(--rahmen);
        }
        .marke-gruen { background: rgba(34, 197, 94, 0.18); color: var(--erfolg); }
        .marke-rot { background: rgba(239, 68, 68, 0.18); color: var(--gefahr); }
        .marke-akzent { background: rgba(201, 100, 66, 0.18); color: var(--akzent); }
        .schalter { position: relative; display: inline-block; width: 48px; height: 26px; }
        .schalter input { opacity: 0; width: 0; height: 0; }
        .regler {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background: var(--rahmen);
            border-radius: 26px;
            transition: 0.25s;
        }
        .regler:before {
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 3px;
            bottom: 3px;
            background: #ffffff;
            border-radius: 50%;
            transition: 0.25s;
        }
        input:checked + .regler { background: var(--akzent); }
        input:checked + .regler:before { transform: translateX(22px); }
        .navigation {
            display: flex;
            gap: 16px;
            padding: 16px 24px;
            background: var(--flaeche);
            border-bottom: 1px solid var(--rahmen);
            align-items: center;
        }
        .nav-marke { font-weight: 700; font-size: 1.1rem; color: var(--akzent); }
        .nav-abstand { flex: 1; }
        .nav-benutzer { color: var(--gedaempft); font-size: 0.9rem; }
        .kennzahl { font-size: 1.5rem; font-weight: 700; }
        .kennzahl-text { font-size: 0.85rem; color: var(--gedaempft); }
        .kachel {
            text-align: center;
            padding: 16px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 8px;
        }
        .fortschritt {
            height: 8px;
            background: var(--rahmen);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .fortschritt-fuellung {
            height: 100%;
            background: var(--akzent);
            border-radius: 4px;
            transition: width 0.3s;
        }
        .auswahlgruppe { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
        .auswahl {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 8px;
            cursor: pointer;
            user-select: none;
        }
        .auswahl input { accent-color: var(--akzent); }
        .balken-reihe { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
        .balken-spur {
            flex: 1;
            height: 14px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 7px;
            overflow: hidden;
        }
        .balken-wert { height: 100%; background: var(--akzent); }
        .balken-text { width: 150px; font-size: 0.85rem; color: var(--gedaempft); }
"""

GRUNDSKRIPT = """
    // Erscheinungsbild (hell/dunkel) wird im Browser gespeichert.
    function setzeErscheinungsbild(modus) {
        document.documentElement.setAttribute('data-erscheinungsbild', modus);
        localStorage.setItem('shadow-erscheinungsbild', modus);
        const knopf = document.getElementById('erscheinungsbild-knopf');
        if (knopf) {
            knopf.textContent = modus === 'dunkel' ? 'Hell' : 'Dunkel';
        }
    }

    function wechsleErscheinungsbild() {
        const aktuell = document.documentElement.getAttribute('data-erscheinungsbild');
        setzeErscheinungsbild(aktuell === 'dunkel' ? 'hell' : 'dunkel');
    }

    setzeErscheinungsbild(localStorage.getItem('shadow-erscheinungsbild') || 'dunkel');

    // Hilfsfunktion für alle Seiten: JSON an eine Schnittstelle senden.
    async function sendeJson(adresse, inhalt = {}) {
        const antwort = await fetch(adresse, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(inhalt),
        });
        const daten = await antwort.json();
        if (daten.fehler) {
            throw new Error(daten.fehler);
        }
        return daten;
    }
"""


def erscheinungsbild_knopf() -> RohHtml:
    """Erzeugt die Schaltfläche zum Wechsel zwischen Hell und Dunkel."""
    return element(
        "button",
        [
            ("class", "btn btn-klein btn-neben"),
            ("id", "erscheinungsbild-knopf"),
            ("type", "button"),
            ("onclick", "wechsleErscheinungsbild()"),
        ],
        [text("Hell")],
    )


def navigation(benutzer: str, adressen: Adressen) -> RohHtml:
    """Erzeugt die Navigationsleiste für angemeldete Administratoren."""
    return element(
        "nav",
        [("class", "navigation")],
        [
            element("div", [("class", "nav-marke")], [text("Shadow")]),
            element("a", [("href", adressen.training)], [text("Training")]),
            element("a", [("href", adressen.verwaltung)], [text("Verwaltung")]),
            element("div", [("class", "nav-abstand")], []),
            element("span", [("class", "nav-benutzer")], [text(benutzer)]),
            erscheinungsbild_knopf(),
            element(
                "a",
                [
                    ("href", adressen.abmeldung),
                    ("style", "font-size:0.9rem;"),
                ],
                [text("Abmelden")],
            ),
        ],
    )


def seite(
    titel: str,
    inhalt: list[RohHtml],
    skript: str = "",
    ist_admin: bool = False,
    benutzer: str = "",
    adressen: Adressen | None = None,
) -> str:
    """Baut eine vollständige HTML-Seite."""
    if adressen is None:
        adressen = Adressen()
    if ist_admin:
        kopfleiste = navigation(benutzer, adressen)
    else:
        kopfleiste = element(
            "div",
            [("style", "position:fixed;top:16px;right:16px;")],
            [erscheinungsbild_knopf()],
        )
    seitenskript = leer() if skript.strip() == "" else element("script", [], [roh(skript)])
    dokument = element(
        "html",
        [
            ("lang", "de"),
            ("data-erscheinungsbild", "dunkel"),
        ],
        [
            element(
                "head",
                [],
                [
                    element("meta", [("charset", "UTF-8")], []),
                    element(
                        "meta",
                        [
                            ("name", "viewport"),
                            ("content", "width=device-width, initial-scale=1.0"),
                        ],
                        [],
                    ),
                    element("title", [], [text(titel)]),
                    element("style", [], [roh(STILANGABEN)]),
                ],
            ),
            element(
                "body",
                [],
                [
                    kopfleiste,
                    element(
                        "div",
                        [("class", "container")],
                        [verbinde(inhalt, "\n")],
                    ),
                    element("script", [], [roh(GRUNDSKRIPT)]),
                    seitenskript,
                ],
            ),
        ],
    )
    return f"<!DOCTYPE html>\n{dokument.als_text()}"


# ------------------------------------------------------------- Anmeldung

def _absenden(beschriftung: str) -> RohHtml:
    """Erzeugt die breite Schaltfläche unter einem Formular."""
    return knopf(
        beschriftung,
        "btn btn-primaer",
        [
            ("type", "submit"),
            ("style", "width:100%;justify-content:center;"),
        ],
    )


def anmeldeseite(fehler: str | None, adressen: Adressen) -> str:
    """Baut die Anmeldeseite."""
    formular = element(
        "form",
        [
            ("method", "POST"),
            ("action", adressen.anmeldung),
        ],
        [
            element(
                "div",
                [
                    ("class", "form-group"),
                    ("style", "text-align:left;"),
                ],
                [
                    element("label", [("for", "username")], [text("Benutzername")]),
                    element(
                        "input",
                        [
                            ("type", "text"),
                            ("id", "username"),
                            ("name", "username"),
                            ("required", True),
                            ("autofocus", True),
                            ("autocomplete", "username"),
                        ],
                        [],
                    ),
                ],
            ),
            element(
                "div",
                [
                    ("class", "form-group"),
                    ("style", "text-align:left;"),
                ],
                [
                    element("label", [("for", "password")], [text("Passwort")]),
                    element(
                        "input",
                        [
                            ("type", "password"),
                            ("id", "password"),
                            ("name", "password"),
                            ("required", True),
                            ("autocomplete", "current-password"),
                        ],
                        [],
                    ),
                ],
            ),
            _absenden("Anmelden"),
        ],
    )
    kasten = element(
        "div",
        [("class", "card"), ("style", "text-align:center;")],
        [
            element(
                "h1",
                [("style", "margin-bottom:4px;color:var(--akzent);")],
                [text("Shadow")],
            ),
            element(
                "p",
                [("style", "color:var(--gedaempft);margin-bottom:24px;")],
                [text("Verwaltungsbereich")],
            ),
            hinweis(fehler, "fehler") if fehler else leer(),
            formular,
            element(
                "p",
                [
                    (
                        "style",
                        "color:var(--gedaempft);font-size:0.82rem;margin-top:16px;",
                    )
                ],
                [
                    roh(
                        "Beim ersten Start gilt das Standardkonto aus der Datei "
                        "<code>config.yaml</code>. Das Passwort muss danach geändert werden."
                    )
                ],
            ),
        ],
    )
    return seite(
        "Anmeldung – Shadow",
        [
            element(
                "div",
                [("style", "max-width:420px;margin:80px auto;")],
                [kasten],
            )
        ],
        "",
        False,
        "",
        adressen,
    )


def zugangsdatenseite(
    benutzer: str,
    meldung: str | None,
    erzwungen: bool,
    adressen: Adressen,
) -> str:
    """Baut die Seite zum Ändern von Benutzername und Passwort."""
    formular = element(
        "form",
        [
            ("method", "POST"),
            ("action", adressen.zugangsdaten),
        ],
        [
            eingabefeld(
                "username",
                "Neuer Benutzername",
                "text",
                None,
                [
                    ("value", benutzer),
                    ("required", True),
                    ("autocomplete", "username"),
                ],
            ),
            eingabefeld(
                "password",
                "Neues Passwort",
                "password",
                None,
                [
                    ("required", True),
                    ("placeholder", "Mindestens 4 Zeichen"),
                    ("autocomplete", "new-password"),
                ],
            ),
            eingabefeld(
                "password2",
                "Passwort wiederholen",
                "password",
                None,
                [
                    ("required", True),
                    ("autocomplete", "new-password"),
                ],
            ),
            _absenden("Speichern"),
        ],
    )
    kasten = element(
        "div",
        [("class", "card")],
        [
            element(
                "h2",
                [("style", "margin-bottom:16px;")],
                [text("Zugangsdaten ändern")],
            ),
            (
                hinweis(
                    "Bitte lege bei der ersten Anmeldung eigene Zugangsdaten fest.",
                    "info",
                )
                if erzwungen
                else leer()
            ),
            hinweis(meldung, "fehler") if meldung else leer(),
            formular,
        ],
    )
    return seite(
        "Zugangsdaten ändern – Shadow",
        [
            element(
                "div",
                [("style", "max-width:440px;margin:60px auto;")],
                [kasten],
            )
        ],
        "",
        False,
        benutzer,
        adressen,
    )


# ------------------------------------------------------------- Training

SKRIPT_TRAINING = """
// ------------------------------------------------------------------ Training
document.getElementById('training-formular').addEventListener('submit', async (ereignis) => {
    ereignis.preventDefault();
    const knopf = document.getElementById('training-knopf');
    const status = document.getElementById('training-status');
    const leiste = document.getElementById('fortschritt-leiste');
    const wert = document.getElementById('fortschritt-wert');
    const bereich = document.getElementById('training-ergebnis');
    const meldung = document.getElementById('training-meldung');

    knopf.disabled = true;
    knopf.textContent = 'Training läuft ...';
    status.textContent = 'Läuft';
    status.className = 'marke marke-akzent';
    leiste.style.display = 'block';
    wert.style.width = '10%';
    bereich.style.display = 'none';

    const felder = new FormData(ereignis.target);
    const schichten = Array.from(
        ereignis.target.querySelectorAll('input[name="layers"]:checked')
    ).map((feld) => feld.value);

    try {
        wert.style.width = '50%';
        const daten = await sendeJson('/api/train', {
            epochs: parseInt(felder.get('epochs'), 10),
            lr: parseFloat(felder.get('lr')),
            base_model: felder.get('base_model') || null,
            layers: schichten.length ? schichten : null,
        });
        wert.style.width = '100%';
        meldung.className = 'hinweis hinweis-erfolg';
        meldung.textContent =
            'Training abgeschlossen. Genauigkeit: '
            + (daten.genauigkeit * 100).toFixed(2) + ' % | Dauer: '
            + daten.trainingszeit.toFixed(2) + ' s | Tokens: ' + daten.tokens
            + ' | Schichten: '
            + (Array.isArray(daten.trainierte_schichten)
                ? daten.trainierte_schichten.join(', ')
                : daten.trainierte_schichten);
        bereich.style.display = 'block';
        status.textContent = 'Bereit';
        status.className = 'marke marke-gruen';
        setTimeout(() => location.reload(), 1800);
    } catch (fehler) {
        meldung.className = 'hinweis hinweis-fehler';
        meldung.textContent = fehler.message;
        bereich.style.display = 'block';
        status.textContent = 'Fehler';
        status.className = 'marke marke-rot';
    } finally {
        knopf.disabled = false;
        knopf.textContent = 'Training starten';
    }
});

// --------------------------------------------------------------- Checkpoints
async function speichereCheckpoint() {
    const name = prompt('Name des Checkpoints:');
    if (!name) { return; }
    try {
        await sendeJson('/api/checkpoints', {name: name, genauigkeit: null});
        location.reload();
    } catch (fehler) {
        alert(fehler.message);
    }
}

async function ladeCheckpoint(kennung) {
    try {
        await sendeJson('/api/checkpoints/' + kennung + '/use');
        alert('Checkpoint als Arbeitsmodell geladen.');
    } catch (fehler) {
        alert(fehler.message);
    }
}

async function loescheCheckpoint(kennung) {
    if (!confirm('Checkpoint wirklich löschen?')) { return; }
    try {
        await sendeJson('/api/checkpoints/' + kennung + '/delete');
        location.reload();
    } catch (fehler) {
        alert(fehler.message);
    }
}

// ---------------------------------------------------------------------- SOUP
async function starteSoup() {
    const kennungen = Array.from(
        document.querySelectorAll('#soup-auswahl input:checked')
    ).map((feld) => feld.value);
    const bereich = document.getElementById('soup-ergebnis');
    if (kennungen.length < 2) {
        bereich.innerHTML =
            '<div class="hinweis hinweis-warnung">Bitte mindestens zwei Checkpoints wählen.</div>';
        return;
    }
    bereich.innerHTML = '<p style="color:var(--gedaempft)">SOUP wird erstellt ...</p>';
    try {
        const daten = await sendeJson('/api/train/soup', {checkpoint_ids: kennungen});
        bereich.innerHTML =
            '<div class="hinweis hinweis-erfolg">SOUP erstellt. Genauigkeit: '
            + (daten.genauigkeit * 100).toFixed(2) + ' % | Kennung: '
            + daten.checkpoint_kennung + '</div>';
        setTimeout(() => location.reload(), 2000);
    } catch (fehler) {
        bereich.innerHTML = '<div class="hinweis hinweis-fehler">' + fehler.message + '</div>';
    }
}
"""

SKRIPT_METRIKEN = """
// ------------------------------------------------------------------ Metriken
async function ladeMetriken() {
    const bereich = document.getElementById('metrik-bereich');
    try {
        const antwort = await fetch('/api/metrics');
        const daten = await antwort.json();
        const metriken = daten.metriken || [];
        if (!metriken.length) {
            bereich.innerHTML =
                '<p style="color:var(--gedaempft)">Noch keine Metriken vorhanden.</p>';
            return;
        }
        const letzte = metriken.slice(-8).reverse();
        const zeilen = letzte.map((eintrag) => {
            const anteil = Math.max(0, Math.min(1, eintrag.genauigkeit || 0));
            return '<tr>'
                + '<td>' + (eintrag.zeitstempel || '').replace('T', ' ').slice(0, 16) + '</td>'
                + '<td>' + eintrag.modell + '</td>'
                + '<td><div class="balken-reihe"><div class="balken-spur">'
                + '<div class="balken-wert" style="width:' + (anteil * 100).toFixed(1) + '%"></div>'
                + '</div><span class="balken-text">'
                + (anteil * 100).toFixed(2) + ' %</span></div></td>'
                + '<td>' + (eintrag.verlust || 0).toFixed(4) + '</td>'
                + '<td>' + (eintrag.trainingszeit || 0).toFixed(2) + ' s</td>'
                + '<td>' + eintrag.tokens + '</td>'
                + '</tr>';
        }).join('');
        bereich.innerHTML =
            '<table><thead><tr><th>Zeitpunkt</th><th>Modell</th><th>Genauigkeit</th>'
            + '<th>Verlust</th><th>Dauer</th><th>Tokens</th></tr></thead><tbody>'
            + zeilen + '</tbody></table>';
    } catch (fehler) {
        bereich.innerHTML =
            '<div class="hinweis hinweis-fehler">Metriken konnten nicht geladen werden.</div>';
    }
}

ladeMetriken();
setInterval(ladeMetriken, 5000);
"""


def _checkpoint_auswahl(checkpoints: list[Checkpoint]) -> RohHtml:
    """Erzeugt das Auswahlfeld für den Basis-Checkpoint."""
    eintraege = [element("option", [("value", "")], [text("Ursprungsmodell")])]
    for punkt in checkpoints:
        beschriftung = punkt.name
        if punkt.genauigkeit is not None:
            beschriftung = f"{beschriftung} ({prozent(punkt.genauigkeit, 2)})"
        eintraege.append(
            element(
                "option",
                [("value", punkt.kennung)],
                [text(beschriftung)],
            )
        )
    return element(
        "div",
        [("class", "form-group")],
        [
            element(
                "label",
                [("for", "basis_modell")],
                [text("Basis-Checkpoint (optional)")],
            ),
            element(
                "select",
                [("name", "base_model"), ("id", "basis_modell")],
                [verbinde(eintraege, "")],
            ),
        ],
    )


def _schichtauswahl(schichten: list[str], erlaubt: bool) -> RohHtml:
    """Erzeugt die Ankreuzfelder für einzelne Schichten."""
    if not erlaubt:
        return element(
            "p",
            [("style", "color:var(--gedaempft);font-size:0.85rem;margin-bottom:12px;")],
            [text("Schicht-Training ist in der Verwaltung abgeschaltet.")],
        )
    kaesten = [
        auswahlkasten(schicht, schicht, "layers") for schicht in schichten
    ]
    return element(
        "div",
        [("class", "form-group")],
        [
            element("label", [], [text("Zu trainierende Schichten")]),
            element(
                "div",
                [("class", "auswahlgruppe")],
                [verbinde(kaesten, "\n")],
            ),
            element(
                "p",
                [("style", "color:var(--gedaempft);font-size:0.82rem;margin-top:6px;")],
                [text("Ohne Auswahl werden alle Schichten trainiert.")],
            ),
        ],
    )


def _trainingskarte(
    checkpoints: list[Checkpoint],
    schichten: list[str],
    schicht_training: bool,
) -> RohHtml:
    """Erzeugt die Karte mit dem Trainingsformular."""
    formular = element(
        "form",
        [("id", "training-formular")],
        [
            _checkpoint_auswahl(checkpoints),
            eingabefeld(
                "epochen",
                "Epochen",
                "number",
                None,
                [
                    ("name", "epochs"),
                    ("value", "10"),
                    ("min", "1"),
                    ("max", "1000"),
                ],
            ),
            eingabefeld(
                "lernrate",
                "Lernrate",
                "number",
                None,
                [
                    ("name", "lr"),
                    ("value", "0.01"),
                    ("step", "0.001"),
                    ("min", "0.0001"),
                    ("max", "1"),
                ],
            ),
            _schichtauswahl(schichten, schicht_training),
            knopf(
                "Training starten",
                "btn btn-primaer",
                [("type", "submit"), ("id", "training-knopf")],
            ),
        ],
    )
    return karte(
        "Training starten",
        [
            formular,
            element(
                "div",
                [
                    ("id", "training-ergebnis"),
                    ("style", "margin-top:16px;display:none;"),
                ],
                [
                    element(
                        "div",
                        [
                            ("class", "hinweis hinweis-erfolg"),
                            ("id", "training-meldung"),
                        ],
                        [],
                    )
                ],
            ),
            element(
                "div",
                [
                    ("class", "fortschritt"),
                    ("id", "fortschritt-leiste"),
                    ("style", "display:none;"),
                ],
                [
                    element(
                        "div",
                        [
                            ("class", "fortschritt-fuellung"),
                            ("id", "fortschritt-wert"),
                            ("style", "width:0%"),
                        ],
                        [],
                    )
                ],
            ),
        ],
        element(
            "span",
            [
                ("id", "training-status"),
                ("class", "marke marke-akzent"),
            ],
            [text("Bereit")],
        ),
        "",
    )


def checkpoint_tabelle(
    checkpoints: list[Checkpoint],
    mit_kennung: bool = False,
) -> RohHtml:
    """Erzeugt die Tabelle der gespeicherten Checkpoints."""
    if not checkpoints:
        return leermeldung("Noch keine Checkpoints vorhanden.")
    zeilen: list[list[RohHtml]] = []
    for punkt in checkpoints:
        aktionen = verbinde(
            [
                knopf(
                    "Laden",
                    "btn btn-klein btn-primaer",
                    [("onclick", f"ladeCheckpoint('{punkt.kennung}')")],
                ),
                knopf(
                    "Löschen",
                    "btn btn-klein btn-gefahr",
                    [("onclick", f"loescheCheckpoint('{punkt.kennung}')")],
                ),
            ],
            " ",
        )
        if mit_kennung:
            name_feld = element("code", [], [text(punkt.kennung)])
        else:
            name_feld = element(
                "span",
                [],
                [
                    element("strong", [], [text(punkt.name)]),
                    element("br", [], []),
                    element(
                        "small",
                        [("style", "color:var(--gedaempft)")],
                        [text(punkt.kennung)],
                    ),
                ],
            )
        zeile = [name_feld]
        if mit_kennung:
            zeile.append(text(punkt.name))
        zeile.append(text(prozent(punkt.genauigkeit, 2)))
        zeile.append(
            element(
                "span",
                [("style", "color:var(--gedaempft);font-size:0.85rem;")],
                [text(punkt.gespeichert_am)],
            )
        )
        zeile.append(aktionen)
        zeilen.append(zeile)
    spalten = (
        ["Kennung", "Name", "Genauigkeit", "Gespeichert", "Aktionen"]
        if mit_kennung
        else ["Name", "Genauigkeit", "Datum", "Aktionen"]
    )
    return tabelle(spalten, zeilen)


def _soupkarte(checkpoints: list[Checkpoint]) -> RohHtml:
    """Erzeugt die Karte zum Mitteln mehrerer Modelle."""
    kaesten = [
        auswahlkasten(punkt.kennung, punkt.name, None) for punkt in checkpoints
    ]
    return karte(
        "SOUP – Gewichte mitteln",
        [
            element(
                "p",
                [("style", "color:var(--gedaempft);margin-bottom:12px;")],
                [
                    text(
                        "Wähle mindestens zwei Checkpoints aus. Ihre Gewichte werden "
                        "gemittelt und als neues Modell gespeichert; die Ursprungsmodelle "
                        "bleiben erhalten."
                    )
                ],
            ),
            element(
                "div",
                [("class", "auswahlgruppe"), ("id", "soup-auswahl")],
                [verbinde(kaesten, "\n")],
            ),
            knopf(
                "SOUP erstellen",
                "btn btn-primaer",
                [
                    ("style", "margin-top:12px;"),
                    ("onclick", "starteSoup()"),
                ],
            ),
            element(
                "div",
                [("id", "soup-ergebnis"), ("style", "margin-top:12px;")],
                [],
            ),
        ],
        None,
        "margin-top:20px;",
    )


def trainingsseite(
    schalter: Schalter,
    checkpoints: list[Checkpoint],
    schichten: list[str],
    benutzer: str,
    kern_fehler: str | None,
    adressen: Adressen,
) -> str:
    """Baut die Trainingsseite."""
    bereiche: list[RohHtml] = [
        element(
            "h1",
            [("style", "margin-bottom:20px;")],
            [text("Modell-Training")],
        ),
        hinweis(kern_fehler, "warnung") if kern_fehler else leer(),
        element(
            "div",
            [("class", "raster-2")],
            [
                _trainingskarte(checkpoints, schichten, schalter.schicht_training),
                karte(
                    "Checkpoints",
                    [checkpoint_tabelle(checkpoints, False)],
                    knopf(
                        "Speichern",
                        "btn btn-klein btn-erfolg",
                        [("onclick", "speichereCheckpoint()")],
                    ),
                    "",
                ),
            ],
        ),
        _soupkarte(checkpoints),
    ]
    skript = SKRIPT_TRAINING
    if schalter.zeige_diagramm:
        bereiche.append(
            karte(
                "Metriken",
                [
                    element(
                        "div",
                        [("id", "metrik-bereich")],
                        [
                            element(
                                "p",
                                [("style", "color:var(--gedaempft);")],
                                [text("Metriken werden geladen ...")],
                            )
                        ],
                    )
                ],
                element(
                    "span",
                    [("class", "marke marke-gruen")],
                    [text("Aktualisiert sich")],
                ),
                "margin-top:20px;",
            )
        )
        skript = skript + SKRIPT_METRIKEN
    return seite(
        "Training – Shadow",
        bereiche,
        skript,
        True,
        benutzer,
        adressen,
    )


# ------------------------------------------------------------- Verwaltung

SCHALTER_BESCHREIBUNG: list[tuple[str, str, str]] = [
    (
        "schalter-bewertung",
        "Bewertungsmodus",
        "Erlaubt das Bewerten von Antworten",
    ),
    (
        "schalter-diagramm",
        "Metriken anzeigen",
        "Zeigt Diagramme und Tabellen im Trainingsbereich",
    ),
    (
        "schalter-schichten",
        "Schicht-Training",
        "Erlaubt das gezielte Training einzelner Schichten",
    ),
    (
        "schalter-benchmarks",
        "Automatische Benchmarks",
        "Vergleichsläufe im Hintergrund",
    ),
]

SKRIPT_VERWALTUNG = """
const SCHALTER_FELDER = {
    bewertungsmodus: 'schalter-bewertung',
    zeige_diagramm: 'schalter-diagramm',
    schicht_training: 'schalter-schichten',
    auto_benchmarks: 'schalter-benchmarks',
};

async function aktualisiereSchalter() {
    const status = document.getElementById('schalter-status');
    const inhalt = {};
    Object.entries(SCHALTER_FELDER).forEach(([name, kennung]) => {
        inhalt[name] = document.getElementById(kennung).checked;
    });
    status.textContent = 'Wird gespeichert ...';
    status.style.color = 'var(--gedaempft)';
    try {
        const daten = await sendeJson('/api/toggles', inhalt);
        status.textContent = 'Gespeichert. Benchmarks: '
            + (daten.benchmarks_laeuft ? 'laufen' : 'gestoppt');
        status.style.color = 'var(--erfolg)';
    } catch (fehler) {
        status.textContent = fehler.message;
        status.style.color = 'var(--gefahr)';
        document.getElementById(SCHALTER_FELDER.auto_benchmarks).checked = false;
    }
}

Object.values(SCHALTER_FELDER).forEach((kennung) => {
    document.getElementById(kennung).addEventListener('change', aktualisiereSchalter);
});

async function ladeCheckpoint(kennung) {
    try {
        await sendeJson('/api/checkpoints/' + kennung + '/use');
        alert('Checkpoint als Arbeitsmodell geladen.');
    } catch (fehler) {
        alert(fehler.message);
    }
}

async function loescheCheckpoint(kennung) {
    if (!confirm('Checkpoint wirklich löschen?')) { return; }
    try {
        await sendeJson('/api/checkpoints/' + kennung + '/delete');
        location.reload();
    } catch (fehler) {
        alert(fehler.message);
    }
}
"""


def _schalterkarte(schalter: Schalter) -> RohHtml:
    """Erzeugt die Karte mit den vier globalen Schaltern."""
    werte = [
        schalter.bewertungsmodus,
        schalter.zeige_diagramm,
        schalter.schicht_training,
        schalter.auto_benchmarks,
    ]
    zeilen = [
        schalterzeile(feld, titel, beschreibung, aktiv)
        for (feld, titel, beschreibung), aktiv in zip(SCHALTER_BESCHREIBUNG, werte)
    ]
    return karte(
        "Globale Schalter",
        [
            element(
                "div",
                [("style", "display:flex;flex-direction:column;gap:16px;")],
                [verbinde(zeilen, "\n")],
            ),
            element(
                "div",
                [
                    ("id", "schalter-status"),
                    ("style", "margin-top:12px;font-size:0.9rem;color:var(--gedaempft);"),
                ],
                [],
            ),
        ],
        None,
        "",
    )


def _zustandskarte(
    anzahl_checkpoints: int,
    anzahl_metriken: int,
    benchmarks_aktiv: bool,
    benutzer: str,
    zusammenfassung: Zusammenfassung | None,
) -> RohHtml:
    """Erzeugt die Karte mit dem Systemzustand."""
    kacheln = element(
        "div",
        [("class", "raster-2"), ("style", "gap:16px;")],
        [
            kachel(str(anzahl_checkpoints), "Checkpoints", ""),
            kachel(str(anzahl_metriken), "Metrik-Einträge", ""),
            kachel(
                "Aktiv" if benchmarks_aktiv else "Aus",
                "Benchmarks",
                "",
            ),
            kachel(
                benutzer if benutzer else "–",
                "Angemeldet als",
                "font-size:1.1rem;",
            ),
        ],
    )
    inhalt = [kacheln]
    if zusammenfassung is not None and zusammenfassung.anzahl > 0:
        inhalt.append(
            element(
                "div",
                [("class", "raster-2"), ("style", "gap:16px;margin-top:16px;")],
                [
                    kachel(
                        prozent(zusammenfassung.beste_genauigkeit, 2),
                        "Beste Genauigkeit",
                        "",
                    ),
                    kachel(
                        str(zusammenfassung.tokens_gesamt),
                        "Tokens insgesamt",
                        "",
                    ),
                ],
            )
        )
    return karte("Systemzustand", inhalt, None, "")


def metriktabelle(metriken: list[Metrik]) -> RohHtml:
    """Erzeugt die Tabelle aller Metrik-Einträge, neueste zuerst."""
    if not metriken:
        return leermeldung("Noch keine Metriken vorhanden.")
    zeilen: list[list[RohHtml]] = []
    for eintrag in reversed(metriken):
        zeilen.append(
            [
                text(zeitpunkt(eintrag.zeitstempel)),
                text("–") if not eintrag.modell else text(eintrag.modell),
                text(prozent(eintrag.genauigkeit, 2)),
                text(kommazahl(eintrag.verlust, 4, "")),
                text(kommazahl(eintrag.trainingszeit, 2, "s")),
                text(str(eintrag.tokens)),
                text(str(eintrag.epochen)),
            ]
        )
    return tabelle(
        [
            "Zeitpunkt",
            "Modell",
            "Genauigkeit",
            "Verlust",
            "Dauer",
            "Tokens",
            "Epochen",
        ],
        zeilen,
    )


def verwaltungsseite(
    schalter: Schalter,
    checkpoints: list[Checkpoint],
    metriken: list[Metrik],
    zusammenfassung: Zusammenfassung | None,
    benchmarks_aktiv: bool,
    benutzer: str,
    kern_fehler: str | None,
    adressen: Adressen,
) -> str:
    """Baut die Seite des Verwaltungsbereichs."""
    bereiche = [
        element(
            "h1",
            [("style", "margin-bottom:20px;")],
            [text("Verwaltungsbereich")],
        ),
        hinweis(kern_fehler, "warnung") if kern_fehler else leer(),
        element(
            "div",
            [("class", "raster-2")],
            [
                _schalterkarte(schalter),
                _zustandskarte(
                    len(checkpoints),
                    len(metriken),
                    benchmarks_aktiv,
                    benutzer,
                    zusammenfassung,
                ),
            ],
        ),
        karte(
            "Alle Metriken",
            [metriktabelle(metriken)],
            None,
            "margin-top:20px;",
        ),
        karte(
            "Checkpoint-Verwaltung",
            [checkpoint_tabelle(checkpoints, True)],
            None,
            "margin-top:20px;",
        ),
    ]
    return seite(
        "Verwaltung – Shadow",
        bereiche,
        SKRIPT_VERWALTUNG,
        True,
        benutzer,
        adressen,
    )
