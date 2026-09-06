//! Bewertungen einzelner Antworten in `data/bewertungen.json`.
//!
//! Eine Bewertung ist `1` (hilfreich), `-1` (nicht hilfreich) oder `0`
//! (ohne Bewertung). Alte Dateien (`data/feedback.json`) und alte
//! englische Feldnamen werden weiterhin gelesen.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};

use crate::zeit;

/// Längste gespeicherte Text­länge für Frage und Antwort.
const HOECHSTLAENGE_TEXT: usize = 1000;

/// Gibt den Anzeigetext einer Bewertung zurück.
pub fn bewertungstext(bewertung: i32) -> &'static str {
    match bewertung {
        1 => "Hilfreich",
        -1 => "Nicht hilfreich",
        _ => "Ohne Bewertung",
    }
}

/// Kürzt einen Text auf die Höchstlänge.
fn kuerze(text: &str) -> String {
    if text.chars().count() <= HOECHSTLAENGE_TEXT {
        text.to_string()
    } else {
        text.chars().take(HOECHSTLAENGE_TEXT).collect()
    }
}

/// Eine einzelne Bewertung.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BewertungsEintrag {
    /// Zeitstempel im ISO-Format.
    pub zeitstempel: String,
    /// Modell, das die Antwort erzeugt hat.
    pub modell: String,
    /// Gestellte Frage.
    pub frage: String,
    /// Gegebene Antwort.
    pub antwort: String,
    /// Bewertung: 1, -1 oder 0.
    pub bewertung: i32,
    /// Freie Markierungen.
    pub markierungen: Vec<String>,
}

impl Default for BewertungsEintrag {
    fn default() -> Self {
        Self {
            zeitstempel: zeit::jetzt_iso(),
            modell: "unbekannt".into(),
            frage: String::new(),
            antwort: String::new(),
            bewertung: 0,
            markierungen: Vec::new(),
        }
    }
}

impl BewertungsEintrag {
    /// Erzeugt einen Eintrag; die Texte werden gekürzt.
    pub fn neu(modell: &str, frage: &str, antwort: &str, bewertung: i32) -> Self {
        Self {
            zeitstempel: zeit::jetzt_iso(),
            modell: if modell.is_empty() {
                "unbekannt".to_string()
            } else {
                modell.to_string()
            },
            frage: kuerze(frage),
            antwort: kuerze(antwort),
            bewertung: bewertung.clamp(-1, 1),
            markierungen: Vec::new(),
        }
    }

    /// Liest einen Eintrag aus – auch alten – JSON-Daten.
    pub fn aus_wert(daten: &Value) -> Self {
        let text = |deutsch: &str, englisch: &str, ersatz: &str| -> String {
            match daten.get(deutsch).or_else(|| daten.get(englisch)) {
                Some(Value::String(wert)) if !wert.is_empty() => wert.clone(),
                Some(Value::Null) | None => ersatz.to_string(),
                Some(anderer) => anderer.to_string(),
            }
        };
        let bewertung = match daten.get("bewertung").or_else(|| daten.get("rating")) {
            Some(Value::Number(zahl)) => zahl.as_f64().unwrap_or(0.0) as i32,
            Some(Value::String(wert)) => wert.trim().parse::<i32>().unwrap_or(0),
            Some(Value::Bool(true)) => 1,
            _ => 0,
        };
        let markierungen = match daten.get("markierungen").or_else(|| daten.get("tags")) {
            Some(Value::Array(liste)) => liste
                .iter()
                .map(|wert| match wert {
                    Value::String(text) => text.clone(),
                    anderer => anderer.to_string(),
                })
                .collect(),
            Some(Value::String(einzel)) if !einzel.is_empty() => vec![einzel.clone()],
            _ => Vec::new(),
        };
        let zeitstempel = {
            let gelesen = text("zeitstempel", "ts", "");
            if gelesen.is_empty() {
                zeit::jetzt_iso()
            } else {
                gelesen
            }
        };
        Self {
            zeitstempel,
            modell: text("modell", "model", "unbekannt"),
            frage: kuerze(&text("frage", "prompt", "")),
            antwort: kuerze(&text("antwort", "response", "")),
            bewertung: bewertung.clamp(-1, 1),
            markierungen,
        }
    }

    /// Gibt den Eintrag als JSON-Wert zurück.
    pub fn als_wert(&self) -> Value {
        serde_json::to_value(self).unwrap_or(Value::Null)
    }

    /// Gibt den Anzeigetext der Bewertung zurück.
    pub fn text(&self) -> &'static str {
        bewertungstext(self.bewertung)
    }

    /// Gibt eine kurze, lesbare Zeitangabe zurück.
    pub fn kurzzeit(&self) -> String {
        zeit::kurzzeit(&self.zeitstempel)
    }
}

/// Kennzahlen über alle Bewertungen.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct BewertungsZusammenfassung {
    /// Anzahl aller Bewertungen.
    pub gesamt: usize,
    /// Anzahl der hilfreichen Bewertungen.
    pub positiv: usize,
    /// Anzahl der nicht hilfreichen Bewertungen.
    pub negativ: usize,
    /// Anzahl der Einträge ohne Bewertung.
    pub neutral: usize,
    /// Anteil hilfreicher Bewertungen zwischen 0 und 1.
    pub anteil: f64,
}

/// Speichert und wertet Bewertungen aus.
#[derive(Debug, Clone)]
pub struct BewertungsSpeicher {
    pfad: PathBuf,
    alter_pfad: Option<PathBuf>,
}

impl BewertungsSpeicher {
    /// Öffnet den Speicher unter dem angegebenen Pfad.
    pub fn neu(pfad: &Path) -> Self {
        Self {
            pfad: pfad.to_path_buf(),
            alter_pfad: pfad.parent().map(|ordner| ordner.join("feedback.json")),
        }
    }

    /// Öffnet den Speicher unter `data/bewertungen.json` des Projekts.
    pub fn standardpfad() -> Self {
        Self::neu(&crate::pfade::datendatei("bewertungen.json"))
    }

    /// Gibt den Pfad der Bewertungsdatei zurück.
    pub fn pfad(&self) -> &Path {
        &self.pfad
    }

    /// Gibt alle Bewertungen zurück.
    pub fn hole_alle(&self) -> Vec<BewertungsEintrag> {
        let mut quellen = vec![self.pfad.clone()];
        quellen.extend(self.alter_pfad.clone());
        for pfad in quellen {
            let Ok(inhalt) = std::fs::read_to_string(&pfad) else {
                continue;
            };
            return match serde_json::from_str::<Value>(&inhalt) {
                Ok(Value::Array(liste)) => liste
                    .iter()
                    .filter(|wert| wert.is_object())
                    .map(BewertungsEintrag::aus_wert)
                    .collect(),
                _ => Vec::new(),
            };
        }
        Vec::new()
    }

    /// Schreibt alle Bewertungen in die Datei.
    fn schreibe(&self, eintraege: &[BewertungsEintrag]) {
        let liste: Vec<Value> = eintraege.iter().map(BewertungsEintrag::als_wert).collect();
        if let Ok(text) = serde_json::to_string_pretty(&Value::Array(liste)) {
            let _ = crate::pfade::schreibe_atomar(&self.pfad, &text);
        }
    }

    /// Legt eine Bewertung an und speichert sie.
    pub fn fuege_hinzu(&self, eintrag: BewertungsEintrag) -> BewertungsEintrag {
        let mut eintraege = self.hole_alle();
        eintraege.push(eintrag.clone());
        self.schreibe(&eintraege);
        eintrag
    }

    /// Legt eine Bewertung aus JSON-Daten an.
    pub fn fuege_wert_hinzu(&self, rohdaten: &Value) -> BewertungsEintrag {
        self.fuege_hinzu(BewertungsEintrag::aus_wert(rohdaten))
    }

    /// Gibt die letzten `anzahl` Bewertungen zurück.
    pub fn hole_letzte(&self, anzahl: usize) -> Vec<BewertungsEintrag> {
        if anzahl == 0 {
            return Vec::new();
        }
        let alle = self.hole_alle();
        let beginn = alle.len().saturating_sub(anzahl);
        alle[beginn..].to_vec()
    }

    /// Berechnet die Kennzahlen über alle Bewertungen.
    pub fn zusammenfassung(&self) -> BewertungsZusammenfassung {
        let eintraege = self.hole_alle();
        let positiv = eintraege.iter().filter(|e| e.bewertung > 0).count();
        let negativ = eintraege.iter().filter(|e| e.bewertung < 0).count();
        let neutral = eintraege.len() - positiv - negativ;
        let bewertet = positiv + negativ;
        BewertungsZusammenfassung {
            gesamt: eintraege.len(),
            positiv,
            negativ,
            neutral,
            anteil: if bewertet == 0 {
                0.0
            } else {
                positiv as f64 / bewertet as f64
            },
        }
    }

    /// Löscht alle Bewertungen.
    pub fn leere(&self) {
        self.schreibe(&[]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn speicher() -> (tempfile::TempDir, BewertungsSpeicher) {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let speicher = BewertungsSpeicher::neu(&ordner.path().join("data/bewertungen.json"));
        (ordner, speicher)
    }

    #[test]
    fn leerer_speicher_gibt_nullen() {
        let (_ordner, speicher) = speicher();
        assert!(speicher.hole_alle().is_empty());
        assert_eq!(
            speicher.zusammenfassung(),
            BewertungsZusammenfassung::default()
        );
    }

    #[test]
    fn bewertungen_werden_gezaehlt() {
        let (_ordner, speicher) = speicher();
        speicher.fuege_hinzu(BewertungsEintrag::neu("modell", "Frage", "Antwort", 1));
        speicher.fuege_hinzu(BewertungsEintrag::neu("modell", "Frage", "Antwort", 1));
        speicher.fuege_hinzu(BewertungsEintrag::neu("modell", "Frage", "Antwort", -1));
        speicher.fuege_hinzu(BewertungsEintrag::neu("modell", "Frage", "Antwort", 0));
        let kennzahlen = speicher.zusammenfassung();
        assert_eq!(kennzahlen.gesamt, 4);
        assert_eq!(kennzahlen.positiv, 2);
        assert_eq!(kennzahlen.negativ, 1);
        assert_eq!(kennzahlen.neutral, 1);
        assert!((kennzahlen.anteil - 2.0 / 3.0).abs() < 1e-9);
        assert_eq!(speicher.hole_letzte(2).len(), 2);
    }

    #[test]
    fn lange_texte_werden_gekuerzt() {
        let (_ordner, speicher) = speicher();
        let eintrag = speicher.fuege_hinzu(BewertungsEintrag::neu(
            "",
            &"ä".repeat(1500),
            &"b".repeat(1500),
            5,
        ));
        assert_eq!(eintrag.frage.chars().count(), 1000);
        assert_eq!(eintrag.antwort.chars().count(), 1000);
        assert_eq!(eintrag.bewertung, 1);
        assert_eq!(eintrag.modell, "unbekannt");
    }

    #[test]
    fn alte_feldnamen_werden_gelesen() {
        let (_ordner, speicher) = speicher();
        let eintrag = speicher.fuege_wert_hinzu(&json!({
            "ts": "2026-01-02T08:30:00", "model": "alt", "prompt": "Warum?",
            "response": "Deshalb.", "rating": "-1", "tags": "web"
        }));
        assert_eq!(eintrag.modell, "alt");
        assert_eq!(eintrag.frage, "Warum?");
        assert_eq!(eintrag.antwort, "Deshalb.");
        assert_eq!(eintrag.bewertung, -1);
        assert_eq!(eintrag.markierungen, vec!["web".to_string()]);
        assert_eq!(eintrag.text(), "Nicht hilfreich");
        assert_eq!(eintrag.kurzzeit(), "02.01. 08:30");
    }

    #[test]
    fn alte_datei_wird_gelesen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let datenordner = ordner.path().join("data");
        std::fs::create_dir_all(&datenordner).expect("Ordner");
        std::fs::write(
            datenordner.join("feedback.json"),
            "[{\"model\": \"alt\", \"rating\": 1}]",
        )
        .expect("schreiben");
        let speicher = BewertungsSpeicher::neu(&datenordner.join("bewertungen.json"));
        assert_eq!(speicher.hole_alle().len(), 1);
        assert_eq!(speicher.zusammenfassung().positiv, 1);
    }

    #[test]
    fn leeren_entfernt_alles() {
        let (_ordner, speicher) = speicher();
        speicher.fuege_hinzu(BewertungsEintrag::default());
        speicher.leere();
        assert!(speicher.hole_alle().is_empty());
    }
}
