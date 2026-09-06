//! Gemeinsamer Zustand des Servers und Umwandlung der Kern-Datentypen.

use std::sync::Arc;
use tokio::sync::Mutex;

use kern::bewertungen::BewertungsSpeicher;
use kern::checkpoints::CheckpointOrdner;
use kern::konfiguration::Konfiguration;
use kern::konten::Kontenverwaltung;
use kern::metriken::MetrikSpeicher;
use kern::schalter::{Schalter, SchalterSpeicher};

use crate::bruecke::Bruecke;
use crate::vorlagen;

/// Alles, was die Routen gemeinsam nutzen.
pub struct Zustand {
    /// Geheimnis für die Unterschrift der Sitzungen.
    pub geheimnis: String,
    /// Stellung der vier Schalter.
    pub schalter: Mutex<Schalter>,
    /// Speicher der Schalterstellungen.
    pub schalter_speicher: SchalterSpeicher,
    /// Speicher der Metriken.
    pub metriken: MetrikSpeicher,
    /// Speicher der Bewertungen.
    pub bewertungen: BewertungsSpeicher,
    /// Benutzerkonten.
    pub konten: Kontenverwaltung,
    /// Ordner der Checkpoint-Dateien.
    pub checkpoints: CheckpointOrdner,
    /// Brücke zum Modellkern in Python.
    pub bruecke: Bruecke,
    /// Laufen die Vergleichsläufe im Hintergrund?
    pub benchmarks_laeuft: Mutex<bool>,
    /// Name des Standardkontos aus der Konfiguration.
    pub standardbenutzer: String,
}

impl Zustand {
    /// Legt den Zustand aus der Konfiguration des Projekts an.
    pub fn neu() -> Arc<Self> {
        let konfiguration = Konfiguration::lade_standardpfad();
        let schalter_speicher = SchalterSpeicher::standardpfad();
        let schalter = schalter_speicher.lade();
        Arc::new(Self {
            geheimnis: crate::sitzung::geheimnis_aus_umgebung(),
            schalter: Mutex::new(schalter),
            schalter_speicher,
            metriken: MetrikSpeicher::standardpfad(),
            bewertungen: BewertungsSpeicher::standardpfad(),
            standardbenutzer: konfiguration.text(&["auth", "default_user"], "Admin"),
            konten: Kontenverwaltung::aus_konfiguration(&konfiguration),
            checkpoints: CheckpointOrdner::standardpfad(),
            bruecke: Bruecke::neu(),
            benchmarks_laeuft: Mutex::new(false),
        })
    }

    /// Gibt die aktuelle Schalterstellung zurück.
    pub async fn schalter(&self) -> Schalter {
        *self.schalter.lock().await
    }

    /// Laufen die Vergleichsläufe im Hintergrund?
    pub async fn benchmarks_laeuft(&self) -> bool {
        *self.benchmarks_laeuft.lock().await
    }
}

/// Wandelt die Schalter des Kerns in den Typ der Seitenvorlagen um.
pub fn schalter_fuer_seite(schalter: &Schalter) -> vorlagen::Schalter {
    vorlagen::Schalter {
        bewertungsmodus: schalter.bewertungsmodus,
        zeige_diagramm: schalter.zeige_diagramm,
        schicht_training: schalter.schicht_training,
        auto_benchmarks: schalter.auto_benchmarks,
    }
}

/// Wandelt einen Checkpoint des Kerns in den Typ der Seitenvorlagen um.
pub fn checkpoint_fuer_seite(punkt: &kern::checkpoints::Checkpoint) -> vorlagen::Checkpoint {
    vorlagen::Checkpoint {
        kennung: punkt.kennung.clone(),
        name: punkt.name.clone(),
        genauigkeit: punkt.genauigkeit,
        gespeichert_am: punkt.gespeichert_am.clone(),
    }
}

/// Wandelt eine Metrik des Kerns in den Typ der Seitenvorlagen um.
pub fn metrik_fuer_seite(eintrag: &kern::metriken::Metrik) -> vorlagen::Metrik {
    vorlagen::Metrik {
        zeitstempel: eintrag.zeitstempel.clone(),
        modell: eintrag.modell.clone(),
        genauigkeit: eintrag.genauigkeit,
        verlust: eintrag.verlust,
        trainingszeit: eintrag.trainingszeit,
        tokens: eintrag.tokens,
        epochen: eintrag.epochen,
    }
}

/// Wandelt die Kennzahlen des Kerns in den Typ der Seitenvorlagen um.
pub fn zusammenfassung_fuer_seite(
    kennzahlen: &kern::metriken::Zusammenfassung,
) -> vorlagen::Zusammenfassung {
    vorlagen::Zusammenfassung {
        anzahl: kennzahlen.anzahl,
        beste_genauigkeit: kennzahlen.beste_genauigkeit,
        tokens_gesamt: kennzahlen.tokens_gesamt,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schalter_werden_uebernommen() {
        let schalter = Schalter {
            bewertungsmodus: true,
            zeige_diagramm: false,
            schicht_training: true,
            auto_benchmarks: false,
        };
        let umgewandelt = schalter_fuer_seite(&schalter);
        assert!(umgewandelt.bewertungsmodus);
        assert!(!umgewandelt.zeige_diagramm);
        assert!(umgewandelt.schicht_training);
        assert!(!umgewandelt.auto_benchmarks);
    }

    #[test]
    fn checkpoints_und_metriken_werden_uebernommen() {
        let punkt = kern::checkpoints::Checkpoint {
            kennung: "abc".into(),
            name: "Lauf".into(),
            genauigkeit: Some(0.5),
            gespeichert_am: "2026-01-01 10:00:00".into(),
        };
        let umgewandelt = checkpoint_fuer_seite(&punkt);
        assert_eq!(umgewandelt.kennung, "abc");
        assert_eq!(umgewandelt.genauigkeit, Some(0.5));

        let eintrag = kern::metriken::Metrik {
            modell: "ToyModel".into(),
            genauigkeit: 0.9,
            tokens: 42,
            ..kern::metriken::Metrik::default()
        };
        let seite = metrik_fuer_seite(&eintrag);
        assert_eq!(seite.modell, "ToyModel");
        assert_eq!(seite.tokens, 42);
    }

    #[test]
    fn kennzahlen_werden_uebernommen() {
        let kennzahlen = kern::metriken::Zusammenfassung {
            anzahl: 3,
            beste_genauigkeit: 0.75,
            tokens_gesamt: 100,
            ..kern::metriken::Zusammenfassung::default()
        };
        let seite = zusammenfassung_fuer_seite(&kennzahlen);
        assert_eq!(seite.anzahl, 3);
        assert_eq!(seite.beste_genauigkeit, 0.75);
        assert_eq!(seite.tokens_gesamt, 100);
    }
}
