//! Dauerhafte Anwendungseinstellungen in `data/settings.json`.
//!
//! Format und Standardwerte entsprechen der bisherigen Python-Fassung
//! (`settings_store.py`), damit vorhandene Dateien weiter gelten.

use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

/// Standardwerte für alle Einstellungen.
pub fn standardwerte() -> Map<String, Value> {
    let werte = json!({
        "erscheinungsbild": "System",
        "farbschema": "blue",
        "fenstergroesse": "1180x860",
        "letzter_benutzer": "",
        "widget_skalierung": 1.0
    });
    werte.as_object().cloned().unwrap_or_default()
}

/// Kleiner, thread-sicherer Einstellungsspeicher auf JSON-Basis.
#[derive(Debug)]
pub struct Einstellungen {
    pfad: PathBuf,
    werte: Mutex<Map<String, Value>>,
}

impl Einstellungen {
    /// Öffnet den Speicher unter dem angegebenen Pfad.
    pub fn neu(pfad: &Path) -> Self {
        let mut werte = standardwerte();
        if let Ok(inhalt) = std::fs::read_to_string(pfad) {
            if let Ok(Value::Object(gespeichert)) = serde_json::from_str::<Value>(&inhalt) {
                for (schluessel, wert) in gespeichert {
                    werte.insert(schluessel, wert);
                }
            }
        }
        Self {
            pfad: pfad.to_path_buf(),
            werte: Mutex::new(werte),
        }
    }

    /// Öffnet den Speicher unter `data/settings.json` des Projekts.
    pub fn standardpfad() -> Self {
        Self::neu(&crate::pfade::datendatei("settings.json"))
    }

    /// Gibt den Pfad der Einstellungsdatei zurück.
    pub fn pfad(&self) -> &Path {
        &self.pfad
    }

    /// Schreibt die Einstellungen auf die Festplatte.
    fn speichere(&self, werte: &Map<String, Value>) {
        if let Ok(text) = serde_json::to_string_pretty(werte) {
            let _ = crate::pfade::schreibe_atomar(&self.pfad, &text);
        }
    }

    /// Gibt einen Wert zurück; fehlt er, gilt der Standardwert.
    pub fn hole(&self, schluessel: &str) -> Value {
        let gesperrt = self.werte.lock();
        let vorhanden = gesperrt
            .as_ref()
            .ok()
            .and_then(|werte| werte.get(schluessel).cloned());
        vorhanden
            .or_else(|| standardwerte().get(schluessel).cloned())
            .unwrap_or(Value::Null)
    }

    /// Gibt einen Wert als Text zurück.
    pub fn text(&self, schluessel: &str, ersatz: &str) -> String {
        match self.hole(schluessel) {
            Value::String(text) => {
                if text.is_empty() {
                    ersatz.to_string()
                } else {
                    text
                }
            }
            Value::Null => ersatz.to_string(),
            anderer => {
                let text = anderer.to_string();
                if text.is_empty() {
                    ersatz.to_string()
                } else {
                    text
                }
            }
        }
    }

    /// Setzt einen Wert und speichert ihn sofort.
    pub fn setze(&self, schluessel: &str, wert: Value) {
        let kopie = {
            let mut gesperrt = match self.werte.lock() {
                Ok(werte) => werte,
                Err(_) => return,
            };
            gesperrt.insert(schluessel.to_string(), wert);
            gesperrt.clone()
        };
        self.speichere(&kopie);
    }

    /// Gibt eine Kopie aller Einstellungen zurück.
    pub fn alle(&self) -> Map<String, Value> {
        self.werte.lock().map(|werte| werte.clone()).unwrap_or_default()
    }

    /// Liest die gespeicherte Fenstergröße als Zahlenpaar.
    ///
    /// Die Untergrenzen (900 × 620) entsprechen der Python-Fassung.
    pub fn fenstergroesse(&self, breite: u32, hoehe: u32) -> (u32, u32) {
        let wert = self.text("fenstergroesse", &format!("{breite}x{hoehe}"));
        let vorne = wert.split('+').next().unwrap_or("").to_lowercase();
        let mut teile = vorne.split('x');
        let gelesen = (
            teile.next().and_then(|text| text.trim().parse::<u32>().ok()),
            teile.next().and_then(|text| text.trim().parse::<u32>().ok()),
        );
        match gelesen {
            (Some(b), Some(h)) => (b.max(900), h.max(620)),
            _ => (breite, hoehe),
        }
    }

    /// Speichert die aktuelle Fenstergröße.
    pub fn setze_fenstergroesse(&self, breite: u32, hoehe: u32) {
        if breite > 200 && hoehe > 200 {
            self.setze("fenstergroesse", Value::String(format!("{breite}x{hoehe}")));
        }
    }

    /// Stellt alle Standardwerte wieder her.
    pub fn zuruecksetzen(&self) {
        let standard = standardwerte();
        if let Ok(mut gesperrt) = self.werte.lock() {
            *gesperrt = standard.clone();
        }
        self.speichere(&standard);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn speicher() -> (tempfile::TempDir, Einstellungen) {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("data/settings.json");
        (ordner.into(), Einstellungen::neu(&pfad))
    }

    #[test]
    fn standardwerte_gelten_ohne_datei() {
        let (_ordner, einstellungen) = speicher();
        assert_eq!(einstellungen.text("erscheinungsbild", ""), "System");
        assert_eq!(einstellungen.fenstergroesse(1180, 860), (1180, 860));
    }

    #[test]
    fn werte_ueberleben_das_neuladen() {
        let (_ordner, einstellungen) = speicher();
        einstellungen.setze("erscheinungsbild", Value::String("Dunkel".into()));
        einstellungen.setze_fenstergroesse(1400, 900);
        let erneut = Einstellungen::neu(einstellungen.pfad());
        assert_eq!(erneut.text("erscheinungsbild", ""), "Dunkel");
        assert_eq!(erneut.fenstergroesse(1180, 860), (1400, 900));
    }

    #[test]
    fn zu_kleine_fenster_werden_angehoben() {
        let (_ordner, einstellungen) = speicher();
        einstellungen.setze("fenstergroesse", Value::String("640x480".into()));
        assert_eq!(einstellungen.fenstergroesse(1180, 860), (900, 620));
    }

    #[test]
    fn unsinnige_angaben_ergeben_den_ersatzwert() {
        let (_ordner, einstellungen) = speicher();
        einstellungen.setze("fenstergroesse", Value::String("viel mal wenig".into()));
        assert_eq!(einstellungen.fenstergroesse(1180, 860), (1180, 860));
    }

    #[test]
    fn defekte_datei_wird_uebergangen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("settings.json");
        std::fs::write(&pfad, "{kein gültiges JSON").expect("schreiben");
        let einstellungen = Einstellungen::neu(&pfad);
        assert_eq!(einstellungen.text("farbschema", ""), "blue");
    }

    #[test]
    fn zuruecksetzen_stellt_standard_wieder_her() {
        let (_ordner, einstellungen) = speicher();
        einstellungen.setze("letzter_benutzer", Value::String("Chef".into()));
        einstellungen.zuruecksetzen();
        assert_eq!(einstellungen.text("letzter_benutzer", "leer"), "leer");
    }
}
