//! Die vier globalen Schalter der Weboberfläche.
//!
//! 1. `bewertungsmodus`  – Antworten dürfen bewertet werden
//! 2. `zeige_diagramm`   – Metriken werden im Trainingsbereich gezeigt
//! 3. `schicht_training` – einzelne Schichten gezielt trainieren
//! 4. `auto_benchmarks`  – wiederkehrende Vergleichsläufe im Hintergrund
//!
//! Gespeichert wird wie bisher in `data/schalter.json`. Ältere Dateien mit
//! englischen Schlüsseln (`data/toggles.json`) werden weiterhin gelesen.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::path::{Path, PathBuf};

/// Stellung der vier Schalter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Schalter {
    /// Antworten dürfen bewertet werden.
    pub bewertungsmodus: bool,
    /// Metriken werden im Trainingsbereich angezeigt.
    pub zeige_diagramm: bool,
    /// Einzelne Schichten dürfen gezielt trainiert werden.
    pub schicht_training: bool,
    /// Wiederkehrende Vergleichsläufe im Hintergrund.
    pub auto_benchmarks: bool,
}

impl Default for Schalter {
    fn default() -> Self {
        Self {
            bewertungsmodus: false,
            zeige_diagramm: true,
            schicht_training: false,
            auto_benchmarks: false,
        }
    }
}

impl Schalter {
    /// Gibt den Wert eines Schalters über seinen Namen zurück.
    pub fn hole(&self, name: &str) -> Option<bool> {
        match Self::deutscher_name(name) {
            "bewertungsmodus" => Some(self.bewertungsmodus),
            "zeige_diagramm" => Some(self.zeige_diagramm),
            "schicht_training" => Some(self.schicht_training),
            "auto_benchmarks" => Some(self.auto_benchmarks),
            _ => None,
        }
    }

    /// Setzt einen Schalter über seinen Namen; gibt `false` bei unbekanntem Namen.
    pub fn setze(&mut self, name: &str, wert: bool) -> bool {
        match Self::deutscher_name(name) {
            "bewertungsmodus" => self.bewertungsmodus = wert,
            "zeige_diagramm" => self.zeige_diagramm = wert,
            "schicht_training" => self.schicht_training = wert,
            "auto_benchmarks" => self.auto_benchmarks = wert,
            _ => return false,
        }
        true
    }

    /// Übersetzt alte englische Schlüssel in die deutschen Namen.
    pub fn deutscher_name(name: &str) -> &str {
        match name {
            "rate_mode" => "bewertungsmodus",
            "show_graph" => "zeige_diagramm",
            "layer_training" => "schicht_training",
            anderer => anderer,
        }
    }

    /// Gibt die Schalter als JSON-Wörterbuch zurück.
    pub fn als_wert(&self) -> Value {
        let mut karte = Map::new();
        karte.insert("bewertungsmodus".into(), Value::Bool(self.bewertungsmodus));
        karte.insert("zeige_diagramm".into(), Value::Bool(self.zeige_diagramm));
        karte.insert("schicht_training".into(), Value::Bool(self.schicht_training));
        karte.insert("auto_benchmarks".into(), Value::Bool(self.auto_benchmarks));
        Value::Object(karte)
    }

    /// Übernimmt alle bekannten Schalter aus einem JSON-Wörterbuch.
    ///
    /// Rückgabe ist die Liste der übernommenen deutschen Namen.
    pub fn uebernimm(&mut self, daten: &Value) -> Vec<String> {
        let mut geaendert = Vec::new();
        if let Some(karte) = daten.as_object() {
            for (schluessel, wert) in karte {
                let name = Self::deutscher_name(schluessel).to_string();
                let wahrheit = match wert {
                    Value::Bool(bool_wert) => *bool_wert,
                    Value::Number(zahl) => zahl.as_f64().unwrap_or(0.0) != 0.0,
                    Value::String(text) => !text.is_empty() && text != "false" && text != "0",
                    Value::Null => false,
                    _ => true,
                };
                if self.setze(&name, wahrheit) {
                    geaendert.push(name);
                }
            }
        }
        geaendert
    }
}

/// Liest und schreibt die Schalterstellungen.
#[derive(Debug, Clone)]
pub struct SchalterSpeicher {
    pfad: PathBuf,
    alter_pfad: Option<PathBuf>,
}

impl SchalterSpeicher {
    /// Öffnet den Speicher unter dem angegebenen Pfad.
    pub fn neu(pfad: &Path) -> Self {
        Self {
            pfad: pfad.to_path_buf(),
            alter_pfad: pfad.parent().map(|ordner| ordner.join("toggles.json")),
        }
    }

    /// Öffnet den Speicher unter `data/schalter.json` des Projekts.
    pub fn standardpfad() -> Self {
        Self::neu(&crate::pfade::datendatei("schalter.json"))
    }

    /// Gibt den Pfad der Schalterdatei zurück.
    pub fn pfad(&self) -> &Path {
        &self.pfad
    }

    /// Liest die Schalterstellungen; fehlende Werte bleiben auf Standard.
    pub fn lade(&self) -> Schalter {
        let mut schalter = Schalter::default();
        let mut quellen = vec![self.pfad.clone()];
        quellen.extend(self.alter_pfad.clone());
        for pfad in quellen {
            let Ok(inhalt) = std::fs::read_to_string(&pfad) else {
                continue;
            };
            if let Ok(wert) = serde_json::from_str::<Value>(&inhalt) {
                schalter.uebernimm(&wert);
            }
            // Wie bisher wird nur die erste vorhandene Datei ausgewertet.
            break;
        }
        schalter
    }

    /// Schreibt die Schalterstellungen auf die Festplatte.
    pub fn speichere(&self, schalter: &Schalter) {
        if let Ok(text) = serde_json::to_string_pretty(&schalter.als_wert()) {
            let _ = crate::pfade::schreibe_atomar(&self.pfad, &text);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn standardstellung_entspricht_der_python_fassung() {
        let schalter = Schalter::default();
        assert!(!schalter.bewertungsmodus);
        assert!(schalter.zeige_diagramm);
        assert!(!schalter.schicht_training);
        assert!(!schalter.auto_benchmarks);
    }

    #[test]
    fn englische_schluessel_werden_uebernommen() {
        let mut schalter = Schalter::default();
        let geaendert = schalter.uebernimm(&json!({
            "rate_mode": true, "show_graph": false, "layer_training": true,
            "unbekannt": true
        }));
        assert!(schalter.bewertungsmodus);
        assert!(!schalter.zeige_diagramm);
        assert!(schalter.schicht_training);
        assert_eq!(geaendert.len(), 3);
    }

    #[test]
    fn speichern_und_laden_ergibt_dieselbe_stellung() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let speicher = SchalterSpeicher::neu(&ordner.path().join("data/schalter.json"));
        let mut schalter = Schalter::default();
        schalter.setze("schicht_training", true);
        schalter.setze("zeige_diagramm", false);
        speicher.speichere(&schalter);
        assert_eq!(speicher.lade(), schalter);
    }

    #[test]
    fn alte_datei_wird_gelesen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        std::fs::create_dir_all(ordner.path().join("data")).expect("Ordner");
        std::fs::write(
            ordner.path().join("data/toggles.json"),
            "{\"rate_mode\": true, \"show_graph\": false}",
        )
        .expect("schreiben");
        let speicher = SchalterSpeicher::neu(&ordner.path().join("data/schalter.json"));
        let schalter = speicher.lade();
        assert!(schalter.bewertungsmodus);
        assert!(!schalter.zeige_diagramm);
    }

    #[test]
    fn defekte_datei_ergibt_standardstellung() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("schalter.json");
        std::fs::write(&pfad, "kein JSON").expect("schreiben");
        assert_eq!(SchalterSpeicher::neu(&pfad).lade(), Schalter::default());
    }
}
