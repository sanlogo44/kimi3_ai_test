//! Alle Routen der Weboberfläche – die Rust-Fassung des früheren `app.py`.
//!
//! Adressen, Formularfelder, JSON-Felder, Statuscodes und Meldungen sind
//! unverändert übernommen, damit die Seiten und ihr JavaScript ohne
//! Anpassung weiterlaufen.

use std::collections::HashMap;
use std::sync::Arc;

use axum::extract::{Path, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::Router;
use serde_json::{json, Map, Value};

use kern::bewertungen::BewertungsEintrag;
use kern::metriken::Metrik;

use crate::bruecke::BrueckenFehler;
use crate::sitzung::{self, Sitzung};
use crate::vorlagen;
use crate::zustand::{
    checkpoint_fuer_seite, metrik_fuer_seite, schalter_fuer_seite, zusammenfassung_fuer_seite,
    Zustand,
};

/// Meldung, wenn jemand ohne Rechte eine Schnittstelle aufruft.
const OHNE_RECHTE: &str = "Nicht angemeldet oder keine Administratorrechte.";

/// Baut den Router mit allen Routen.
pub fn baue_router(zustand: Arc<Zustand>) -> Router {
    Router::new()
        .route("/login", get(anmeldung_zeigen).post(anmeldung_pruefen))
        .route(
            "/change-credentials",
            get(zugangsdaten_zeigen).post(zugangsdaten_aendern),
        )
        .route("/logout", get(abmelden))
        .route("/", get(trainingsseite))
        .route("/admin", get(verwaltungsseite))
        .route("/api/toggles", get(schalter_lesen).post(schalter_setzen))
        .route("/api/train", post(training))
        .route("/api/train/soup", post(soup))
        .route(
            "/api/checkpoints",
            get(checkpoints_lesen).post(checkpoint_speichern),
        )
        .route(
            "/api/checkpoints/{kennung}/delete",
            post(checkpoint_loeschen),
        )
        .route("/api/checkpoints/{kennung}/use", post(checkpoint_nutzen))
        .route("/api/rate", post(bewerten))
        .route("/api/metrics", get(metriken_lesen))
        .route("/api/benchmarks", get(benchmarks_lesen))
        .with_state(zustand)
}

// ----------------------------------------------------------------- Hilfen
/// Gibt die Adressen der Routen für die Seitenvorlagen zurück.
fn adressen() -> vorlagen::Adressen {
    vorlagen::Adressen::default()
}

/// Baut eine HTML-Antwort.
fn html(inhalt: String) -> Response {
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/html; charset=utf-8")],
        inhalt,
    )
        .into_response()
}

/// Baut eine JSON-Antwort mit Status.
fn antwort_json(status: StatusCode, inhalt: Value) -> Response {
    (status, axum::Json(inhalt)).into_response()
}

/// Baut eine Umleitung (wie `redirect` in Flask, Status 302).
fn umleitung(ziel: &str) -> Response {
    (
        StatusCode::FOUND,
        [(header::LOCATION, ziel.to_string())],
        String::new(),
    )
        .into_response()
}

/// Baut eine Umleitung, die zugleich die Sitzung setzt.
fn umleitung_mit_sitzung(ziel: &str, kopfzeile: String) -> Response {
    (
        StatusCode::FOUND,
        [
            (header::LOCATION, ziel.to_string()),
            (header::SET_COOKIE, kopfzeile),
        ],
        String::new(),
    )
        .into_response()
}

/// Liest die Sitzung aus den Kopfzeilen.
fn hole_sitzung(zustand: &Zustand, kopfzeilen: &HeaderMap) -> Sitzung {
    let zeile = kopfzeilen
        .get(header::COOKIE)
        .and_then(|wert| wert.to_str().ok());
    sitzung::aus_kopfzeile(&zustand.geheimnis, zeile)
}

/// Prüft die Administratorrechte für eine Seite.
///
/// Wie der frühere Dekorator `admin_erforderlich`: Seiten leiten zur
/// Anmeldung um, Schnittstellen antworten mit 401 und JSON.
fn pruefe_seite(zustand: &Zustand, kopfzeilen: &HeaderMap) -> Result<Sitzung, Response> {
    let sitzung = hole_sitzung(zustand, kopfzeilen);
    if sitzung.ist_angemeldet() {
        Ok(sitzung)
    } else {
        Err(umleitung(&adressen().anmeldung))
    }
}

/// Prüft die Administratorrechte für eine Schnittstelle.
fn pruefe_api(zustand: &Zustand, kopfzeilen: &HeaderMap) -> Result<Sitzung, Response> {
    let sitzung = hole_sitzung(zustand, kopfzeilen);
    if sitzung.ist_angemeldet() {
        Ok(sitzung)
    } else {
        Err(antwort_json(
            StatusCode::UNAUTHORIZED,
            json!({"fehler": OHNE_RECHTE}),
        ))
    }
}

/// Wandelt einen Fehler der Brücke in eine JSON-Antwort um.
fn fehler_antwort(fehler: &BrueckenFehler) -> Response {
    let status = StatusCode::from_u16(fehler.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
    antwort_json(status, json!({"fehler": fehler.meldung}))
}

/// Liest einen JSON-Rumpf; ungültige Angaben ergeben ein leeres Wörterbuch.
///
/// Entspricht `request.get_json(silent=True) or {}` in Flask.
pub fn json_rumpf(rumpf: &str) -> Value {
    match serde_json::from_str::<Value>(rumpf) {
        Ok(wert) if wert.is_object() => wert,
        _ => json!({}),
    }
}

/// Entschlüsselt einen Wert aus einem Formular (`%20`, `+`).
fn entschluessle(text: &str) -> String {
    let bytes = text.as_bytes();
    let mut ergebnis: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut stelle = 0;
    while stelle < bytes.len() {
        match bytes[stelle] {
            b'+' => {
                ergebnis.push(b' ');
                stelle += 1;
            }
            b'%' if stelle + 2 < bytes.len() => {
                let paar = std::str::from_utf8(&bytes[stelle + 1..stelle + 3]).unwrap_or("");
                match u8::from_str_radix(paar, 16) {
                    Ok(zahl) => {
                        ergebnis.push(zahl);
                        stelle += 3;
                    }
                    Err(_) => {
                        ergebnis.push(b'%');
                        stelle += 1;
                    }
                }
            }
            zeichen => {
                ergebnis.push(zeichen);
                stelle += 1;
            }
        }
    }
    String::from_utf8_lossy(&ergebnis).to_string()
}

/// Liest die Felder eines Formulars (`application/x-www-form-urlencoded`).
pub fn formular(rumpf: &str) -> HashMap<String, String> {
    let mut felder = HashMap::new();
    for teil in rumpf.split('&').filter(|teil| !teil.is_empty()) {
        let (name, wert) = match teil.split_once('=') {
            Some((name, wert)) => (name, wert),
            None => (teil, ""),
        };
        felder.insert(entschluessle(name), entschluessle(wert));
    }
    felder
}

/// Gibt ein Formularfeld zurück (fehlt es, ist es leer).
fn feld<'a>(felder: &'a HashMap<String, String>, name: &str) -> &'a str {
    felder.get(name).map(String::as_str).unwrap_or("")
}

/// Liest eine Zahl aus dem JSON-Rumpf, deutsch oder englisch benannt.
fn json_zahl(daten: &Value, englisch: &str, deutsch: &str) -> Option<f64> {
    match zahlwunsch(daten, englisch, deutsch) {
        Zahlwunsch::Fliesskomma(zahl) => Some(zahl),
        _ => None,
    }
}

/// Ergebnis des Zahlenlesens: fehlt, ungültig oder gültig.
///
/// Die Unterscheidung ist nötig, weil ein fehlendes Feld den Standardwert
/// nutzt, ein unlesbares Feld aber – wie in der Flask-Fassung – zu einer
/// Antwort mit Status 400 führt.
#[derive(Debug, PartialEq)]
enum Zahlwunsch {
    /// Kein passendes Feld vorhanden.
    Fehlt,
    /// Feld vorhanden, aber keine Zahl.
    Ungueltig,
    /// Gültige Fließkommazahl.
    Fliesskomma(f64),
}

/// Liest den Rohwert eines deutsch oder englisch benannten Feldes.
fn rohwert<'a>(daten: &'a Value, englisch: &str, deutsch: &str) -> Option<&'a Value> {
    match daten.get(englisch) {
        Some(wert) => Some(wert),
        None => daten.get(deutsch),
    }
}

/// Deutet einen Rohwert als Fließkommazahl (wie `float(...)` in Python).
fn zahlwunsch(daten: &Value, englisch: &str, deutsch: &str) -> Zahlwunsch {
    let Some(wert) = rohwert(daten, englisch, deutsch) else {
        return Zahlwunsch::Fehlt;
    };
    match wert {
        Value::Number(zahl) => match zahl.as_f64() {
            Some(zahl) => Zahlwunsch::Fliesskomma(zahl),
            None => Zahlwunsch::Ungueltig,
        },
        Value::Bool(ja) => Zahlwunsch::Fliesskomma(if *ja { 1.0 } else { 0.0 }),
        Value::String(text) => match text.trim().parse::<f64>() {
            Ok(zahl) => Zahlwunsch::Fliesskomma(zahl),
            Err(_) => Zahlwunsch::Ungueltig,
        },
        _ => Zahlwunsch::Ungueltig,
    }
}

/// Deutet einen Rohwert als Ganzzahl (wie `int(...)` in Python).
///
/// Texte müssen – genau wie in Python – ganzzahlig sein: `"2.5"` gilt als
/// ungültig, `2.5` als Zahl wird abgeschnitten.
fn ganzzahlwunsch(daten: &Value, englisch: &str, deutsch: &str) -> Zahlwunsch {
    let Some(wert) = rohwert(daten, englisch, deutsch) else {
        return Zahlwunsch::Fehlt;
    };
    match wert {
        Value::Number(zahl) => match zahl.as_f64() {
            Some(zahl) => Zahlwunsch::Fliesskomma(zahl.trunc()),
            None => Zahlwunsch::Ungueltig,
        },
        Value::Bool(ja) => Zahlwunsch::Fliesskomma(if *ja { 1.0 } else { 0.0 }),
        Value::String(text) => match text.trim().parse::<i64>() {
            Ok(zahl) => Zahlwunsch::Fliesskomma(zahl as f64),
            Err(_) => Zahlwunsch::Ungueltig,
        },
        _ => Zahlwunsch::Ungueltig,
    }
}

/// Liest einen Text aus dem JSON-Rumpf, deutsch oder englisch benannt.
fn json_text(daten: &Value, englisch: &str, deutsch: &str) -> Option<String> {
    daten
        .get(englisch)
        .or_else(|| daten.get(deutsch))
        .and_then(Value::as_str)
        .map(str::to_string)
        .filter(|text| !text.is_empty())
}

/// Liest eine Liste von Texten aus dem JSON-Rumpf.
fn json_liste(daten: &Value, englisch: &str, deutsch: &str) -> Vec<String> {
    daten
        .get(englisch)
        .or_else(|| daten.get(deutsch))
        .and_then(Value::as_array)
        .map(|liste| {
            liste
                .iter()
                .map(|wert| match wert {
                    Value::String(text) => text.clone(),
                    anderer => anderer.to_string(),
                })
                .collect()
        })
        .unwrap_or_default()
}

/// Holt die Checkpoint-Liste – über die Brücke, sonst aus den Dateinamen.
async fn checkpoint_liste(zustand: &Zustand) -> Vec<kern::checkpoints::Checkpoint> {
    match zustand.bruecke.rufe("checkpoints", json!({})).await {
        Ok(daten) => daten
            .get("checkpoints")
            .and_then(Value::as_array)
            .map(|liste| {
                liste
                    .iter()
                    .map(kern::checkpoints::Checkpoint::aus_wert)
                    .collect()
            })
            .unwrap_or_else(|| zustand.checkpoints.liste()),
        Err(_) => zustand.checkpoints.liste(),
    }
}

// -------------------------------------------------------------- Anmeldung
/// Zeigt das Anmeldeformular.
async fn anmeldung_zeigen(State(_zustand): State<Arc<Zustand>>) -> Response {
    html(vorlagen::anmeldeseite(None, &adressen()))
}

/// Prüft die Zugangsdaten.
async fn anmeldung_pruefen(State(zustand): State<Arc<Zustand>>, rumpf: String) -> Response {
    let felder = formular(&rumpf);
    let benutzername = feld(&felder, "username").trim().to_string();
    let passwort = feld(&felder, "password").to_string();
    let fehler: Option<&str> = match zustand.konten.pruefe_anmeldung(&benutzername, &passwort) {
        Some(konto) if !konto.ist_administrator() => {
            Some("Dieses Konto hat keine Administratorrechte.")
        }
        Some(konto) => {
            let neue_sitzung = Sitzung {
                benutzer: konto.benutzername.clone(),
                ist_admin: true,
            };
            let kopfzeile = sitzung::setz_kopfzeile(&zustand.geheimnis, &neue_sitzung);
            let ziel = if konto.passwortwechsel_faellig {
                adressen().zugangsdaten
            } else {
                adressen().training
            };
            return umleitung_mit_sitzung(&ziel, kopfzeile);
        }
        None => Some("Ungültige Zugangsdaten."),
    };
    html(vorlagen::anmeldeseite(fehler, &adressen()))
}

/// Zeigt das Formular für neue Zugangsdaten.
async fn zugangsdaten_zeigen(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
) -> Response {
    let sitzung = match pruefe_seite(&zustand, &kopfzeilen) {
        Ok(sitzung) => sitzung,
        Err(antwort) => return antwort,
    };
    let benutzer = if sitzung.benutzer.is_empty() {
        zustand.standardbenutzer.clone()
    } else {
        sitzung.benutzer
    };
    let erzwungen = zustand.konten.passwortwechsel_faellig(&benutzer);
    html(vorlagen::zugangsdatenseite(
        &benutzer,
        None,
        erzwungen,
        &adressen(),
    ))
}

/// Ändert Benutzername und Passwort.
async fn zugangsdaten_aendern(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    rumpf: String,
) -> Response {
    let sitzung = match pruefe_seite(&zustand, &kopfzeilen) {
        Ok(sitzung) => sitzung,
        Err(antwort) => return antwort,
    };
    let aktueller_benutzer = if sitzung.benutzer.is_empty() {
        zustand.standardbenutzer.clone()
    } else {
        sitzung.benutzer
    };
    let felder = formular(&rumpf);
    let neuer_benutzer = feld(&felder, "username").trim().to_string();
    let passwort = feld(&felder, "password");
    let wiederholung = feld(&felder, "password2");

    let meldung: Option<&str> = if neuer_benutzer.is_empty() {
        Some("Bitte einen Benutzernamen eingeben.")
    } else if passwort.chars().count() < kern::konten::MINDESTLAENGE_PASSWORT {
        Some("Das Passwort muss mindestens 4 Zeichen haben.")
    } else if passwort != wiederholung {
        Some("Die Passwörter stimmen nicht überein.")
    } else {
        match zustand
            .konten
            .aendere_zugangsdaten(&aktueller_benutzer, &neuer_benutzer, passwort)
        {
            Ok(konto) => {
                let neue_sitzung = Sitzung {
                    benutzer: konto.benutzername,
                    ist_admin: true,
                };
                return umleitung_mit_sitzung(
                    &adressen().training,
                    sitzung::setz_kopfzeile(&zustand.geheimnis, &neue_sitzung),
                );
            }
            Err(_) => Some("Die Zugangsdaten konnten nicht geändert werden."),
        }
    };
    let erzwungen = zustand.konten.passwortwechsel_faellig(&aktueller_benutzer);
    html(vorlagen::zugangsdatenseite(
        &aktueller_benutzer,
        meldung,
        erzwungen,
        &adressen(),
    ))
}

/// Beendet die Sitzung.
async fn abmelden(State(_zustand): State<Arc<Zustand>>) -> Response {
    umleitung_mit_sitzung(&adressen().anmeldung, sitzung::loesch_kopfzeile())
}

// ------------------------------------------------------------------ Seiten
/// Zeigt die Trainingsoberfläche.
async fn trainingsseite(State(zustand): State<Arc<Zustand>>, kopfzeilen: HeaderMap) -> Response {
    let sitzung = match pruefe_seite(&zustand, &kopfzeilen) {
        Ok(sitzung) => sitzung,
        Err(antwort) => return antwort,
    };
    let schichten: Vec<String> = match zustand.bruecke.rufe("schichten", json!({})).await {
        Ok(daten) => json_liste(&daten, "schichten", "layers"),
        Err(_) => Vec::new(),
    };
    let punkte: Vec<vorlagen::Checkpoint> = checkpoint_liste(&zustand)
        .await
        .iter()
        .map(checkpoint_fuer_seite)
        .collect();
    let kern_fehler = zustand.bruecke.kern_fehler().await;
    html(vorlagen::trainingsseite(
        &schalter_fuer_seite(&zustand.schalter().await),
        &punkte,
        &schichten,
        &sitzung.benutzer,
        kern_fehler.as_deref(),
        &adressen(),
    ))
}

/// Zeigt den Verwaltungsbereich.
async fn verwaltungsseite(State(zustand): State<Arc<Zustand>>, kopfzeilen: HeaderMap) -> Response {
    let sitzung = match pruefe_seite(&zustand, &kopfzeilen) {
        Ok(sitzung) => sitzung,
        Err(antwort) => return antwort,
    };
    let punkte: Vec<vorlagen::Checkpoint> = checkpoint_liste(&zustand)
        .await
        .iter()
        .map(checkpoint_fuer_seite)
        .collect();
    let metriken: Vec<vorlagen::Metrik> = zustand
        .metriken
        .hole_alle()
        .iter()
        .map(metrik_fuer_seite)
        .collect();
    let kennzahlen = zusammenfassung_fuer_seite(&zustand.metriken.zusammenfassung());
    let kern_fehler = zustand.bruecke.kern_fehler().await;
    html(vorlagen::verwaltungsseite(
        &schalter_fuer_seite(&zustand.schalter().await),
        &punkte,
        &metriken,
        Some(&kennzahlen),
        zustand.benchmarks_laeuft().await,
        &sitzung.benutzer,
        kern_fehler.as_deref(),
        &adressen(),
    ))
}

// -------------------------------------------------- Schnittstelle: Schalter
/// Baut die Antwort der Schalter-Schnittstelle.
async fn schalter_antwort(zustand: &Zustand) -> Response {
    let schalter = zustand.schalter().await.als_wert();
    let laeuft = zustand.benchmarks_laeuft().await;
    antwort_json(
        StatusCode::OK,
        json!({
            "schalter": schalter,
            "toggles": schalter,
            "benchmarks_laeuft": laeuft,
            "benchmarks_running": laeuft,
        }),
    )
}

/// Liest die vier Schalter.
async fn schalter_lesen(State(zustand): State<Arc<Zustand>>, kopfzeilen: HeaderMap) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    schalter_antwort(&zustand).await
}

/// Setzt die vier Schalter.
async fn schalter_setzen(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    rumpf: String,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    let daten = json_rumpf(&rumpf);
    {
        let mut schalter = zustand.schalter.lock().await;
        schalter.uebernimm(&daten);
        zustand.schalter_speicher.speichere(&schalter);
    }
    let benchmarks_erwaehnt = daten.get("auto_benchmarks").is_some();
    if benchmarks_erwaehnt {
        let gewuenscht = zustand.schalter().await.auto_benchmarks;
        if gewuenscht {
            match zustand.bruecke.rufe("benchmarks_starten", json!({})).await {
                Ok(_) => *zustand.benchmarks_laeuft.lock().await = true,
                Err(fehler) => {
                    // Ohne Modellkern lässt sich der Schalter nicht halten.
                    let mut schalter = zustand.schalter.lock().await;
                    schalter.auto_benchmarks = false;
                    zustand.schalter_speicher.speichere(&schalter);
                    *zustand.benchmarks_laeuft.lock().await = false;
                    return fehler_antwort(&fehler);
                }
            }
        } else {
            let _ = zustand.bruecke.rufe("benchmarks_stoppen", json!({})).await;
            *zustand.benchmarks_laeuft.lock().await = false;
        }
    }
    schalter_antwort(&zustand).await
}

// ------------------------------------------------- Schnittstelle: Training
/// Trainiert eine Kopie des Modells.
async fn training(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    rumpf: String,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    // Ohne Modellkern antwortet die Brücke sofort mit 503 – wie in Flask.
    if let Err(fehler) = zustand.bruecke.rufe("bereit", json!({})).await {
        return fehler_antwort(&fehler);
    }
    let daten = json_rumpf(&rumpf);
    let zahlenfehler = antwort_json(
        StatusCode::BAD_REQUEST,
        json!({"fehler": "Epochen und Lernrate müssen Zahlen sein."}),
    );
    let epochen_zahl = match ganzzahlwunsch(&daten, "epochs", "epochen") {
        Zahlwunsch::Fliesskomma(zahl) if zahl.is_finite() => zahl,
        Zahlwunsch::Fehlt => 10.0,
        _ => return zahlenfehler,
    };
    let lernrate = match zahlwunsch(&daten, "lr", "lernrate") {
        Zahlwunsch::Fliesskomma(zahl) => zahl,
        Zahlwunsch::Fehlt => 1e-2,
        Zahlwunsch::Ungueltig => return zahlenfehler,
    };
    let epochen = (epochen_zahl as i64).max(1);
    let basis = json_text(&daten, "base_model", "basis_modell");
    let schichten = {
        let liste = json_liste(&daten, "layers", "schichten");
        if liste.is_empty() {
            None
        } else {
            Some(liste)
        }
    };
    if schichten.is_some() && !zustand.schalter().await.schicht_training {
        return antwort_json(
            StatusCode::FORBIDDEN,
            json!({"fehler": "Schicht-Training ist deaktiviert."}),
        );
    }
    let anfrage = json!({
        "epochen": epochen,
        "lernrate": lernrate,
        "basis": basis,
        "schichten": schichten,
    });
    let werte = match zustand.bruecke.rufe("trainiere", anfrage).await {
        Ok(werte) => werte,
        Err(fehler) => return fehler_antwort(&fehler),
    };
    let genauigkeit = werte
        .get("genauigkeit")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let trainingszeit = werte
        .get("trainingszeit")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let tokens = werte.get("tokens").and_then(Value::as_i64).unwrap_or(0);
    let verlust = werte.get("verlust").and_then(Value::as_f64).unwrap_or(0.0);
    let modellname = werte
        .get("modellname")
        .and_then(Value::as_str)
        .unwrap_or("unbekannt")
        .to_string();
    zustand.metriken.fuege_hinzu(Metrik {
        modell: modellname,
        genauigkeit,
        verlust,
        tokens,
        trainingszeit,
        epochen,
        markierungen: vec!["web".into(), "training".into()],
        ..Metrik::default()
    });
    let trainierte_schichten = match &schichten {
        Some(liste) => json!(liste),
        None => json!("alle"),
    };
    antwort_json(
        StatusCode::OK,
        json!({
            "genauigkeit": genauigkeit,
            "accuracy": genauigkeit,
            "trainingszeit": trainingszeit,
            "train_time": trainingszeit,
            "tokens": tokens,
            "verlust": verlust,
            "trainierte_schichten": trainierte_schichten,
            "layers_trained": trainierte_schichten,
        }),
    )
}

/// Mittelt mehrere Checkpoints (SOUP-Training).
async fn soup(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    rumpf: String,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    if let Err(fehler) = zustand.bruecke.rufe("bereit", json!({})).await {
        return fehler_antwort(&fehler);
    }
    let daten = json_rumpf(&rumpf);
    let kennungen = json_liste(&daten, "checkpoint_ids", "checkpoint_kennungen");
    let werte = match zustand
        .bruecke
        .rufe("soup", json!({"kennungen": kennungen}))
        .await
    {
        Ok(werte) => werte,
        Err(fehler) => return fehler_antwort(&fehler),
    };
    let genauigkeit = werte
        .get("genauigkeit")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let kennung = werte
        .get("kennung")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let modellname = werte
        .get("modellname")
        .and_then(Value::as_str)
        .unwrap_or("soup")
        .to_string();
    zustand.metriken.fuege_hinzu(Metrik {
        modell: modellname,
        genauigkeit,
        markierungen: vec!["web".into(), "soup".into()],
        ..Metrik::default()
    });
    antwort_json(
        StatusCode::OK,
        json!({
            "genauigkeit": genauigkeit,
            "accuracy": genauigkeit,
            "checkpoint_kennung": kennung,
            "checkpoint_id": kennung,
        }),
    )
}

// ---------------------------------------------- Schnittstelle: Checkpoints
/// Listet die Checkpoints.
async fn checkpoints_lesen(State(zustand): State<Arc<Zustand>>, kopfzeilen: HeaderMap) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    match zustand.bruecke.rufe("checkpoints", json!({})).await {
        Ok(daten) => {
            let liste = daten
                .get("checkpoints")
                .cloned()
                .unwrap_or_else(|| json!([]));
            antwort_json(StatusCode::OK, json!({"checkpoints": liste}))
        }
        Err(fehler) => {
            // Lesen geht auch ohne PyTorch, nur ohne die Zusatzdaten der Datei.
            let liste: Vec<Value> = zustand
                .checkpoints
                .liste()
                .iter()
                .map(kern::checkpoints::Checkpoint::als_wert)
                .collect();
            antwort_json(
                StatusCode::OK,
                json!({"checkpoints": liste, "hinweis": fehler.meldung}),
            )
        }
    }
}

/// Speichert das aktuelle Modell als Checkpoint.
async fn checkpoint_speichern(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    rumpf: String,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    let daten = json_rumpf(&rumpf);
    let name = json_text(&daten, "name", "name").unwrap_or_else(|| "checkpoint".to_string());
    let genauigkeit = json_zahl(&daten, "accuracy", "genauigkeit");
    let anfrage = json!({"name": name, "genauigkeit": genauigkeit});
    match zustand.bruecke.rufe("checkpoint_speichern", anfrage).await {
        Ok(werte) => {
            let kennung = werte.get("kennung").cloned().unwrap_or(Value::Null);
            antwort_json(
                StatusCode::OK,
                json!({"checkpoint_kennung": kennung, "checkpoint_id": kennung}),
            )
        }
        Err(fehler) => fehler_antwort(&fehler),
    }
}

/// Löscht einen Checkpoint.
async fn checkpoint_loeschen(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    Path(kennung): Path<String>,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    let geloescht = match zustand
        .bruecke
        .rufe("checkpoint_loeschen", json!({"kennung": kennung}))
        .await
    {
        Ok(werte) => werte
            .get("geloescht")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        // Löschen gelingt auch ohne PyTorch.
        Err(_) => zustand.checkpoints.loesche(&kennung),
    };
    antwort_json(
        StatusCode::OK,
        json!({"geloescht": geloescht, "deleted": geloescht}),
    )
}

/// Lädt einen Checkpoint als Arbeitskopie.
async fn checkpoint_nutzen(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    Path(kennung): Path<String>,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    match zustand
        .bruecke
        .rufe("checkpoint_nutzen", json!({"kennung": kennung}))
        .await
    {
        Ok(werte) => {
            let name = werte
                .get("geladen")
                .and_then(Value::as_str)
                .unwrap_or("unbekannt")
                .to_string();
            antwort_json(StatusCode::OK, json!({"geladen": name, "loaded": name}))
        }
        Err(fehler) => fehler_antwort(&fehler),
    }
}

// ----------------------------------------------- Schnittstelle: Bewertung
/// Speichert eine Bewertung.
///
/// Bewusste Änderung gegenüber der Flask-Fassung: Die Bewertung landet im
/// gemeinsamen JSON-Speicher `data/bewertungen.json` statt in der eigenen
/// SQLite-Datei `data/bewertungen.db`. So sehen Weboberfläche und
/// Desktop-Oberfläche dieselben Bewertungen.
async fn bewerten(
    State(zustand): State<Arc<Zustand>>,
    kopfzeilen: HeaderMap,
    rumpf: String,
) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    if !zustand.schalter().await.bewertungsmodus {
        return antwort_json(
            StatusCode::FORBIDDEN,
            json!({"fehler": "Bewertungsmodus ist deaktiviert."}),
        );
    }
    let daten = json_rumpf(&rumpf);
    let punkte = json_zahl(&daten, "score", "bewertung").unwrap_or(0.0);
    let antwort_text = json_text(&daten, "answer", "antwort").unwrap_or_default();
    let kommentar = json_text(&daten, "comment", "kommentar").unwrap_or_default();
    let frage = json_text(&daten, "prompt", "frage").unwrap_or(kommentar);
    let modell = json_text(&daten, "model", "modell").unwrap_or_else(|| "unbekannt".to_string());
    let mut eintrag = BewertungsEintrag::neu(&modell, &frage, &antwort_text, punkte as i32);
    eintrag.markierungen = vec!["web".to_string()];
    zustand.bewertungen.fuege_hinzu(eintrag);
    antwort_json(StatusCode::OK, json!({"ok": true}))
}

// ------------------------------------------------ Schnittstelle: Metriken
/// Gibt alle gesammelten Metriken zurück.
async fn metriken_lesen(State(zustand): State<Arc<Zustand>>, kopfzeilen: HeaderMap) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    let metriken: Vec<Value> = zustand
        .metriken
        .hole_alle()
        .iter()
        .map(kern::metriken::Metrik::als_wert)
        .collect();
    let kennzahlen = zustand.metriken.zusammenfassung();
    let aktiv = zustand.schalter().await.zeige_diagramm;
    let mut karte = Map::new();
    karte.insert("metriken".into(), json!(metriken));
    karte.insert("metrics".into(), json!(metriken));
    karte.insert(
        "zusammenfassung".into(),
        serde_json::to_value(&kennzahlen).unwrap_or(Value::Null),
    );
    karte.insert("aktiv".into(), Value::Bool(aktiv));
    karte.insert("enabled".into(), Value::Bool(aktiv));
    antwort_json(StatusCode::OK, Value::Object(karte))
}

/// Gibt die Ergebnisse der Hintergrund-Benchmarks zurück.
async fn benchmarks_lesen(State(zustand): State<Arc<Zustand>>, kopfzeilen: HeaderMap) -> Response {
    if let Err(antwort) = pruefe_api(&zustand, &kopfzeilen) {
        return antwort;
    }
    let (laeuft, ergebnisse) = match zustand.bruecke.rufe("benchmarks_status", json!({})).await {
        Ok(werte) => (
            werte.get("laeuft").and_then(Value::as_bool).unwrap_or(false),
            werte.get("ergebnisse").cloned().unwrap_or_else(|| json!([])),
        ),
        Err(_) => (false, json!([])),
    };
    *zustand.benchmarks_laeuft.lock().await = laeuft;
    antwort_json(
        StatusCode::OK,
        json!({"laeuft": laeuft, "ergebnisse": ergebnisse}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formulare_werden_entschluesselt() {
        let felder = formular("username=Admin&password=ge%20heim%21&leer=");
        assert_eq!(feld(&felder, "username"), "Admin");
        assert_eq!(feld(&felder, "password"), "ge heim!");
        assert_eq!(feld(&felder, "leer"), "");
        assert_eq!(feld(&felder, "gibt-es-nicht"), "");
        let mit_plus = formular("text=eins+zwei&umlaut=Gr%C3%BC%C3%9Fe");
        assert_eq!(feld(&mit_plus, "text"), "eins zwei");
        assert_eq!(feld(&mit_plus, "umlaut"), "Grüße");
        assert!(formular("").is_empty());
    }

    #[test]
    fn ungueltiges_json_ergibt_leeres_woerterbuch() {
        assert_eq!(json_rumpf("kein JSON"), json!({}));
        assert_eq!(json_rumpf("[1, 2]"), json!({}));
        assert_eq!(json_rumpf(""), json!({}));
        assert_eq!(json_rumpf("{\"a\": 1}"), json!({"a": 1}));
    }

    #[test]
    fn deutsche_und_englische_felder_werden_gelesen() {
        let daten = json!({"epochs": 5, "lernrate": "0.5", "layers": ["fc1"]});
        assert_eq!(json_zahl(&daten, "epochs", "epochen"), Some(5.0));
        assert_eq!(json_zahl(&daten, "lr", "lernrate"), Some(0.5));
        assert_eq!(json_zahl(&daten, "fehlt", "fehlt-auch"), None);
        assert_eq!(json_liste(&daten, "layers", "schichten"), vec!["fc1"]);
        assert!(json_liste(&daten, "nichts", "nichts").is_empty());
        assert_eq!(
            ganzzahlwunsch(&json!({"epochen": "2.5"}), "epochs", "epochen"),
            Zahlwunsch::Ungueltig
        );
        assert_eq!(
            ganzzahlwunsch(&json!({"epochen": 3.9}), "epochs", "epochen"),
            Zahlwunsch::Fliesskomma(3.0)
        );
        assert_eq!(
            ganzzahlwunsch(&json!({}), "epochs", "epochen"),
            Zahlwunsch::Fehlt
        );
        assert_eq!(
            zahlwunsch(&json!({"lr": Value::Null}), "lr", "lernrate"),
            Zahlwunsch::Ungueltig
        );
        let texte = json!({"basis_modell": "abc", "name": ""});
        assert_eq!(
            json_text(&texte, "base_model", "basis_modell"),
            Some("abc".to_string())
        );
        assert_eq!(json_text(&texte, "name", "name"), None);
    }

    #[test]
    fn adressen_entsprechen_den_routen() {
        let adressen = adressen();
        assert_eq!(adressen.training, "/");
        assert_eq!(adressen.verwaltung, "/admin");
        assert_eq!(adressen.anmeldung, "/login");
    }
}
