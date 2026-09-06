//! Datentypen, die die Seitenvorlagen entgegennehmen.
//!
//! In der Python-Fassung werden die Werte als `Mapping` übergeben. In Rust
//! treten an ihre Stelle klar benannte Verbunde mit öffentlichen Feldern.

/// Die vier globalen Schalter der Verwaltung.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Schalter {
    /// Erlaubt das Bewerten von Antworten.
    pub bewertungsmodus: bool,
    /// Zeigt Diagramme und Tabellen im Trainingsbereich.
    pub zeige_diagramm: bool,
    /// Erlaubt das gezielte Training einzelner Schichten.
    pub schicht_training: bool,
    /// Vergleichsläufe im Hintergrund.
    pub auto_benchmarks: bool,
}

/// Ein gespeicherter Modellstand.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Checkpoint {
    /// Eindeutige Kennung des Checkpoints.
    pub kennung: String,
    /// Sprechender Name des Checkpoints.
    pub name: String,
    /// Genauigkeit als Anteil zwischen 0 und 1, sofern bekannt.
    pub genauigkeit: Option<f64>,
    /// Zeitpunkt der Speicherung als ISO-Text.
    pub gespeichert_am: String,
}

/// Ein einzelner Metrik-Eintrag eines Trainingslaufs.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Metrik {
    /// Zeitstempel des Laufs als ISO-Text.
    pub zeitstempel: String,
    /// Name des verwendeten Modells.
    pub modell: String,
    /// Genauigkeit als Anteil zwischen 0 und 1.
    pub genauigkeit: f64,
    /// Verlustwert des Laufs.
    pub verlust: f64,
    /// Dauer des Trainings in Sekunden.
    pub trainingszeit: f64,
    /// Anzahl verarbeiteter Tokens.
    pub tokens: i64,
    /// Anzahl der Epochen.
    pub epochen: i64,
}

/// Zusammenfassung über alle Metrik-Einträge.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct Zusammenfassung {
    /// Anzahl der ausgewerteten Einträge.
    pub anzahl: usize,
    /// Beste erreichte Genauigkeit als Anteil zwischen 0 und 1.
    pub beste_genauigkeit: f64,
    /// Summe aller verarbeiteten Tokens.
    pub tokens_gesamt: i64,
}

/// Die Adressen, auf die die Navigation und die Formulare zeigen.
///
/// Die Standardwerte passen zu den Routen in `app.py` und erlauben es, die
/// Seiten ohne laufenden Server zu erzeugen.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Adressen {
    /// Adresse der Trainingsseite.
    pub training: String,
    /// Adresse des Verwaltungsbereichs.
    pub verwaltung: String,
    /// Adresse der Anmeldung.
    pub anmeldung: String,
    /// Adresse der Abmeldung.
    pub abmeldung: String,
    /// Adresse zum Ändern der Zugangsdaten.
    pub zugangsdaten: String,
}

impl Default for Adressen {
    fn default() -> Self {
        Self {
            training: "/".to_string(),
            verwaltung: "/admin".to_string(),
            anmeldung: "/login".to_string(),
            abmeldung: "/logout".to_string(),
            zugangsdaten: "/change-credentials".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standardadressen_entsprechen_den_routen() {
        let adressen = Adressen::default();
        assert_eq!(adressen.training, "/");
        assert_eq!(adressen.verwaltung, "/admin");
        assert_eq!(adressen.anmeldung, "/login");
        assert_eq!(adressen.abmeldung, "/logout");
        assert_eq!(adressen.zugangsdaten, "/change-credentials");
    }

    #[test]
    fn schalter_sind_standardmaessig_aus() {
        let schalter = Schalter::default();
        assert!(!schalter.bewertungsmodus);
        assert!(!schalter.zeige_diagramm);
        assert!(!schalter.schicht_training);
        assert!(!schalter.auto_benchmarks);
    }
}
