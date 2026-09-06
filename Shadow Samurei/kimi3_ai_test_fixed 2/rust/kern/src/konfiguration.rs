//! Liest `config.yaml` (oder eine JSON-Datei) und ergänzt fehlende Werte.
//!
//! Die Standardwerte entsprechen genau der bisherigen Python-Fassung
//! (`config_loader.DEFAULT_CONFIG`). Fehlt die Datei oder ist sie defekt,
//! gelten die Standardwerte und es erscheint ein deutscher Hinweis.

use serde_json::{json, Map, Value};
use std::path::Path;

/// Die Konfiguration des Programms.
#[derive(Debug, Clone, PartialEq)]
pub struct Konfiguration {
    werte: Value,
}

/// Gibt die eingebauten Standardwerte zurück.
pub fn standardwerte() -> Value {
    json!({
        "logging": {"level": "INFO", "colored": true, "log_file": null},
        "hardware": {"device": "auto", "use_4bit": true, "use_fp16": true, "weights_dtype": "fp32"},
        "model": {"name": "meta-llama/Meta-Llama-3-8B-Instruct", "max_tool_iterations": 5},
        "training": {
            "output_dir": "./tool_model", "batch_size": 1,
            "gradient_accumulation_steps": 8, "num_epochs": 3,
            "learning_rate": 2e-4, "max_length": 2048
        },
        "auth": {"default_user": "Admin", "default_password": "1234", "force_password_change": true},
        "oberflaeche": {"erscheinungsbild": "System", "farbschema": "kimi"}
    })
}

/// Führt zwei Wörterbücher tief zusammen; `ueberschreibung` gewinnt.
pub fn tiefe_zusammenfuehrung(basis: &mut Value, ueberschreibung: &Value) {
    let (Some(ziel), Some(quelle)) = (basis.as_object_mut(), ueberschreibung.as_object()) else {
        *basis = ueberschreibung.clone();
        return;
    };
    for (schluessel, wert) in quelle {
        match ziel.get_mut(schluessel) {
            Some(vorhanden) if vorhanden.is_object() && wert.is_object() => {
                tiefe_zusammenfuehrung(vorhanden, wert);
            }
            _ => {
                ziel.insert(schluessel.clone(), wert.clone());
            }
        }
    }
}

impl Default for Konfiguration {
    fn default() -> Self {
        Self {
            werte: standardwerte(),
        }
    }
}

impl Konfiguration {
    /// Lädt die Konfiguration aus einer Datei.
    ///
    /// Die Meldungen entsprechen der Python-Fassung, damit sich das
    /// Verhalten beim Start nicht ändert.
    pub fn lade(pfad: &Path) -> Self {
        let mut werte = standardwerte();
        if !pfad.exists() {
            println!(
                "[INFO] {} nicht gefunden, nutze Standardwerte.",
                pfad.display()
            );
            return Self { werte };
        }
        let endung = pfad
            .extension()
            .map(|wert| wert.to_string_lossy().to_lowercase())
            .unwrap_or_default();
        let inhalt = match std::fs::read_to_string(pfad) {
            Ok(text) => text,
            Err(fehler) => {
                println!(
                    "[WARNUNG] {} konnte nicht gelesen werden ({fehler}), nutze Standardwerte.",
                    pfad.display()
                );
                return Self { werte };
            }
        };
        let gelesen: Result<Value, String> = match endung.as_str() {
            "yaml" | "yml" => serde_yaml::from_str::<Value>(&inhalt)
                .map(|wert| if wert.is_null() { json!({}) } else { wert })
                .map_err(|fehler| fehler.to_string()),
            "json" => serde_json::from_str::<Value>(&inhalt).map_err(|fehler| fehler.to_string()),
            _ => return Self { werte },
        };
        match gelesen {
            Ok(eigene) => tiefe_zusammenfuehrung(&mut werte, &eigene),
            Err(fehler) => println!(
                "[WARNUNG] {} konnte nicht gelesen werden ({fehler}), nutze Standardwerte.",
                pfad.display()
            ),
        }
        Self { werte }
    }

    /// Lädt die Konfiguration aus `config.yaml` des Projektordners.
    pub fn lade_standardpfad() -> Self {
        Self::lade(&crate::pfade::projektordner().join("config.yaml"))
    }

    /// Erzeugt eine Konfiguration aus einem bereits gelesenen Wert.
    pub fn aus_wert(eigene: &Value) -> Self {
        let mut werte = standardwerte();
        tiefe_zusammenfuehrung(&mut werte, eigene);
        Self { werte }
    }

    /// Gibt die gesamte Konfiguration zurück.
    pub fn wert(&self) -> &Value {
        &self.werte
    }

    /// Gibt einen Abschnitt zurück, zum Beispiel `logging`.
    pub fn abschnitt(&self, name: &str) -> Map<String, Value> {
        self.werte
            .get(name)
            .and_then(|wert| wert.as_object())
            .cloned()
            .unwrap_or_default()
    }

    /// Gibt einen Wert über seinen Pfad zurück, etwa `["auth", "default_user"]`.
    pub fn hole(&self, pfad: &[&str]) -> Option<&Value> {
        let mut aktuell = &self.werte;
        for teil in pfad {
            aktuell = aktuell.get(*teil)?;
        }
        Some(aktuell)
    }

    /// Gibt einen Text zurück oder den Ersatzwert.
    pub fn text(&self, pfad: &[&str], ersatz: &str) -> String {
        match self.hole(pfad).and_then(|wert| wert.as_str()) {
            Some(text) if !text.is_empty() => text.to_string(),
            _ => ersatz.to_string(),
        }
    }

    /// Gibt einen Wahrheitswert zurück oder den Ersatzwert.
    pub fn wahrheitswert(&self, pfad: &[&str], ersatz: bool) -> bool {
        self.hole(pfad)
            .and_then(|wert| wert.as_bool())
            .unwrap_or(ersatz)
    }

    /// Gibt eine Zahl zurück oder den Ersatzwert.
    pub fn zahl(&self, pfad: &[&str], ersatz: f64) -> f64 {
        self.hole(pfad)
            .and_then(|wert| wert.as_f64())
            .unwrap_or(ersatz)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn schreibe(name: &str, inhalt: &str) -> (tempfile::TempDir, std::path::PathBuf) {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join(name);
        let mut datei = std::fs::File::create(&pfad).expect("anlegen");
        datei.write_all(inhalt.as_bytes()).expect("schreiben");
        (ordner, pfad)
    }

    #[test]
    fn fehlende_datei_ergibt_standardwerte() {
        let konfiguration = Konfiguration::lade(Path::new("/gibt/es/nicht.yaml"));
        assert_eq!(konfiguration.text(&["auth", "default_user"], ""), "Admin");
        assert!(konfiguration.wahrheitswert(&["auth", "force_password_change"], false));
    }

    #[test]
    fn yaml_wird_tief_zusammengefuehrt() {
        let (_ordner, pfad) = schreibe(
            "config.yaml",
            "auth:\n  default_user: Chef\nmodel:\n  max_tool_iterations: 9\n",
        );
        let konfiguration = Konfiguration::lade(&pfad);
        assert_eq!(konfiguration.text(&["auth", "default_user"], ""), "Chef");
        // Nicht genannte Werte des Abschnitts bleiben erhalten.
        assert_eq!(konfiguration.text(&["auth", "default_password"], ""), "1234");
        assert_eq!(konfiguration.zahl(&["model", "max_tool_iterations"], 0.0), 9.0);
    }

    #[test]
    fn defekte_datei_ergibt_standardwerte() {
        let (_ordner, pfad) = schreibe("config.yaml", "auth: [unvollständig\n");
        let konfiguration = Konfiguration::lade(&pfad);
        assert_eq!(konfiguration.text(&["auth", "default_user"], ""), "Admin");
    }

    #[test]
    fn json_wird_ebenfalls_gelesen() {
        let (_ordner, pfad) = schreibe("config.json", "{\"logging\": {\"level\": \"DEBUG\"}}");
        let konfiguration = Konfiguration::lade(&pfad);
        assert_eq!(konfiguration.text(&["logging", "level"], ""), "DEBUG");
        assert!(konfiguration.wahrheitswert(&["logging", "colored"], false));
    }

    #[test]
    fn abschnitt_gibt_alle_werte() {
        let konfiguration = Konfiguration::default();
        let abschnitt = konfiguration.abschnitt("oberflaeche");
        assert_eq!(abschnitt.get("erscheinungsbild").and_then(Value::as_str), Some("System"));
    }
}
