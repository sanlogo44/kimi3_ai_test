//! Python-Modul `kimi3_kern`: macht die Rust-Logik in Python nutzbar.
//!
//! Die Desktop-Oberfläche (CustomTkinter) und der Modellkern (PyTorch)
//! bleiben in Python. Damit es die Regeln – Dateiformate, Standardwerte,
//! Meldungen – nur einmal gibt, greifen sie über dieses Modul auf dieselbe
//! Rust-Logik zu, die auch die Weboberfläche verwendet.
//!
//! Die Klassen und Funktionen tragen deutsche Namen und geben gewöhnliche
//! Python-Wörterbücher und -Listen zurück, damit die bisherigen
//! Python-Module unverändert damit weiterarbeiten können.

use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString};
use serde_json::{Map, Value};
use std::path::{Path, PathBuf};

// --------------------------------------------------------------- Umwandlung
/// Wandelt einen JSON-Wert in ein Python-Objekt.
fn nach_python<'p>(py: Python<'p>, wert: &Value) -> PyResult<Bound<'p, PyAny>> {
    Ok(match wert {
        Value::Null => py.None().into_bound(py),
        Value::Bool(ja) => PyBool::new(py, *ja).to_owned().into_any(),
        Value::Number(zahl) => {
            if let Some(ganz) = zahl.as_i64() {
                ganz.into_pyobject(py)?.into_any()
            } else {
                zahl.as_f64().unwrap_or(0.0).into_pyobject(py)?.into_any()
            }
        }
        Value::String(text) => PyString::new(py, text).into_any(),
        Value::Array(liste) => {
            let ziel = PyList::empty(py);
            for eintrag in liste {
                ziel.append(nach_python(py, eintrag)?)?;
            }
            ziel.into_any()
        }
        Value::Object(karte) => {
            let ziel = PyDict::new(py);
            for (schluessel, eintrag) in karte {
                ziel.set_item(schluessel, nach_python(py, eintrag)?)?;
            }
            ziel.into_any()
        }
    })
}

/// Wandelt ein Python-Objekt in einen JSON-Wert.
fn nach_wert(objekt: &Bound<'_, PyAny>) -> PyResult<Value> {
    if objekt.is_none() {
        return Ok(Value::Null);
    }
    if objekt.is_instance_of::<PyBool>() {
        return Ok(Value::Bool(objekt.extract::<bool>()?));
    }
    if objekt.is_instance_of::<PyInt>() {
        let zahl: i64 = objekt.extract()?;
        return Ok(Value::from(zahl));
    }
    if objekt.is_instance_of::<PyFloat>() {
        let zahl: f64 = objekt.extract()?;
        return Ok(serde_json::Number::from_f64(zahl)
            .map(Value::Number)
            .unwrap_or(Value::Null));
    }
    if objekt.is_instance_of::<PyString>() {
        return Ok(Value::String(objekt.extract::<String>()?));
    }
    if let Ok(karte) = objekt.cast::<PyDict>() {
        let mut ziel = Map::new();
        for (schluessel, eintrag) in karte.iter() {
            ziel.insert(schluessel.str()?.extract::<String>()?, nach_wert(&eintrag)?);
        }
        return Ok(Value::Object(ziel));
    }
    if let Ok(liste) = objekt.try_iter() {
        let mut ziel = Vec::new();
        for eintrag in liste {
            ziel.push(nach_wert(&eintrag?)?);
        }
        return Ok(Value::Array(ziel));
    }
    Ok(Value::String(objekt.str()?.extract::<String>()?))
}

/// Wandelt einen Wert mit `serde` und gibt ihn als Python-Objekt zurück.
fn serde_nach_python<'p, T: serde::Serialize>(py: Python<'p>, wert: &T) -> PyResult<Bound<'p, PyAny>> {
    let json = serde_json::to_value(wert)
        .map_err(|fehler| PyValueError::new_err(format!("Umwandlung fehlgeschlagen: {fehler}")))?;
    nach_python(py, &json)
}

/// Deutet einen optionalen Pfad; `None` bedeutet Standardpfad.
fn pfad_oder<T: AsRef<Path>>(pfad: Option<PathBuf>, ersatz: T) -> PathBuf {
    pfad.unwrap_or_else(|| ersatz.as_ref().to_path_buf())
}

/// Wandelt ein Konto in ein Wörterbuch samt Benutzernamen.
///
/// In `data/users.json` steht der Name als Schlüssel; für Python ist er als
/// Feld `benutzername` bequemer.
fn konto_als_wert(konto: &kern::Konto) -> Value {
    let mut wert = konto.als_wert();
    if let Some(karte) = wert.as_object_mut() {
        karte.insert(
            "benutzername".to_string(),
            Value::String(konto.benutzername.clone()),
        );
    }
    wert
}

// ------------------------------------------------------------------- Pfade
/// Gibt den Projektordner zurück.
#[pyfunction]
fn projektordner() -> String {
    kern::pfade::projektordner().to_string_lossy().to_string()
}

/// Gibt den Datenordner `data/` zurück und legt ihn bei Bedarf an.
#[pyfunction]
fn datenordner() -> String {
    let ordner = kern::pfade::datenordner();
    let _ = kern::pfade::stelle_ordner_bereit(&ordner);
    ordner.to_string_lossy().to_string()
}

/// Gibt den Pfad einer Datei im Datenordner zurück.
#[pyfunction]
fn datendatei(name: &str) -> String {
    kern::pfade::datendatei(name).to_string_lossy().to_string()
}

// ---------------------------------------------------------------- Zeitangaben
/// Gibt den aktuellen Zeitstempel als ISO-Text zurück.
#[pyfunction]
fn jetzt_iso() -> String {
    kern::zeit::jetzt_iso()
}

/// Gibt den aktuellen Zeitpunkt lesbar zurück (`JJJJ-MM-TT HH:MM:SS`).
#[pyfunction]
fn jetzt_lesbar() -> String {
    kern::zeit::jetzt_lesbar()
}

/// Kürzt einen Zeitstempel auf `TT.MM. HH:MM`.
#[pyfunction]
fn kurzzeit(zeitstempel: &str) -> String {
    kern::zeit::kurzzeit(zeitstempel)
}

// -------------------------------------------------------------- Konfiguration
/// Lädt `config.yaml` samt Standardwerten als Wörterbuch.
#[pyfunction]
#[pyo3(signature = (pfad=None))]
fn lade_konfiguration(py: Python<'_>, pfad: Option<PathBuf>) -> PyResult<Bound<'_, PyAny>> {
    let konfiguration = match pfad {
        Some(pfad) => kern::Konfiguration::lade(&pfad),
        None => kern::Konfiguration::lade_standardpfad(),
    };
    nach_python(py, konfiguration.wert())
}

// ------------------------------------------------------------ Protokollierung
/// Richtet das Protokoll aus der Konfiguration ein.
#[pyfunction]
#[pyo3(signature = (stufe=None, farbig=true, datei=None))]
fn richte_protokoll_ein(stufe: Option<&str>, farbig: bool, datei: Option<PathBuf>) -> bool {
    let gewaehlt = stufe.map(kern::Stufe::aus_text).unwrap_or(kern::Stufe::Hinweis);
    kern::protokoll::setze_protokoll(kern::Protokoll::neu(gewaehlt, farbig, datei))
}

/// Schreibt eine Meldung ins Protokoll.
#[pyfunction]
fn protokolliere(stufe: &str, meldung: &str) {
    kern::protokoll::hole_protokoll().schreibe(kern::Stufe::aus_text(stufe), meldung);
}

/// Setzt die Protokollstufe nachträglich.
#[pyfunction]
fn setze_protokollstufe(stufe: &str) {
    kern::protokoll::hole_protokoll().setze_stufe(kern::Stufe::aus_text(stufe));
}

/// Gibt die eingestellte Protokollstufe zurück.
#[pyfunction]
fn protokollstufe() -> String {
    kern::protokoll::hole_protokoll().stufe().name().to_string()
}

// ------------------------------------------------------------------ Passwörter
/// Erzeugt einen Passwort-Hash im Format von Werkzeug.
#[pyfunction]
fn erzeuge_passwort_hash(passwort: &str) -> String {
    kern::passwort::erzeuge_hash(passwort)
}

/// Prüft ein Passwort gegen einen Hash (scrypt oder PBKDF2).
#[pyfunction]
fn pruefe_passwort(hash: &str, passwort: &str) -> bool {
    kern::passwort::pruefe(hash, passwort)
}

// --------------------------------------------------------------------- Rechner
/// Berechnet einen Ausdruck; bei Fehlern wird `ValueError` ausgelöst.
#[pyfunction]
fn berechne(ausdruck: &str) -> PyResult<f64> {
    kern::berechne(ausdruck).map_err(|fehler| PyValueError::new_err(fehler.meldung))
}

/// Formatiert ein Rechenergebnis wie die Oberfläche.
#[pyfunction]
fn ergebnis_text(wert: f64) -> String {
    kern::rechner::ergebnis_text(wert)
}

// ---------------------------------------------------------------- Einstellungen
/// Einstellungen der Desktop-Oberfläche (`data/settings.json`).
#[pyclass(name = "Einstellungen")]
struct PyEinstellungen {
    innen: kern::Einstellungen,
}

#[pymethods]
impl PyEinstellungen {
    /// Legt die Verwaltung an; ohne Pfad wird `data/settings.json` genutzt.
    #[new]
    #[pyo3(signature = (pfad=None))]
    fn neu(pfad: Option<PathBuf>) -> Self {
        let innen = match pfad {
            Some(pfad) => kern::Einstellungen::neu(&pfad),
            None => kern::Einstellungen::standardpfad(),
        };
        Self { innen }
    }

    /// Gibt den Dateipfad zurück.
    #[getter]
    fn pfad(&self) -> String {
        self.innen.pfad().to_string_lossy().to_string()
    }

    /// Gibt einen einzelnen Wert zurück.
    fn hole<'p>(&self, py: Python<'p>, schluessel: &str) -> PyResult<Bound<'p, PyAny>> {
        nach_python(py, &self.innen.hole(schluessel))
    }

    /// Gibt einen Wert als Text zurück.
    #[pyo3(signature = (schluessel, ersatz=""))]
    fn text(&self, schluessel: &str, ersatz: &str) -> String {
        self.innen.text(schluessel, ersatz)
    }

    /// Setzt einen Wert und speichert die Datei.
    fn setze(&self, schluessel: &str, wert: &Bound<'_, PyAny>) -> PyResult<()> {
        self.innen.setze(schluessel, nach_wert(wert)?);
        Ok(())
    }

    /// Gibt alle Einstellungen zurück.
    fn alle<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        nach_python(py, &Value::Object(self.innen.alle()))
    }

    /// Gibt die gespeicherte Fenstergröße zurück.
    #[pyo3(signature = (breite=1180, hoehe=860))]
    fn fenstergroesse(&self, breite: u32, hoehe: u32) -> (u32, u32) {
        self.innen.fenstergroesse(breite, hoehe)
    }

    /// Speichert eine neue Fenstergröße.
    fn setze_fenstergroesse(&self, breite: u32, hoehe: u32) {
        self.innen.setze_fenstergroesse(breite, hoehe);
    }

    /// Setzt alle Einstellungen auf die Standardwerte zurück.
    fn zuruecksetzen(&self) {
        self.innen.zuruecksetzen();
    }
}

// --------------------------------------------------------------------- Schalter
/// Stellung der vier Schalter (`data/schalter.json`).
#[pyclass(name = "Schalter")]
struct PySchalter {
    speicher: kern::schalter::SchalterSpeicher,
}

#[pymethods]
impl PySchalter {
    /// Legt die Verwaltung an; ohne Pfad wird `data/schalter.json` genutzt.
    #[new]
    #[pyo3(signature = (pfad=None))]
    fn neu(pfad: Option<PathBuf>) -> Self {
        let speicher = match pfad {
            Some(pfad) => kern::schalter::SchalterSpeicher::neu(&pfad),
            None => kern::schalter::SchalterSpeicher::standardpfad(),
        };
        Self { speicher }
    }

    /// Gibt den Dateipfad zurück.
    #[getter]
    fn pfad(&self) -> String {
        self.speicher.pfad().to_string_lossy().to_string()
    }

    /// Lädt die Schalterstellung als Wörterbuch.
    fn lade<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        nach_python(py, &self.speicher.lade().als_wert())
    }

    /// Übernimmt Änderungen und speichert sie; gibt die neue Stellung zurück.
    fn setze<'p>(&self, py: Python<'p>, daten: &Bound<'_, PyAny>) -> PyResult<Bound<'p, PyAny>> {
        let mut schalter = self.speicher.lade();
        schalter.uebernimm(&nach_wert(daten)?);
        self.speicher.speichere(&schalter);
        nach_python(py, &schalter.als_wert())
    }

    /// Gibt den deutschen Namen eines Schalters zurück.
    #[staticmethod]
    fn deutscher_name(name: &str) -> String {
        kern::Schalter::deutscher_name(name).to_string()
    }
}

// --------------------------------------------------------------------- Metriken
/// Speicher der Trainings- und Benchmark-Metriken (`data/metriken.json`).
#[pyclass(name = "MetrikSpeicher")]
struct PyMetrikSpeicher {
    innen: kern::MetrikSpeicher,
}

#[pymethods]
impl PyMetrikSpeicher {
    /// Legt den Speicher an; ohne Pfad wird `data/metriken.json` genutzt.
    #[new]
    #[pyo3(signature = (pfad=None))]
    fn neu(pfad: Option<PathBuf>) -> Self {
        let innen = match pfad {
            Some(pfad) => kern::MetrikSpeicher::neu(&pfad),
            None => kern::MetrikSpeicher::standardpfad(),
        };
        Self { innen }
    }

    /// Gibt den Dateipfad zurück.
    #[getter]
    fn pfad(&self) -> String {
        self.innen.pfad().to_string_lossy().to_string()
    }

    /// Gibt alle Einträge zurück.
    fn hole_alle<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.hole_alle())
    }

    /// Gibt die letzten `anzahl` Einträge zurück.
    #[pyo3(signature = (anzahl=10))]
    fn hole_letzte<'p>(&self, py: Python<'p>, anzahl: i64) -> PyResult<Bound<'p, PyAny>> {
        let anzahl = anzahl.max(0) as usize;
        serde_nach_python(py, &self.innen.hole_letzte(anzahl))
    }

    /// Fügt einen Eintrag hinzu und gibt ihn zurück.
    fn fuege_hinzu<'p>(&self, py: Python<'p>, eintrag: &Bound<'_, PyAny>) -> PyResult<Bound<'p, PyAny>> {
        let gespeichert = self.innen.fuege_wert_hinzu(&nach_wert(eintrag)?);
        serde_nach_python(py, &gespeichert)
    }

    /// Filtert nach Modell und/oder Markierung.
    #[pyo3(signature = (modell=None, markierung=None))]
    fn filtere<'p>(
        &self,
        py: Python<'p>,
        modell: Option<&str>,
        markierung: Option<&str>,
    ) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.filtere(modell, markierung))
    }

    /// Gibt alle vorkommenden Modellnamen zurück.
    fn modelle<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.modelle())
    }

    /// Gibt die Kennzahlen über alle Einträge zurück.
    fn zusammenfassung<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.zusammenfassung())
    }

    /// Gibt Durchschnittswerte je Modell zurück.
    fn vergleich_je_modell<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.vergleich_je_modell())
    }

    /// Schreibt alle Einträge als CSV-Datei und gibt den Pfad zurück.
    fn exportiere_csv(&self, pfad: PathBuf) -> PyResult<String> {
        self.innen
            .exportiere_csv(&pfad)
            .map(|pfad| pfad.to_string_lossy().to_string())
            .map_err(|fehler| PyValueError::new_err(format!("Export fehlgeschlagen: {fehler}")))
    }

    /// Löscht Einträge, die älter als `tage` Tage sind.
    fn loesche_aelter_als(&self, tage: i64) -> usize {
        self.innen.loesche_aelter_als(tage)
    }

    /// Löscht alle Einträge.
    fn leere(&self) {
        self.innen.leere();
    }
}

// ------------------------------------------------------------------ Bewertungen
/// Speicher der Antwortbewertungen (`data/bewertungen.json`).
#[pyclass(name = "BewertungsSpeicher")]
struct PyBewertungsSpeicher {
    innen: kern::BewertungsSpeicher,
}

#[pymethods]
impl PyBewertungsSpeicher {
    /// Legt den Speicher an; ohne Pfad wird `data/bewertungen.json` genutzt.
    #[new]
    #[pyo3(signature = (pfad=None))]
    fn neu(pfad: Option<PathBuf>) -> Self {
        let innen = match pfad {
            Some(pfad) => kern::BewertungsSpeicher::neu(&pfad),
            None => kern::BewertungsSpeicher::standardpfad(),
        };
        Self { innen }
    }

    /// Gibt den Dateipfad zurück.
    #[getter]
    fn pfad(&self) -> String {
        self.innen.pfad().to_string_lossy().to_string()
    }

    /// Gibt alle Bewertungen zurück.
    fn hole_alle<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.hole_alle())
    }

    /// Gibt die letzten `anzahl` Bewertungen zurück.
    #[pyo3(signature = (anzahl=10))]
    fn hole_letzte<'p>(&self, py: Python<'p>, anzahl: i64) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.hole_letzte(anzahl.max(0) as usize))
    }

    /// Fügt eine Bewertung hinzu und gibt sie zurück.
    fn fuege_hinzu<'p>(
        &self,
        py: Python<'p>,
        eintrag: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'p, PyAny>> {
        let gespeichert = self.innen.fuege_wert_hinzu(&nach_wert(eintrag)?);
        serde_nach_python(py, &gespeichert)
    }

    /// Gibt Kennzahlen über alle Bewertungen zurück.
    fn zusammenfassung<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.zusammenfassung())
    }

    /// Löscht alle Bewertungen.
    fn leere(&self) {
        self.innen.leere();
    }

    /// Gibt den Anzeigetext einer Bewertungszahl zurück.
    #[staticmethod]
    fn bewertungstext(bewertung: i32) -> String {
        kern::bewertungen::bewertungstext(bewertung).to_string()
    }
}

// ---------------------------------------------------------------------- Konten
/// Benutzerkonten samt Passwortprüfung (`data/users.json`).
#[pyclass(name = "Kontenverwaltung")]
struct PyKontenverwaltung {
    innen: kern::Kontenverwaltung,
}

#[pymethods]
impl PyKontenverwaltung {
    /// Legt die Verwaltung an; ohne Angaben gilt die Konfiguration.
    #[new]
    #[pyo3(signature = (pfad=None, standardbenutzer=None, standardpasswort=None, wechsel=None))]
    fn neu(
        pfad: Option<PathBuf>,
        standardbenutzer: Option<String>,
        standardpasswort: Option<String>,
        wechsel: Option<bool>,
    ) -> Self {
        let konfiguration = kern::Konfiguration::lade_standardpfad();
        let benutzer = standardbenutzer
            .unwrap_or_else(|| konfiguration.text(&["auth", "default_user"], "Admin"));
        let passwort = standardpasswort
            .unwrap_or_else(|| konfiguration.text(&["auth", "default_password"], "1234"));
        let wechsel = wechsel.unwrap_or_else(|| {
            konfiguration.wahrheitswert(&["auth", "force_password_change"], true)
        });
        let pfad = pfad_oder(pfad, kern::pfade::datendatei("users.json"));
        Self {
            innen: kern::Kontenverwaltung::neu(&pfad, &benutzer, &passwort, wechsel),
        }
    }

    /// Gibt den Dateipfad zurück.
    #[getter]
    fn pfad(&self) -> String {
        self.innen.pfad().to_string_lossy().to_string()
    }

    /// Gibt alle Konten zurück.
    fn lade_benutzer<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        let konten: Vec<Value> = self
            .innen
            .lade_benutzer()
            .iter()
            .map(konto_als_wert)
            .collect();
        nach_python(py, &Value::Array(konten))
    }

    /// Gibt ein einzelnes Konto zurück oder `None`.
    fn hole<'p>(&self, py: Python<'p>, benutzername: &str) -> PyResult<Bound<'p, PyAny>> {
        match self.innen.hole(benutzername) {
            Some(konto) => nach_python(py, &konto_als_wert(&konto)),
            None => Ok(py.None().into_bound(py)),
        }
    }

    /// Gibt die Namen aller Konten zurück.
    fn liste<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.liste())
    }

    /// Gibt die Anzahl der Konten zurück.
    fn anzahl(&self) -> usize {
        self.innen.anzahl()
    }

    /// Prüft, ob ein Konto Administratorrechte hat.
    fn ist_administrator(&self, benutzername: &str) -> bool {
        self.innen.ist_administrator(benutzername)
    }

    /// Prüft, ob das Passwort noch geändert werden muss.
    fn passwortwechsel_faellig(&self, benutzername: &str) -> bool {
        self.innen.passwortwechsel_faellig(benutzername)
    }

    /// Prüft die Anmeldung; gibt das Konto zurück oder `None`.
    fn pruefe_anmeldung<'p>(
        &self,
        py: Python<'p>,
        benutzername: &str,
        passwort: &str,
    ) -> PyResult<Bound<'p, PyAny>> {
        match self.innen.pruefe_anmeldung(benutzername, passwort) {
            Some(konto) => nach_python(py, &konto_als_wert(&konto)),
            None => Ok(py.None().into_bound(py)),
        }
    }

    /// Legt ein Konto an; bei Fehlern wird `ValueError` ausgelöst.
    #[pyo3(signature = (benutzername, passwort, rolle="benutzer", wechsel=false))]
    fn fuege_benutzer_hinzu<'p>(
        &self,
        py: Python<'p>,
        benutzername: &str,
        passwort: &str,
        rolle: &str,
        wechsel: bool,
    ) -> PyResult<Bound<'p, PyAny>> {
        let konto = self
            .innen
            .fuege_benutzer_hinzu(benutzername, passwort, rolle, wechsel)
            .map_err(PyValueError::new_err)?;
        nach_python(py, &konto_als_wert(&konto))
    }

    /// Löscht ein Konto; bei Fehlern wird `ValueError` ausgelöst.
    fn loesche_benutzer(&self, benutzername: &str) -> PyResult<()> {
        self.innen
            .loesche_benutzer(benutzername)
            .map_err(PyValueError::new_err)
    }

    /// Ändert das Passwort eines Kontos.
    #[pyo3(signature = (benutzername, passwort, wechsel=false))]
    fn aendere_passwort(&self, benutzername: &str, passwort: &str, wechsel: bool) -> PyResult<()> {
        self.innen
            .aendere_passwort(benutzername, passwort, wechsel)
            .map_err(PyValueError::new_err)
    }

    /// Ändert die Rolle eines Kontos.
    fn aendere_rolle(&self, benutzername: &str, rolle: &str) -> PyResult<()> {
        self.innen
            .aendere_rolle(benutzername, rolle)
            .map_err(PyValueError::new_err)
    }

    /// Ändert Benutzernamen und Passwort in einem Schritt.
    fn aendere_zugangsdaten<'p>(
        &self,
        py: Python<'p>,
        alter_name: &str,
        neuer_name: &str,
        neues_passwort: &str,
    ) -> PyResult<Bound<'p, PyAny>> {
        let konto = self
            .innen
            .aendere_zugangsdaten(alter_name, neuer_name, neues_passwort)
            .map_err(PyValueError::new_err)?;
        nach_python(py, &konto_als_wert(&konto))
    }

    /// Merkt, dass die erste Anmeldung erledigt ist.
    fn markiere_erstanmeldung_erledigt(&self, benutzername: &str) -> PyResult<()> {
        self.innen
            .markiere_erstanmeldung_erledigt(benutzername)
            .map_err(PyKeyError::new_err)
    }

    /// Gibt den Anzeigenamen einer Rolle zurück.
    #[staticmethod]
    fn rollenname(rolle: &str) -> String {
        kern::konten::rollenname(rolle)
    }
}

// ----------------------------------------------------------------- Checkpoints
/// Verwaltung der Checkpoint-Dateien (`data/checkpoints/`).
#[pyclass(name = "CheckpointOrdner")]
struct PyCheckpointOrdner {
    innen: kern::checkpoints::CheckpointOrdner,
}

#[pymethods]
impl PyCheckpointOrdner {
    /// Legt die Verwaltung an; ohne Pfad wird `data/checkpoints/` genutzt.
    #[new]
    #[pyo3(signature = (ordner=None))]
    fn neu(ordner: Option<PathBuf>) -> Self {
        let innen = match ordner {
            Some(ordner) => kern::checkpoints::CheckpointOrdner::neu(&ordner),
            None => kern::checkpoints::CheckpointOrdner::standardpfad(),
        };
        Self { innen }
    }

    /// Gibt den Ordnerpfad zurück.
    #[getter]
    fn ordner(&self) -> String {
        self.innen.ordner().to_string_lossy().to_string()
    }

    /// Listet alle Checkpoints, neueste zuerst.
    fn liste<'p>(&self, py: Python<'p>) -> PyResult<Bound<'p, PyAny>> {
        serde_nach_python(py, &self.innen.liste())
    }

    /// Löscht einen Checkpoint und meldet, ob das gelungen ist.
    fn loesche(&self, kennung: &str) -> bool {
        self.innen.loesche(kennung)
    }

    /// Gibt den Dateipfad eines Checkpoints zurück oder `None`.
    fn datei(&self, kennung: &str) -> Option<String> {
        self.innen
            .datei(kennung)
            .map(|pfad| pfad.to_string_lossy().to_string())
    }
}

// ------------------------------------------------------------------ Modulaufbau
/// Baut das Python-Modul `kimi3_kern` zusammen.
#[pymodule]
fn kimi3_kern(modul: &Bound<'_, PyModule>) -> PyResult<()> {
    modul.add("__doc__", "Rust-Kern des Kimi3-Projekts (Logik und Datenhaltung).")?;
    modul.add("VERSION", kern::VERSION)?;
    modul.add("MINDESTLAENGE_PASSWORT", kern::konten::MINDESTLAENGE_PASSWORT)?;

    modul.add_function(wrap_pyfunction!(projektordner, modul)?)?;
    modul.add_function(wrap_pyfunction!(datenordner, modul)?)?;
    modul.add_function(wrap_pyfunction!(datendatei, modul)?)?;
    modul.add_function(wrap_pyfunction!(jetzt_iso, modul)?)?;
    modul.add_function(wrap_pyfunction!(jetzt_lesbar, modul)?)?;
    modul.add_function(wrap_pyfunction!(kurzzeit, modul)?)?;
    modul.add_function(wrap_pyfunction!(lade_konfiguration, modul)?)?;
    modul.add_function(wrap_pyfunction!(richte_protokoll_ein, modul)?)?;
    modul.add_function(wrap_pyfunction!(protokolliere, modul)?)?;
    modul.add_function(wrap_pyfunction!(setze_protokollstufe, modul)?)?;
    modul.add_function(wrap_pyfunction!(protokollstufe, modul)?)?;
    modul.add_function(wrap_pyfunction!(erzeuge_passwort_hash, modul)?)?;
    modul.add_function(wrap_pyfunction!(pruefe_passwort, modul)?)?;
    modul.add_function(wrap_pyfunction!(berechne, modul)?)?;
    modul.add_function(wrap_pyfunction!(ergebnis_text, modul)?)?;

    modul.add_class::<PyEinstellungen>()?;
    modul.add_class::<PySchalter>()?;
    modul.add_class::<PyMetrikSpeicher>()?;
    modul.add_class::<PyBewertungsSpeicher>()?;
    modul.add_class::<PyKontenverwaltung>()?;
    modul.add_class::<PyCheckpointOrdner>()?;
    Ok(())
}
