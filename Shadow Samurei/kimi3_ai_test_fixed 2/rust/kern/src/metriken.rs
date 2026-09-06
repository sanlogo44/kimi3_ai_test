//! Metriken der Trainings- und Benchmark-Läufe.
//!
//! Gespeichert wird als JSON-Liste in `data/metriken.json`. Alte Dateien
//! früherer Programmversionen (`data/metrics.json`,
//! `dev_tools/metrics/training_sessions.jsonl`) werden beim ersten Zugriff
//! einmalig übernommen, ebenso alte englische Feldnamen.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use crate::zeit;

/// Ein einzelner Metrikeintrag.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Metrik {
    /// Name des Modells oder Checkpoints.
    pub modell: String,
    /// Trefferquote zwischen 0 und 1.
    pub genauigkeit: f64,
    /// Verlustwert des Laufs.
    pub verlust: f64,
    /// Anzahl verarbeiteter Tokens.
    pub tokens: i64,
    /// Dauer des Trainings in Sekunden.
    pub trainingszeit: f64,
    /// Anzahl der Epochen.
    pub epochen: i64,
    /// Größe eines Stapels.
    pub stapelgroesse: i64,
    /// Verwendete Hardware.
    pub hardware: String,
    /// Freie Notizen.
    pub notizen: String,
    /// Markierungen, etwa `web` oder `training`.
    pub markierungen: Vec<String>,
    /// Zeitstempel im ISO-Format.
    pub zeitstempel: String,
}

impl Default for Metrik {
    fn default() -> Self {
        Self {
            modell: "unbekannt".into(),
            genauigkeit: 0.0,
            verlust: 0.0,
            tokens: 0,
            trainingszeit: 0.0,
            epochen: 0,
            stapelgroesse: 0,
            hardware: "unbekannt".into(),
            notizen: String::new(),
            markierungen: Vec::new(),
            zeitstempel: zeit::jetzt_iso(),
        }
    }
}

/// Übersetzt alte englische Feldnamen in das deutsche Schema.
fn deutscher_name(name: &str) -> &str {
    match name {
        "timestamp" | "ts" => "zeitstempel",
        "model" => "modell",
        "accuracy" => "genauigkeit",
        "loss" => "verlust",
        "tokens_used" => "tokens",
        "train_time_sec" | "train_time" => "trainingszeit",
        "epochs" | "epoch" => "epochen",
        "batch_size" => "stapelgroesse",
        "notes" => "notizen",
        "tags" => "markierungen",
        anderer => anderer,
    }
}

/// Liest eine Zahl robust aus einem JSON-Wert.
fn zahl(wert: Option<&Value>, ersatz: f64) -> f64 {
    match wert {
        Some(Value::Number(zahl)) => zahl.as_f64().unwrap_or(ersatz),
        Some(Value::String(text)) => text.trim().parse::<f64>().unwrap_or(ersatz),
        _ => ersatz,
    }
}

/// Liest eine Ganzzahl robust aus einem JSON-Wert.
fn ganzzahl(wert: Option<&Value>, ersatz: i64) -> i64 {
    let gelesen = zahl(wert, ersatz as f64);
    if gelesen.is_finite() {
        gelesen as i64
    } else {
        ersatz
    }
}

/// Liest einen Text robust aus einem JSON-Wert.
fn text(wert: Option<&Value>, ersatz: &str) -> String {
    match wert {
        // Leere Texte gelten wie in der Python-Fassung als „nicht gesetzt“.
        Some(Value::String(text)) => {
            if text.is_empty() {
                ersatz.to_string()
            } else {
                text.clone()
            }
        }
        Some(Value::Null) | None => ersatz.to_string(),
        Some(anderer) => {
            let text = anderer.to_string();
            if text.is_empty() {
                ersatz.to_string()
            } else {
                text
            }
        }
    }
}

impl Metrik {
    /// Erzeugt einen Eintrag aus – auch alten – JSON-Daten.
    pub fn aus_wert(rohdaten: &Value) -> Self {
        let mut daten: Map<String, Value> = Map::new();
        if let Some(karte) = rohdaten.as_object() {
            for (schluessel, wert) in karte {
                daten.insert(deutscher_name(schluessel).to_string(), wert.clone());
            }
        }
        let markierungen = match daten.get("markierungen") {
            Some(Value::Array(liste)) => liste
                .iter()
                .map(|wert| match wert {
                    Value::String(text) => text.clone(),
                    anderer => anderer.to_string(),
                })
                .collect(),
            Some(Value::String(einzel)) => vec![einzel.clone()],
            _ => Vec::new(),
        };
        Self {
            modell: text(daten.get("modell"), "unbekannt"),
            genauigkeit: zahl(daten.get("genauigkeit"), 0.0),
            verlust: zahl(daten.get("verlust"), 0.0),
            tokens: ganzzahl(daten.get("tokens"), 0),
            trainingszeit: zahl(daten.get("trainingszeit"), 0.0),
            epochen: ganzzahl(daten.get("epochen"), 0),
            stapelgroesse: ganzzahl(daten.get("stapelgroesse"), 0),
            hardware: text(daten.get("hardware"), "unbekannt"),
            notizen: text(daten.get("notizen"), ""),
            markierungen,
            zeitstempel: {
                let gelesen = text(daten.get("zeitstempel"), "");
                if gelesen.is_empty() {
                    zeit::jetzt_iso()
                } else {
                    gelesen
                }
            },
        }
    }

    /// Gibt den Eintrag als JSON-Wert zurück.
    pub fn als_wert(&self) -> Value {
        serde_json::to_value(self).unwrap_or(Value::Null)
    }

    /// Gibt eine kurze, lesbare Zeitangabe zurück.
    pub fn kurzzeit(&self) -> String {
        zeit::kurzzeit(&self.zeitstempel)
    }
}

/// Kennzahlen über alle Metrikeinträge.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Zusammenfassung {
    /// Anzahl der Einträge.
    pub anzahl: usize,
    /// Beste erreichte Genauigkeit.
    pub beste_genauigkeit: f64,
    /// Durchschnittliche Genauigkeit.
    pub durchschnitt_genauigkeit: f64,
    /// Durchschnittlicher Verlust.
    pub durchschnitt_verlust: f64,
    /// Durchschnittliche Trainingsdauer in Sekunden.
    pub durchschnitt_zeit: f64,
    /// Summe aller Tokens.
    pub tokens_gesamt: i64,
    /// Anzahl unterschiedlicher Modelle.
    pub modelle: usize,
    /// Zeitpunkt des letzten Laufs.
    pub letzter_lauf: String,
}

impl Default for Zusammenfassung {
    fn default() -> Self {
        Self {
            anzahl: 0,
            beste_genauigkeit: 0.0,
            durchschnitt_genauigkeit: 0.0,
            durchschnitt_verlust: 0.0,
            durchschnitt_zeit: 0.0,
            tokens_gesamt: 0,
            modelle: 0,
            letzter_lauf: "-".into(),
        }
    }
}

/// Durchschnittswerte eines einzelnen Modells.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ModellVergleich {
    /// Anzahl der Läufe dieses Modells.
    pub anzahl: usize,
    /// Durchschnittliche Genauigkeit.
    pub genauigkeit: f64,
    /// Durchschnittlicher Verlust.
    pub verlust: f64,
    /// Durchschnittliche Dauer in Sekunden.
    pub zeit: f64,
    /// Summe der Tokens.
    pub tokens: i64,
}

/// Speichert und wertet Metrikeinträge aus.
#[derive(Debug, Clone)]
pub struct MetrikSpeicher {
    pfad: PathBuf,
}

impl MetrikSpeicher {
    /// Öffnet den Speicher unter dem angegebenen Pfad.
    ///
    /// Fehlt die Datei, werden einmalig die Dateien früherer Versionen
    /// übernommen.
    pub fn neu(pfad: &Path) -> Self {
        let speicher = Self {
            pfad: pfad.to_path_buf(),
        };
        let _ = crate::pfade::stelle_ordner_bereit(&speicher.pfad);
        if !speicher.pfad.exists() {
            speicher.uebernimm_alte_dateien();
        }
        speicher
    }

    /// Öffnet den Speicher unter `data/metriken.json` des Projekts.
    pub fn standardpfad() -> Self {
        Self::neu(&crate::pfade::datendatei("metriken.json"))
    }

    /// Gibt den Pfad der Metrikdatei zurück.
    pub fn pfad(&self) -> &Path {
        &self.pfad
    }

    /// Liest Metriken früherer Programmversionen ein.
    fn uebernimm_alte_dateien(&self) {
        let datenordner = self.pfad.parent().map(Path::to_path_buf).unwrap_or_default();
        let projektordner = datenordner.parent().map(Path::to_path_buf).unwrap_or_default();
        let alte = [
            datenordner.join("metrics.json"),
            projektordner.join("dev_tools/metrics/training_sessions.jsonl"),
        ];
        let mut eintraege: Vec<Metrik> = Vec::new();
        for pfad in alte {
            let Ok(inhalt) = std::fs::read_to_string(&pfad) else {
                continue;
            };
            if pfad.extension().is_some_and(|endung| endung == "jsonl") {
                for zeile in inhalt.lines().filter(|zeile| !zeile.trim().is_empty()) {
                    if let Ok(wert) = serde_json::from_str::<Value>(zeile) {
                        eintraege.push(Metrik::aus_wert(&wert));
                    }
                }
            } else if let Ok(Value::Array(liste)) = serde_json::from_str::<Value>(&inhalt) {
                eintraege.extend(liste.iter().map(Metrik::aus_wert));
            }
        }
        if !eintraege.is_empty() {
            self.schreibe(&eintraege);
        }
    }

    /// Schreibt alle Einträge in die JSON-Datei.
    fn schreibe(&self, eintraege: &[Metrik]) {
        let liste: Vec<Value> = eintraege.iter().map(Metrik::als_wert).collect();
        if let Ok(text) = serde_json::to_string_pretty(&Value::Array(liste)) {
            let _ = crate::pfade::schreibe_atomar(&self.pfad, &text);
        }
    }

    /// Gibt alle Einträge in zeitlicher Reihenfolge zurück.
    pub fn hole_alle(&self) -> Vec<Metrik> {
        let Ok(inhalt) = std::fs::read_to_string(&self.pfad) else {
            return Vec::new();
        };
        match serde_json::from_str::<Value>(&inhalt) {
            Ok(Value::Array(liste)) => liste
                .iter()
                .filter(|wert| wert.is_object())
                .map(Metrik::aus_wert)
                .collect(),
            _ => Vec::new(),
        }
    }

    /// Legt einen neuen Eintrag an und speichert ihn.
    pub fn fuege_hinzu(&self, eintrag: Metrik) -> Metrik {
        let mut eintraege = self.hole_alle();
        eintraege.push(eintrag.clone());
        self.schreibe(&eintraege);
        eintrag
    }

    /// Legt einen Eintrag aus JSON-Daten an – auch mit alten Feldnamen.
    pub fn fuege_wert_hinzu(&self, rohdaten: &Value) -> Metrik {
        self.fuege_hinzu(Metrik::aus_wert(rohdaten))
    }

    /// Gibt die letzten `anzahl` Einträge zurück.
    pub fn hole_letzte(&self, anzahl: usize) -> Vec<Metrik> {
        if anzahl == 0 {
            return Vec::new();
        }
        let alle = self.hole_alle();
        let beginn = alle.len().saturating_sub(anzahl);
        alle[beginn..].to_vec()
    }

    /// Filtert Einträge nach Modellname und/oder Markierung.
    pub fn filtere(&self, modell: Option<&str>, markierung: Option<&str>) -> Vec<Metrik> {
        self.hole_alle()
            .into_iter()
            .filter(|eintrag| modell.is_none_or(|name| eintrag.modell == name))
            .filter(|eintrag| {
                markierung.is_none_or(|name| {
                    eintrag.markierungen.iter().any(|vorhanden| vorhanden == name)
                })
            })
            .collect()
    }

    /// Gibt alle vorkommenden Modellnamen in ihrer Reihenfolge zurück.
    pub fn modelle(&self) -> Vec<String> {
        let mut gesehen: Vec<String> = Vec::new();
        for eintrag in self.hole_alle() {
            if !gesehen.contains(&eintrag.modell) {
                gesehen.push(eintrag.modell);
            }
        }
        gesehen
    }

    /// Berechnet die Kennzahlen über alle Einträge.
    pub fn zusammenfassung(&self) -> Zusammenfassung {
        let eintraege = self.hole_alle();
        if eintraege.is_empty() {
            return Zusammenfassung::default();
        }
        let anzahl = eintraege.len();
        let teiler = anzahl as f64;
        let mut modelle: Vec<&str> = Vec::new();
        for eintrag in &eintraege {
            if !modelle.contains(&eintrag.modell.as_str()) {
                modelle.push(&eintrag.modell);
            }
        }
        Zusammenfassung {
            anzahl,
            beste_genauigkeit: eintraege
                .iter()
                .map(|eintrag| eintrag.genauigkeit)
                .fold(f64::NEG_INFINITY, f64::max),
            durchschnitt_genauigkeit: eintraege.iter().map(|e| e.genauigkeit).sum::<f64>() / teiler,
            durchschnitt_verlust: eintraege.iter().map(|e| e.verlust).sum::<f64>() / teiler,
            durchschnitt_zeit: eintraege.iter().map(|e| e.trainingszeit).sum::<f64>() / teiler,
            tokens_gesamt: eintraege.iter().map(|e| e.tokens).sum(),
            modelle: modelle.len(),
            letzter_lauf: eintraege
                .last()
                .map(Metrik::kurzzeit)
                .unwrap_or_else(|| "-".into()),
        }
    }

    /// Berechnet Durchschnittswerte je Modell.
    pub fn vergleich_je_modell(&self) -> BTreeMap<String, ModellVergleich> {
        let mut gruppen: BTreeMap<String, Vec<Metrik>> = BTreeMap::new();
        for eintrag in self.hole_alle() {
            gruppen.entry(eintrag.modell.clone()).or_default().push(eintrag);
        }
        gruppen
            .into_iter()
            .map(|(name, liste)| {
                let teiler = liste.len() as f64;
                (
                    name,
                    ModellVergleich {
                        anzahl: liste.len(),
                        genauigkeit: liste.iter().map(|e| e.genauigkeit).sum::<f64>() / teiler,
                        verlust: liste.iter().map(|e| e.verlust).sum::<f64>() / teiler,
                        zeit: liste.iter().map(|e| e.trainingszeit).sum::<f64>() / teiler,
                        tokens: liste.iter().map(|e| e.tokens).sum(),
                    },
                )
            })
            .collect()
    }

    /// Schreibt alle Einträge als CSV-Datei (Semikolon als Trennzeichen).
    pub fn exportiere_csv(&self, pfad: &Path) -> std::io::Result<PathBuf> {
        crate::pfade::stelle_ordner_bereit(pfad)?;
        let mut inhalt = String::from(
            "zeitstempel;modell;genauigkeit;verlust;tokens;trainingszeit;epochen;\
stapelgroesse;hardware;markierungen;notizen\n",
        );
        for eintrag in self.hole_alle() {
            let felder = [
                eintrag.zeitstempel.clone(),
                eintrag.modell.clone(),
                eintrag.genauigkeit.to_string(),
                eintrag.verlust.to_string(),
                eintrag.tokens.to_string(),
                eintrag.trainingszeit.to_string(),
                eintrag.epochen.to_string(),
                eintrag.stapelgroesse.to_string(),
                eintrag.hardware.clone(),
                eintrag.markierungen.join(", "),
                eintrag.notizen.clone(),
            ];
            let zeile: Vec<String> = felder
                .iter()
                .map(|feld| {
                    if feld.contains(';') || feld.contains('"') || feld.contains('\n') {
                        format!("\"{}\"", feld.replace('"', "\"\""))
                    } else {
                        feld.clone()
                    }
                })
                .collect();
            inhalt.push_str(&zeile.join(";"));
            inhalt.push('\n');
        }
        std::fs::write(pfad, inhalt)?;
        Ok(pfad.to_path_buf())
    }

    /// Löscht Einträge, die älter als `tage` Tage sind; gibt die Anzahl zurück.
    pub fn loesche_aelter_als(&self, tage: i64) -> usize {
        let grenze = zeit::vor_tagen(tage);
        let eintraege = self.hole_alle();
        let behalten: Vec<Metrik> = eintraege
            .iter()
            .filter(|eintrag| match zeit::lese(&eintrag.zeitstempel) {
                Some(zeitpunkt) => zeitpunkt >= grenze,
                None => true,
            })
            .cloned()
            .collect();
        let entfernt = eintraege.len() - behalten.len();
        if entfernt > 0 {
            self.schreibe(&behalten);
        }
        entfernt
    }

    /// Löscht alle gespeicherten Metriken.
    pub fn leere(&self) {
        self.schreibe(&[]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn speicher() -> (tempfile::TempDir, MetrikSpeicher) {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let speicher = MetrikSpeicher::neu(&ordner.path().join("data/metriken.json"));
        (ordner, speicher)
    }

    fn eintrag(modell: &str, genauigkeit: f64, tokens: i64) -> Metrik {
        Metrik {
            modell: modell.into(),
            genauigkeit,
            tokens,
            verlust: 1.0,
            trainingszeit: 2.0,
            epochen: 3,
            markierungen: vec!["training".into()],
            ..Metrik::default()
        }
    }

    #[test]
    fn leerer_speicher_gibt_leere_kennzahlen() {
        let (_ordner, speicher) = speicher();
        assert!(speicher.hole_alle().is_empty());
        assert_eq!(speicher.zusammenfassung(), Zusammenfassung::default());
    }

    #[test]
    fn eintraege_werden_gespeichert_und_gelesen() {
        let (_ordner, speicher) = speicher();
        speicher.fuege_hinzu(eintrag("ToyModel", 0.5, 100));
        speicher.fuege_hinzu(eintrag("ToyModel", 0.9, 200));
        speicher.fuege_hinzu(eintrag("soup", 0.7, 300));
        let kennzahlen = speicher.zusammenfassung();
        assert_eq!(kennzahlen.anzahl, 3);
        assert_eq!(kennzahlen.beste_genauigkeit, 0.9);
        assert_eq!(kennzahlen.tokens_gesamt, 600);
        assert_eq!(kennzahlen.modelle, 2);
        assert_eq!(speicher.hole_letzte(2).len(), 2);
        assert_eq!(speicher.modelle(), vec!["ToyModel", "soup"]);
    }

    #[test]
    fn alte_englische_feldnamen_werden_uebernommen() {
        let (_ordner, speicher) = speicher();
        let eintrag = speicher.fuege_wert_hinzu(&json!({
            "model": "alt", "accuracy": "0.42", "loss": 0.1,
            "tokens_used": 12, "train_time_sec": 3.5, "epochs": 7,
            "tags": "benchmark", "timestamp": "2026-01-01T10:00:00"
        }));
        assert_eq!(eintrag.modell, "alt");
        assert_eq!(eintrag.genauigkeit, 0.42);
        assert_eq!(eintrag.tokens, 12);
        assert_eq!(eintrag.epochen, 7);
        assert_eq!(eintrag.markierungen, vec!["benchmark".to_string()]);
        assert_eq!(eintrag.kurzzeit(), "01.01. 10:00");
    }

    #[test]
    fn filter_und_vergleich_arbeiten_je_modell() {
        let (_ordner, speicher) = speicher();
        speicher.fuege_hinzu(eintrag("a", 0.4, 10));
        speicher.fuege_hinzu(eintrag("a", 0.6, 20));
        speicher.fuege_hinzu(eintrag("b", 1.0, 30));
        assert_eq!(speicher.filtere(Some("a"), None).len(), 2);
        assert_eq!(speicher.filtere(None, Some("training")).len(), 3);
        assert_eq!(speicher.filtere(None, Some("gibt-es-nicht")).len(), 0);
        let vergleich = speicher.vergleich_je_modell();
        assert_eq!(vergleich["a"].anzahl, 2);
        assert!((vergleich["a"].genauigkeit - 0.5).abs() < 1e-9);
        assert_eq!(vergleich["b"].tokens, 30);
    }

    #[test]
    fn csv_enthaelt_kopfzeile_und_alle_zeilen() {
        let (ordner, speicher) = speicher();
        speicher.fuege_hinzu(eintrag("mit;Semikolon", 0.5, 10));
        let ziel = ordner.path().join("aus/metriken.csv");
        speicher.exportiere_csv(&ziel).expect("export");
        let inhalt = std::fs::read_to_string(&ziel).expect("lesen");
        assert!(inhalt.starts_with("zeitstempel;modell;"));
        assert!(inhalt.contains("\"mit;Semikolon\""));
        assert_eq!(inhalt.lines().count(), 2);
    }

    #[test]
    fn alte_eintraege_werden_geloescht() {
        let (_ordner, speicher) = speicher();
        speicher.fuege_wert_hinzu(&json!({"modell": "alt", "zeitstempel": "2020-01-01T00:00:00"}));
        speicher.fuege_hinzu(eintrag("neu", 0.5, 1));
        assert_eq!(speicher.loesche_aelter_als(30), 1);
        assert_eq!(speicher.hole_alle().len(), 1);
        speicher.leere();
        assert!(speicher.hole_alle().is_empty());
    }

    #[test]
    fn alte_datei_wird_einmalig_uebernommen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let datenordner = ordner.path().join("data");
        std::fs::create_dir_all(&datenordner).expect("Ordner");
        std::fs::write(
            datenordner.join("metrics.json"),
            "[{\"model\": \"alt\", \"accuracy\": 0.8}]",
        )
        .expect("schreiben");
        let speicher = MetrikSpeicher::neu(&datenordner.join("metriken.json"));
        let alle = speicher.hole_alle();
        assert_eq!(alle.len(), 1);
        assert_eq!(alle[0].modell, "alt");
        assert_eq!(alle[0].genauigkeit, 0.8);
    }
}
