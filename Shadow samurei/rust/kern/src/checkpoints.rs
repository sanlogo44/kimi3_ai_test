//! Verwaltung der Checkpoint-Dateien in `data/checkpoints/`.
//!
//! Die Dateien selbst schreibt und liest der Modellkern in Python
//! (PyTorch). Hier stehen nur die Aufgaben, die ohne PyTorch möglich
//! sind: die Liste aus den Dateinamen lesen und Dateien löschen. Genau
//! das hat bisher `app.checkpoints_aus_dateinamen()` getan.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use crate::zeit;

/// Ein gespeicherter Checkpoint.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct Checkpoint {
    /// Kennung, also der Teil des Dateinamens vor dem ersten Unterstrich.
    pub kennung: String,
    /// Anzeigename.
    pub name: String,
    /// Genauigkeit, sofern bekannt.
    pub genauigkeit: Option<f64>,
    /// Zeitpunkt der Speicherung.
    pub gespeichert_am: String,
}

impl Checkpoint {
    /// Liest einen Checkpoint aus – auch alten – JSON-Daten.
    pub fn aus_wert(daten: &Value) -> Self {
        let text = |deutsch: &str, englisch: &str| -> String {
            match daten.get(deutsch).or_else(|| daten.get(englisch)) {
                Some(Value::String(wert)) if !wert.is_empty() => wert.clone(),
                Some(Value::Null) | None => String::new(),
                Some(anderer) => anderer.to_string(),
            }
        };
        let kennung = text("kennung", "id");
        let name = text("name", "kennung");
        let genauigkeit = daten
            .get("genauigkeit")
            .or_else(|| daten.get("accuracy"))
            .and_then(Value::as_f64);
        Self {
            name: if name.is_empty() {
                if kennung.is_empty() {
                    "unbenannt".to_string()
                } else {
                    kennung.clone()
                }
            } else {
                name
            },
            kennung,
            genauigkeit,
            gespeichert_am: text("gespeichert_am", "saved_at"),
        }
    }

    /// Gibt den Checkpoint als JSON-Wert mit deutschen **und** alten
    /// englischen Schlüsseln zurück, wie die Weboberfläche sie liefert.
    pub fn als_wert(&self) -> Value {
        let genauigkeit = match self.genauigkeit {
            Some(wert) => serde_json::json!(wert),
            None => Value::Null,
        };
        let mut karte = Map::new();
        karte.insert("kennung".into(), Value::String(self.kennung.clone()));
        karte.insert("id".into(), Value::String(self.kennung.clone()));
        karte.insert("name".into(), Value::String(self.name.clone()));
        karte.insert("genauigkeit".into(), genauigkeit.clone());
        karte.insert("accuracy".into(), genauigkeit);
        karte.insert(
            "gespeichert_am".into(),
            Value::String(self.gespeichert_am.clone()),
        );
        karte.insert(
            "saved_at".into(),
            Value::String(self.gespeichert_am.clone()),
        );
        Value::Object(karte)
    }

    /// Gibt die Genauigkeit als Text in Prozent zurück.
    pub fn genauigkeit_text(&self) -> String {
        match self.genauigkeit {
            Some(wert) => format!("{:.1} %", wert * 100.0),
            None => "-".to_string(),
        }
    }
}

/// Verwaltet den Ordner mit den Checkpoint-Dateien.
#[derive(Debug, Clone)]
pub struct CheckpointOrdner {
    ordner: PathBuf,
}

impl CheckpointOrdner {
    /// Öffnet die Verwaltung für den angegebenen Ordner.
    pub fn neu(ordner: &Path) -> Self {
        Self {
            ordner: ordner.to_path_buf(),
        }
    }

    /// Öffnet die Verwaltung für `data/checkpoints/` des Projekts.
    pub fn standardpfad() -> Self {
        Self::neu(&crate::pfade::datenordner().join("checkpoints"))
    }

    /// Gibt den Ordner zurück.
    pub fn ordner(&self) -> &Path {
        &self.ordner
    }

    /// Liest die Checkpoint-Liste allein aus den Dateinamen.
    ///
    /// Die Zusatzdaten stecken in den Dateien selbst und lassen sich ohne
    /// PyTorch nicht lesen, der Name und der Zeitpunkt aber schon.
    pub fn liste(&self) -> Vec<Checkpoint> {
        let Ok(eintraege) = std::fs::read_dir(&self.ordner) else {
            return Vec::new();
        };
        let mut dateinamen: Vec<String> = eintraege
            .filter_map(Result::ok)
            .map(|eintrag| eintrag.file_name().to_string_lossy().to_string())
            .filter(|name| name.ends_with(".pt"))
            .collect();
        dateinamen.sort();
        dateinamen
            .into_iter()
            .map(|datei| {
                let rumpf = datei.trim_end_matches(".pt");
                let (kennung, name) = match rumpf.split_once('_') {
                    Some((kennung, rest)) => (kennung.to_string(), rest.replace('_', " ")),
                    None => (rumpf.to_string(), String::new()),
                };
                let gespeichert_am = std::fs::metadata(self.ordner.join(&datei))
                    .and_then(|angaben| angaben.modified())
                    .ok()
                    .and_then(|zeitpunkt| zeitpunkt.duration_since(UNIX_EPOCH).ok())
                    .map(|dauer| zeit::aus_sekunden(dauer.as_secs() as i64))
                    .unwrap_or_default();
                Checkpoint {
                    name: if name.is_empty() {
                        kennung.clone()
                    } else {
                        name
                    },
                    kennung,
                    genauigkeit: None,
                    gespeichert_am,
                }
            })
            .collect()
    }

    /// Löscht alle Dateien mit der angegebenen Kennung.
    ///
    /// Gibt `true` zurück, wenn mindestens eine Datei gelöscht wurde.
    pub fn loesche(&self, kennung: &str) -> bool {
        if kennung.is_empty() {
            return false;
        }
        let Ok(eintraege) = std::fs::read_dir(&self.ordner) else {
            return false;
        };
        let mut geloescht = false;
        let anfang = format!("{kennung}_");
        for eintrag in eintraege.filter_map(Result::ok) {
            let name = eintrag.file_name().to_string_lossy().to_string();
            if name.starts_with(&anfang) && name.ends_with(".pt") {
                geloescht |= std::fs::remove_file(eintrag.path()).is_ok();
            }
        }
        geloescht
    }

    /// Gibt den Pfad zur Datei einer Kennung zurück, falls vorhanden.
    pub fn datei(&self, kennung: &str) -> Option<PathBuf> {
        let anfang = format!("{kennung}_");
        std::fs::read_dir(&self.ordner)
            .ok()?
            .filter_map(Result::ok)
            .map(|eintrag| eintrag.path())
            .filter(|pfad| {
                let name = pfad
                    .file_name()
                    .map(|name| name.to_string_lossy().to_string())
                    .unwrap_or_default();
                name.starts_with(&anfang) && name.ends_with(".pt")
            })
            .min()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn ordner_mit_dateien() -> (tempfile::TempDir, CheckpointOrdner) {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("data/checkpoints");
        std::fs::create_dir_all(&pfad).expect("Ordner");
        std::fs::write(pfad.join("abc123_Mein_Lauf.pt"), b"x").expect("Datei");
        std::fs::write(pfad.join("def456_Zweiter.pt"), b"x").expect("Datei");
        std::fs::write(pfad.join("liesmich.txt"), b"x").expect("Datei");
        (ordner, CheckpointOrdner::neu(&pfad))
    }

    #[test]
    fn liste_liest_nur_pt_dateien() {
        let (_ordner, verwaltung) = ordner_mit_dateien();
        let liste = verwaltung.liste();
        assert_eq!(liste.len(), 2);
        assert_eq!(liste[0].kennung, "abc123");
        assert_eq!(liste[0].name, "Mein Lauf");
        assert_eq!(liste[1].name, "Zweiter");
        assert_eq!(liste[0].gespeichert_am.len(), 19);
        assert_eq!(liste[0].genauigkeit_text(), "-");
    }

    #[test]
    fn fehlender_ordner_ergibt_leere_liste() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let verwaltung = CheckpointOrdner::neu(&ordner.path().join("gibt-es-nicht"));
        assert!(verwaltung.liste().is_empty());
        assert!(!verwaltung.loesche("abc"));
    }

    #[test]
    fn loeschen_entfernt_nur_die_kennung() {
        let (_ordner, verwaltung) = ordner_mit_dateien();
        assert!(verwaltung.datei("abc123").is_some());
        assert!(verwaltung.loesche("abc123"));
        assert_eq!(verwaltung.liste().len(), 1);
        assert!(!verwaltung.loesche("abc123"));
        assert!(!verwaltung.loesche(""));
        assert!(verwaltung.datei("abc123").is_none());
    }

    #[test]
    fn dateiname_ohne_unterstrich_wird_zum_namen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("checkpoints");
        std::fs::create_dir_all(&pfad).expect("Ordner");
        std::fs::write(pfad.join("einzeln.pt"), b"x").expect("Datei");
        let liste = CheckpointOrdner::neu(&pfad).liste();
        assert_eq!(liste[0].kennung, "einzeln");
        assert_eq!(liste[0].name, "einzeln");
    }

    #[test]
    fn json_wird_mit_alten_schluesseln_gelesen_und_geschrieben() {
        let punkt = Checkpoint::aus_wert(&json!({
            "id": "xyz", "accuracy": 0.815, "saved_at": "2026-01-01 10:00:00"
        }));
        assert_eq!(punkt.kennung, "xyz");
        assert_eq!(punkt.name, "xyz");
        assert_eq!(punkt.genauigkeit, Some(0.815));
        assert_eq!(punkt.genauigkeit_text(), "81.5 %");
        let wert = punkt.als_wert();
        assert_eq!(wert["kennung"], json!("xyz"));
        assert_eq!(wert["id"], json!("xyz"));
        assert_eq!(wert["accuracy"], json!(0.815));
        assert_eq!(wert["saved_at"], json!("2026-01-01 10:00:00"));
    }

    #[test]
    fn leere_daten_ergeben_unbenannt() {
        let punkt = Checkpoint::aus_wert(&json!({}));
        assert_eq!(punkt.name, "unbenannt");
        assert!(punkt.kennung.is_empty());
        assert_eq!(punkt.genauigkeit, None);
    }
}
