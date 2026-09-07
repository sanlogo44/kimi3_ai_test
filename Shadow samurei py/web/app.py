"""Flask-Weboberfläche des Kimi3-Projekts.

Alle Routen, Formularfelder, JSON-Felder, Statuscodes und Meldungen sind
unverändert aus der Rust-Fassung übernommen, damit die Seiten und ihr
JavaScript ohne Anpassung weiterlaufen.

Aufruf: ``python -m web.app --host 127.0.0.1 --port 5000``
"""
from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.parse import unquote_plus

from flask import Flask, Response, request

import kern

from .bruecke import BrueckenFehler
from .sitzung import (
    Sitzung,
    aus_kopfzeile,
    loesch_kopfzeile,
    setz_kopfzeile,
)
from .vorlagen import (
    Adressen,
    anmeldeseite,
    checkpoint_tabelle,
    zugangsdatenseite,
    trainingsseite,
    verwaltungsseite,
)
from .zustand import (
    Zustand,
    checkpoint_fuer_seite,
    metrik_fuer_seite,
    schalter_fuer_seite,
    zusammenfassung_fuer_seite,
)

OHNE_RECHTE = "Nicht angemeldet oder keine Administratorrechte."

app = Flask(__name__)
_zustand: Zustand | None = None


def _zustand_holen() -> Zustand:
    """Gibt den gemeinsamen Zustand zurück."""
    global _zustand
    if _zustand is None:
        _zustand = Zustand()
    return _zustand


def _adressen() -> Adressen:
    """Gibt die Adressen der Routen für die Seitenvorlagen zurück."""
    return Adressen()


# ----------------------------------------------------------------- Hilfen

def _html(inhalt: str) -> Response:
    """Baut eine HTML-Antwort."""
    return Response(inhalt, status=200, content_type="text/html; charset=utf-8")


def _antwort_json(status: int, inhalt: Any) -> Response:
    """Baut eine JSON-Antwort mit Status."""
    from flask import jsonify
    antwort = jsonify(inhalt)
    antwort.status_code = status
    return antwort


def _umleitung(ziel: str) -> Response:
    """Baut eine Umleitung (Status 302)."""
    return Response("", status=302, headers={"Location": ziel})


def _umleitung_mit_sitzung(ziel: str, kopfzeile: str) -> Response:
    """Baut eine Umleitung, die zugleich die Sitzung setzt."""
    return Response(
        "",
        status=302,
        headers={"Location": ziel, "Set-Cookie": kopfzeile},
    )


def _hole_sitzung(zustand: Zustand) -> Sitzung:
    """Liest die Sitzung aus den Kopfzeilen."""
    zeile = request.headers.get("Cookie")
    return aus_kopfzeile(zustand.geheimnis, zeile)


def _pruefe_seite(zustand: Zustand) -> Sitzung | None:
    """Prüft die Administratorrechte für eine Seite.

    Gibt die Sitzung zurück, oder None, wenn eine Umleitung gesendet wurde.
    Der Aufrufer muss im None-Fall die Umleitung selbst senden.
    """
    sitzung = _hole_sitzung(zustand)
    if sitzung.ist_angemeldet():
        return sitzung
    return None


def _pruefe_api(zustand: Zustand) -> Sitzung | Response:
    """Prüft die Administratorrechte für eine Schnittstelle."""
    sitzung = _hole_sitzung(zustand)
    if sitzung.ist_angemeldet():
        return sitzung
    return _antwort_json(401, {"fehler": OHNE_RECHTE})


def _fehler_antwort(fehler: BrueckenFehler) -> Response:
    """Wandelt einen Fehler der Brücke in eine JSON-Antwort um."""
    return _antwort_json(fehler.status, {"fehler": fehler.meldung})


def _json_rumpf() -> dict:
    """Liest einen JSON-Rumpf; ungültige Angaben ergeben ein leeres Wörterbuch."""
    daten = request.get_json(silent=True)
    if isinstance(daten, dict):
        return daten
    return {}


def _formular() -> dict[str, str]:
    """Liest die Felder eines Formulars (application/x-www-form-urlencoded)."""
    return request.form.to_dict()


def _feld(felder: dict[str, str], name: str) -> str:
    """Gibt ein Formularfeld zurück (fehlt es, ist es leer)."""
    return felder.get(name, "")


def _json_zahl(daten: dict, englisch: str, deutsch: str) -> float | None:
    """Liest eine Zahl aus dem JSON-Rumpf, deutsch oder englisch benannt."""
    roh = _rohwert(daten, englisch, deutsch)
    if roh is None:
        return None
    if isinstance(roh, bool):
        return 1.0 if roh else 0.0
    if isinstance(roh, (int, float)):
        return float(roh)
    if isinstance(roh, str):
        try:
            return float(roh.strip())
        except (ValueError, AttributeError):
            return None  # unlesbar
    return None


class _Zahlwunsch:
    """Ergebnis des Zahlenlesens: fehlt, ungültig oder gültig."""

    FEHLT = "fehlt"
    UNGUELTIG = "ungueltig"
    FLIESSKOMMA = "fliesskomma"


def _rohwert(daten: dict, englisch: str, deutsch: str) -> Any:
    """Liest den Rohwert eines deutsch oder englisch benannten Feldes."""
    if englisch in daten:
        return daten[englisch]
    if deutsch in daten:
        return daten[deutsch]
    return None


def _zahlwunsch(daten: dict, englisch: str, deutsch: str) -> tuple[str, float | None]:
    """Deutet einen Rohwert als Fließkommazahl."""
    roh = _rohwert(daten, englisch, deutsch)
    if roh is None:
        return _Zahlwunsch.FEHLT, None
    if isinstance(roh, bool):
        return _Zahlwunsch.FLIESSKOMMA, 1.0 if roh else 0.0
    if isinstance(roh, (int, float)):
        return _Zahlwunsch.FLIESSKOMMA, float(roh)
    if isinstance(roh, str):
        try:
            return _Zahlwunsch.FLIESSKOMMA, float(roh.strip())
        except (ValueError, AttributeError):
            return _Zahlwunsch.UNGUELTIG, None
    return _Zahlwunsch.UNGUELTIG, None


def _ganzzahlwunsch(daten: dict, englisch: str, deutsch: str) -> tuple[str, float | None]:
    """Deutet einen Rohwert als Ganzzahl.

    Texte müssen ganzzahlig sein: ``"2.5"`` gilt als ungültig, ``2.5`` als
    Zahl wird abgeschnitten.
    """
    roh = _rohwert(daten, englisch, deutsch)
    if roh is None:
        return _Zahlwunsch.FEHLT, None
    if isinstance(roh, bool):
        return _Zahlwunsch.FLIESSKOMMA, 1.0 if roh else 0.0
    if isinstance(roh, (int, float)):
        return _Zahlwunsch.FLIESSKOMMA, float(int(roh))
    if isinstance(roh, str):
        try:
            return _Zahlwunsch.FLIESSKOMMA, float(int(roh.strip()))
        except (ValueError, AttributeError):
            return _Zahlwunsch.UNGUELTIG, None
    return _Zahlwunsch.UNGUELTIG, None


def _json_text(daten: dict, englisch: str, deutsch: str) -> str | None:
    """Liest einen Text aus dem JSON-Rumpf, deutsch oder englisch benannt."""
    roh = _rohwert(daten, englisch, deutsch)
    if isinstance(roh, str) and roh:
        return roh
    return None


def _json_liste(daten: dict, englisch: str, deutsch: str) -> list[str]:
    """Liest eine Liste von Texten aus dem JSON-Rumpf."""
    roh = _rohwert(daten, englisch, deutsch)
    if isinstance(roh, list):
        return [
            element if isinstance(element, str) else str(element)
            for element in roh
        ]
    return []


def _checkpoint_liste(zustand: Zustand) -> list[kern.checkpoints.Checkpoint]:
    """Holt die Checkpoint-Liste – über die Brücke, sonst aus den Dateinamen."""
    try:
        daten = zustand.bruecke.rufe("checkpoints", {})
        liste = daten.get("checkpoints", []) if isinstance(daten, dict) else []
        if isinstance(liste, list):
            return [
                kern.checkpoints.Checkpoint.aus_wert(eintrag)
                for eintrag in liste
                if isinstance(eintrag, dict)
            ]
    except BrueckenFehler:
        pass
    return zustand.checkpoints.liste()


# -------------------------------------------------------------- Anmeldung

@app.route("/login", methods=["GET"])
def anmeldung_zeigen() -> Response:
    """Zeigt das Anmeldeformular."""
    return _html(anmeldeseite(None, _adressen()))


@app.route("/login", methods=["POST"])
def anmeldung_pruefen() -> Response:
    """Prüft die Zugangsdaten."""
    zustand = _zustand_holen()
    felder = _formular()
    benutzername = _feld(felder, "username").strip()
    passwort = _feld(felder, "password")
    konto = zustand.konten.pruefe_anmeldung(benutzername, passwort)
    if konto is not None and konto.ist_administrator():
        neue_sitzung = Sitzung(benutzer=konto.benutzername, ist_admin=True)
        kopfzeile = setz_kopfzeile(zustand.geheimnis, neue_sitzung)
        ziel = (
            _adressen().zugangsdaten
            if konto.passwortwechsel_faellig
            else _adressen().training
        )
        return _umleitung_mit_sitzung(ziel, kopfzeile)
    fehler = (
        "Dieses Konto hat keine Administratorrechte."
        if konto is not None
        else "Ungültige Zugangsdaten."
    )
    return _html(anmeldeseite(fehler, _adressen()))


@app.route("/change-credentials", methods=["GET"])
def zugangsdaten_zeigen() -> Response:
    """Zeigt das Formular für neue Zugangsdaten."""
    zustand = _zustand_holen()
    sitzung = _pruefe_seite(zustand)
    if sitzung is None:
        return _umleitung(_adressen().anmeldung)
    benutzer = sitzung.benutzer if sitzung.benutzer else zustand.standardbenutzer
    erzwungen = zustand.konten.passwortwechsel_faellig(benutzer)
    return _html(
        zugangsdatenseite(benutzer, None, erzwungen, _adressen())
    )


@app.route("/change-credentials", methods=["POST"])
def zugangsdaten_aendern() -> Response:
    """Ändert Benutzername und Passwort."""
    zustand = _zustand_holen()
    sitzung = _pruefe_seite(zustand)
    if sitzung is None:
        return _umleitung(_adressen().anmeldung)
    aktueller_benutzer = sitzung.benutzer if sitzung.benutzer else zustand.standardbenutzer
    felder = _formular()
    neuer_benutzer = _feld(felder, "username").strip()
    passwort = _feld(felder, "password")
    wiederholung = _feld(felder, "password2")

    meldung: str | None = None
    if not neuer_benutzer:
        meldung = "Bitte einen Benutzernamen eingeben."
    elif len(passwort) < kern.konten.MINDESTLAENGE_PASSWORT:
        meldung = "Das Passwort muss mindestens 4 Zeichen haben."
    elif passwort != wiederholung:
        meldung = "Die Passwörter stimmen nicht überein."
    else:
        ergebnis = zustand.konten.aendere_zugangsdaten(
            aktueller_benutzer, neuer_benutzer, passwort
        )
        if ergebnis is not None:
            neue_sitzung = Sitzung(benutzer=ergebnis.benutzername, ist_admin=True)
            return _umleitung_mit_sitzung(
                _adressen().training,
                setz_kopfzeile(zustand.geheimnis, neue_sitzung),
            )
        meldung = "Die Zugangsdaten konnten nicht geändert werden."

    erzwungen = zustand.konten.passwortwechsel_faellig(aktueller_benutzer)
    return _html(
        zugangsdatenseite(aktueller_benutzer, meldung, erzwungen, _adressen())
    )


@app.route("/logout", methods=["GET", "POST"])
def abmelden() -> Response:
    """Beendet die Sitzung."""
    return _umleitung_mit_sitzung(_adressen().anmeldung, loesch_kopfzeile())


# ------------------------------------------------------------------ Seiten

@app.route("/", methods=["GET"])
def trainingsseite_route() -> Response:
    """Zeigt die Trainingsoberfläche."""
    zustand = _zustand_holen()
    sitzung = _pruefe_seite(zustand)
    if sitzung is None:
        return _umleitung(_adressen().anmeldung)
    try:
        daten = zustand.bruecke.rufe("schichten", {})
        schichten = _json_liste(daten, "schichten", "layers")
    except BrueckenFehler:
        schichten = []
    punkte = [
        checkpoint_fuer_seite(p) for p in _checkpoint_liste(zustand)
    ]
    kern_fehler = zustand.bruecke.kern_fehler()
    return _html(
        trainingsseite(
            schalter_fuer_seite(zustand.schalter_lesen()),
            punkte,
            schichten,
            sitzung.benutzer,
            kern_fehler,
            _adressen(),
        )
    )


@app.route("/admin", methods=["GET"])
def verwaltungsseite_route() -> Response:
    """Zeigt den Verwaltungsbereich."""
    zustand = _zustand_holen()
    sitzung = _pruefe_seite(zustand)
    if sitzung is None:
        return _umleitung(_adressen().anmeldung)
    punkte = [
        checkpoint_fuer_seite(p) for p in _checkpoint_liste(zustand)
    ]
    metriken = [
        metrik_fuer_seite(e) for e in zustand.metriken.hole_alle()
    ]
    kennzahlen = zusammenfassung_fuer_seite(zustand.metriken.zusammenfassung())
    kern_fehler = zustand.bruecke.kern_fehler()
    return _html(
        verwaltungsseite(
            schalter_fuer_seite(zustand.schalter_lesen()),
            punkte,
            metriken,
            kennzahlen,
            zustand.benchmarks_laeuft_lesen(),
            sitzung.benutzer,
            kern_fehler,
            _adressen(),
        )
    )


# -------------------------------------------------- Schnittstelle: Schalter

def _schalter_antwort(zustand: Zustand) -> Response:
    """Baut die Antwort der Schalter-Schnittstelle."""
    schalter = zustand.schalter_lesen()
    schalter_wert = schalter.als_wert()
    laeuft = zustand.benchmarks_laeuft_lesen()
    return _antwort_json(
        200,
        {
            "schalter": schalter_wert,
            "toggles": schalter_wert,
            "benchmarks_laeuft": laeuft,
            "benchmarks_running": laeuft,
        },
    )


@app.route("/api/toggles", methods=["GET"])
def schalter_lesen() -> Response:
    """Liest die vier Schalter."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    return _schalter_antwort(zustand)


@app.route("/api/toggles", methods=["POST"])
def schalter_setzen() -> Response:
    """Setzt die vier Schalter."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    daten = _json_rumpf()
    zustand.schalter_aktualisieren(daten)
    if "auto_benchmarks" in daten:
        gewuenscht = zustand.auto_benchmarks()
        if gewuenscht:
            try:
                zustand.bruecke.rufe("benchmarks_starten", {})
                zustand.benchmarks_laeuft_setzen(True)
            except BrueckenFehler as fehler:
                # Ohne Modellkern lässt sich der Schalter nicht halten.
                zustand.schalter_aktualisieren({"auto_benchmarks": False})
                zustand.benchmarks_laeuft_setzen(False)
                return _fehler_antwort(fehler)
        else:
            try:
                zustand.bruecke.rufe("benchmarks_stoppen", {})
            except BrueckenFehler:
                pass
            zustand.benchmarks_laeuft_setzen(False)
    return _schalter_antwort(zustand)


# ------------------------------------------------- Schnittstelle: Training

@app.route("/api/train", methods=["POST"])
def training() -> Response:
    """Trainiert eine Kopie des Modells."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    # Ohne Modellkern antwortet die Brücke sofort mit 503
    try:
        zustand.bruecke.rufe("bereit", {})
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    daten = _json_rumpf()
    zahlenfehler = _antwort_json(
        400, {"fehler": "Epochen und Lernrate müssen Zahlen sein."}
    )
    status_epochen, wert_epochen = _ganzzahlwunsch(daten, "epochs", "epochen")
    if status_epochen == _Zahlwunsch.FLIESSKOMMA and wert_epochen is not None:
        import math
        if math.isfinite(wert_epochen):
            epochen_zahl = wert_epochen
        else:
            return zahlenfehler
    elif status_epochen == _Zahlwunsch.FEHLT:
        epochen_zahl = 10.0
    else:
        return zahlenfehler
    status_lr, wert_lr = _zahlwunsch(daten, "lr", "lernrate")
    if status_lr == _Zahlwunsch.FLIESSKOMMA and wert_lr is not None:
        lernrate = wert_lr
    elif status_lr == _Zahlwunsch.FEHLT:
        lernrate = 1e-2
    else:
        return zahlenfehler
    epochen = max(1, int(epochen_zahl))
    basis = _json_text(daten, "base_model", "basis_modell")
    schichten_liste = _json_liste(daten, "layers", "schichten")
    schichten = schichten_liste if schichten_liste else None
    if schichten is not None and not zustand.schalter_lesen().schicht_training:
        return _antwort_json(403, {"fehler": "Schicht-Training ist deaktiviert."})
    anfrage = {
        "epochen": epochen,
        "lernrate": lernrate,
        "basis": basis,
        "schichten": schichten,
    }
    try:
        werte = zustand.bruecke.rufe("trainiere", anfrage)
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    genauigkeit = werte.get("genauigkeit", 0.0) if isinstance(werte, dict) else 0.0
    trainingszeit = werte.get("trainingszeit", 0.0) if isinstance(werte, dict) else 0.0
    tokens = werte.get("tokens", 0) if isinstance(werte, dict) else 0
    verlust = werte.get("verlust", 0.0) if isinstance(werte, dict) else 0.0
    modellname = werte.get("modellname", "unbekannt") if isinstance(werte, dict) else "unbekannt"
    zustand.metriken.fuege_hinzu(
        kern.metriken.Metrik(
            modell=modellname,
            genauigkeit=genauigkeit,
            verlust=verlust,
            tokens=tokens,
            trainingszeit=trainingszeit,
            epochen=epochen,
            markierungen=["web", "training"],
        )
    )
    trainierte_schichten = schichten if schichten is not None else "alle"
    return _antwort_json(
        200,
        {
            "genauigkeit": genauigkeit,
            "accuracy": genauigkeit,
            "trainingszeit": trainingszeit,
            "train_time": trainingszeit,
            "tokens": tokens,
            "verlust": verlust,
            "trainierte_schichten": trainierte_schichten,
            "layers_trained": trainierte_schichten,
        },
    )


@app.route("/api/train/soup", methods=["POST"])
def soup() -> Response:
    """Mittelt mehrere Checkpoints (SOUP-Training)."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        zustand.bruecke.rufe("bereit", {})
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    daten = _json_rumpf()
    kennungen = _json_liste(daten, "checkpoint_ids", "checkpoint_kennungen")
    try:
        werte = zustand.bruecke.rufe("soup", {"kennungen": kennungen})
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    genauigkeit = werte.get("genauigkeit", 0.0) if isinstance(werte, dict) else 0.0
    kennung = werte.get("kennung", "") if isinstance(werte, dict) else ""
    modellname = werte.get("modellname", "soup") if isinstance(werte, dict) else "soup"
    zustand.metriken.fuege_hinzu(
        kern.metriken.Metrik(
            modell=modellname,
            genauigkeit=genauigkeit,
            markierungen=["web", "soup"],
        )
    )
    return _antwort_json(
        200,
        {
            "genauigkeit": genauigkeit,
            "accuracy": genauigkeit,
            "checkpoint_kennung": kennung,
            "checkpoint_id": kennung,
        },
    )


# ---------------------------------------------- Schnittstelle: Checkpoints

@app.route("/api/checkpoints", methods=["GET"])
def checkpoints_lesen() -> Response:
    """Listet die Checkpoints."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        daten = zustand.bruecke.rufe("checkpoints", {})
        liste = daten.get("checkpoints", []) if isinstance(daten, dict) else []
        return _antwort_json(200, {"checkpoints": liste})
    except BrueckenFehler as fehler:
        # Lesen geht auch ohne PyTorch, nur ohne die Zusatzdaten der Datei.
        liste = [
            punkt.als_wert()
            for punkt in zustand.checkpoints.liste()
        ]
        return _antwort_json(
            200,
            {"checkpoints": liste, "hinweis": fehler.meldung},
        )


@app.route("/api/checkpoints", methods=["POST"])
def checkpoint_speichern() -> Response:
    """Speichert das aktuelle Modell als Checkpoint."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    daten = _json_rumpf()
    name = _json_text(daten, "name", "name") or "checkpoint"
    genauigkeit = _json_zahl(daten, "accuracy", "genauigkeit")
    anfrage = {"name": name, "genauigkeit": genauigkeit}
    try:
        werte = zustand.bruecke.rufe("checkpoint_speichern", anfrage)
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    kennung = werte.get("kennung", None) if isinstance(werte, dict) else None
    return _antwort_json(
        200,
        {"checkpoint_kennung": kennung, "checkpoint_id": kennung},
    )


@app.route("/api/checkpoints/<kennung>/delete", methods=["POST"])
def checkpoint_loeschen(kennung: str) -> Response:
    """Löscht einen Checkpoint."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        werte = zustand.bruecke.rufe("checkpoint_loeschen", {"kennung": kennung})
        geloescht = (
            werte.get("geloescht", False) if isinstance(werte, dict) else False
        )
    except BrueckenFehler:
        # Löschen gelingt auch ohne PyTorch.
        geloescht = zustand.checkpoints.loesche(kennung)
    return _antwort_json(
        200,
        {"geloescht": geloescht, "deleted": geloescht},
    )


@app.route("/api/checkpoints/<kennung>/use", methods=["POST"])
def checkpoint_nutzen(kennung: str) -> Response:
    """Lädt einen Checkpoint als Arbeitskopie."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        werte = zustand.bruecke.rufe("checkpoint_nutzen", {"kennung": kennung})
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    name = werte.get("geladen", "unbekannt") if isinstance(werte, dict) else "unbekannt"
    return _antwort_json(200, {"geladen": name, "loaded": name})


# ----------------------------------------------- Schnittstelle: Bewertung

@app.route("/api/rate", methods=["POST"])
def bewerten() -> Response:
    """Speichert eine Bewertung."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    if not zustand.schalter_lesen().bewertungsmodus:
        return _antwort_json(403, {"fehler": "Bewertungsmodus ist deaktiviert."})
    daten = _json_rumpf()
    punkte = _json_zahl(daten, "score", "bewertung") or 0.0
    antwort_text = _json_text(daten, "answer", "antwort") or ""
    kommentar = _json_text(daten, "comment", "kommentar") or ""
    frage = _json_text(daten, "prompt", "frage") or kommentar
    modell = _json_text(daten, "model", "modell") or "unbekannt"
    eintrag = kern.bewertungen.BewertungsEintrag.neu(
        modell, frage, antwort_text, int(punkte)
    )
    eintrag.markierungen = ["web"]
    zustand.bewertungen.fuege_hinzu(eintrag)
    return _antwort_json(200, {"ok": True})


# ------------------------------------------------ Schnittstelle: Metriken

@app.route("/api/metrics", methods=["GET"])
def metriken_lesen() -> Response:
    """Gibt alle gesammelten Metriken zurück."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    metriken = [
        kern.metriken.Metrik.als_wert(e) for e in zustand.metriken.hole_alle()
    ]
    kennzahlen = zustand.metriken.zusammenfassung()
    aktiv = zustand.schalter_lesen().zeige_diagramm
    # Zusammenfassung als Wörterbuch
    try:
        zusammenfassung_wert = kern.metriken.Zusammenfassung.__dict__
    except Exception:
        zusammenfassung_wert = {}
    # Kern-Zusammenfassung hat öffentliche Felder
    zusammenfassung_dict = {
        "anzahl": kennzahlen.anzahl,
        "beste_genauigkeit": kennzahlen.beste_genauigkeit,
        "durchschnitt_genauigkeit": kennzahlen.durchschnitt_genauigkeit,
        "durchschnitt_verlust": kennzahlen.durchschnitt_verlust,
        "durchschnitt_zeit": kennzahlen.durchschnitt_zeit,
        "tokens_gesamt": kennzahlen.tokens_gesamt,
        "modelle": kennzahlen.modelle,
        "letzter_lauf": kennzahlen.letzter_lauf,
    }
    return _antwort_json(
        200,
        {
            "metriken": metriken,
            "metrics": metriken,
            "zusammenfassung": zusammenfassung_dict,
            "aktiv": aktiv,
            "enabled": aktiv,
        },
    )


# ------------------------------------------------ Schnittstelle: Benchmarks

@app.route("/api/benchmarks", methods=["GET"])
def benchmarks_lesen() -> Response:
    """Gibt die Ergebnisse der Hintergrund-Benchmarks zurück."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        werte = zustand.bruecke.rufe("benchmarks_status", {})
        laeuft = werte.get("laeuft", False) if isinstance(werte, dict) else False
        ergebnisse = werte.get("ergebnisse", []) if isinstance(werte, dict) else []
    except BrueckenFehler:
        laeuft = False
        ergebnisse = []
    zustand.benchmarks_laeuft_setzen(laeuft)
    return _antwort_json(
        200,
        {"laeuft": laeuft, "ergebnisse": ergebnisse},
    )


@app.route("/api/benchmarks/start", methods=["POST"])
def benchmarks_starten() -> Response:
    """Startet die Hintergrund-Benchmarks."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        zustand.bruecke.rufe("benchmarks_starten", {})
        zustand.benchmarks_laeuft_setzen(True)
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    return _antwort_json(200, {"ok": True, "laeuft": True})


@app.route("/api/benchmarks/stop", methods=["POST"])
def benchmarks_stoppen() -> Response:
    """Stoppt die Hintergrund-Benchmarks."""
    zustand = _zustand_holen()
    pruefung = _pruefe_api(zustand)
    if isinstance(pruefung, Response):
        return pruefung
    try:
        zustand.bruecke.rufe("benchmarks_stoppen", {})
    except BrueckenFehler as fehler:
        return _fehler_antwort(fehler)
    zustand.benchmarks_laeuft_setzen(False)
    return _antwort_json(200, {"ok": True, "laeuft": False})


# ------------------------------------------------------------- Start

def starte_server(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Startet den Flask-Server."""
    zustand = _zustand_holen()
    # Wie im früheren starte_server: laufen die Vergleichsläufe
    # automatisch, werden sie beim Start angestoßen.
    if zustand.auto_benchmarks():
        try:
            zustand.bruecke.rufe("benchmarks_starten", {})
            zustand.benchmarks_laeuft_setzen(True)
        except BrueckenFehler as fehler:
            print(f"Hinweis: {fehler.meldung}", file=sys.stderr)

    adresse = f"http://{host}:{port}"
    print(f"Weboberfläche läuft auf {adresse}")
    print("Beenden mit Strg+C.")

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    finally:
        zustand.bruecke.beende()


def _lese_aufruf(argumente: list[str]) -> tuple[str, int] | None:
    """Liest die Aufrufparameter aus der Kommandozeile."""
    parser = argparse.ArgumentParser(
        prog="kimi3-web",
        description="Weboberfläche von Kimi3",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Netzwerkadresse (Standard: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Anschlussnummer (Standard: 5000)",
    )
    args = parser.parse_args(argumente)
    host = args.host or _host_aus_umgebung()
    port = args.port or _port_aus_umgebung()
    try:
        port_nummer = int(port)
    except (ValueError, TypeError):
        print(f"Fehler: „{port}“ ist keine gültige Anschlussnummer.", file=sys.stderr)
        return None
    return host, port_nummer


def _host_aus_umgebung() -> str:
    import os
    return os.environ.get("KIMI3_HOST", "0.0.0.0")


def _port_aus_umgebung() -> str:
    import os
    return os.environ.get("KIMI3_PORT", "5000")


if __name__ == "__main__":
    ergebnis = _lese_aufruf(sys.argv[1:])
    if ergebnis is None:
        sys.exit(1)
    starte_server(ergebnis[0], ergebnis[1])
