//! Protokollierung mit farbiger Konsolenausgabe und optionaler Datei.
//!
//! Die Ausgabe entspricht der bisherigen Python-Fassung (`logger.py`):
//! `[HH:MM:SS] STUFE Nachricht` auf der Konsole und
//! `[JJJJ-MM-TT HH:MM:SS] [STUFE] Nachricht` in der Datei.

use std::fmt;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

use crate::konfiguration::Konfiguration;
use crate::zeit;

/// Die fünf Protokollstufen.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Stufe {
    /// Ausführliche Meldungen für die Fehlersuche.
    Fehlersuche,
    /// Übliche Betriebsmeldungen.
    Hinweis,
    /// Warnungen, die den Betrieb nicht verhindern.
    Warnung,
    /// Fehler, die eine Aktion verhindern.
    Fehler,
    /// Schwere Fehler, nach denen kaum weitergearbeitet werden kann.
    Kritisch,
}

impl Stufe {
    /// Gibt den Namen zurück, wie er im Protokoll erscheint.
    pub fn name(self) -> &'static str {
        match self {
            Stufe::Fehlersuche => "DEBUG",
            Stufe::Hinweis => "INFO",
            Stufe::Warnung => "WARNING",
            Stufe::Fehler => "ERROR",
            Stufe::Kritisch => "CRITICAL",
        }
    }

    /// Gibt den ANSI-Farbcode der Stufe zurück.
    fn farbe(self) -> &'static str {
        match self {
            Stufe::Fehlersuche => "\x1b[36m",
            Stufe::Hinweis => "\x1b[32m",
            Stufe::Warnung => "\x1b[33m",
            Stufe::Fehler => "\x1b[31m",
            Stufe::Kritisch => "\x1b[35m",
        }
    }

    /// Liest eine Stufe aus einem Text; unbekannte Angaben ergeben `Hinweis`.
    pub fn aus_text(text: &str) -> Self {
        match text.trim().to_uppercase().as_str() {
            "DEBUG" | "FEHLERSUCHE" => Stufe::Fehlersuche,
            "WARNING" | "WARN" | "WARNUNG" => Stufe::Warnung,
            "ERROR" | "FEHLER" => Stufe::Fehler,
            "CRITICAL" | "KRITISCH" => Stufe::Kritisch,
            _ => Stufe::Hinweis,
        }
    }
}

impl fmt::Display for Stufe {
    fn fmt(&self, ausgabe: &mut fmt::Formatter<'_>) -> fmt::Result {
        ausgabe.write_str(self.name())
    }
}

/// Schreibt Meldungen auf die Konsole und optional in eine Datei.
#[derive(Debug)]
pub struct Protokoll {
    stufe: Mutex<Stufe>,
    farbig: bool,
    datei: Option<PathBuf>,
}

impl Protokoll {
    /// Erzeugt ein Protokoll.
    pub fn neu(stufe: Stufe, farbig: bool, datei: Option<PathBuf>) -> Self {
        if let Some(pfad) = &datei {
            let _ = crate::pfade::stelle_ordner_bereit(pfad);
        }
        Self {
            stufe: Mutex::new(stufe),
            farbig,
            datei,
        }
    }

    /// Erzeugt ein Protokoll aus dem Abschnitt `logging` der Konfiguration.
    pub fn aus_konfiguration(konfiguration: &Konfiguration) -> Self {
        let datei = konfiguration
            .hole(&["logging", "log_file"])
            .and_then(|wert| wert.as_str())
            .filter(|text| !text.is_empty())
            .map(PathBuf::from);
        Self::neu(
            Stufe::aus_text(&konfiguration.text(&["logging", "level"], "INFO")),
            konfiguration.wahrheitswert(&["logging", "colored"], true),
            datei,
        )
    }

    /// Setzt die kleinste Stufe, die noch ausgegeben wird.
    pub fn setze_stufe(&self, stufe: Stufe) {
        if let Ok(mut aktuell) = self.stufe.lock() {
            *aktuell = stufe;
        }
    }

    /// Gibt die aktuell eingestellte Stufe zurück.
    pub fn stufe(&self) -> Stufe {
        self.stufe.lock().map(|wert| *wert).unwrap_or(Stufe::Hinweis)
    }

    /// Gibt den Pfad der Protokolldatei zurück, falls eine gesetzt ist.
    pub fn dateipfad(&self) -> Option<&Path> {
        self.datei.as_deref()
    }

    /// Schreibt eine Meldung, wenn ihre Stufe hoch genug ist.
    pub fn schreibe(&self, stufe: Stufe, nachricht: &str) {
        if stufe < self.stufe() {
            return;
        }
        let uhrzeit = zeit::jetzt_lesbar();
        let konsole = if self.farbig {
            format!(
                "[{}] {}\x1b[1m{}\x1b[0m {}",
                &uhrzeit[11..],
                stufe.farbe(),
                stufe.name(),
                nachricht
            )
        } else {
            format!("[{}] {} {}", &uhrzeit[11..], stufe.name(), nachricht)
        };
        println!("{konsole}");
        if let Some(pfad) = &self.datei {
            let zeile = format!("[{uhrzeit}] [{}] {nachricht}\n", stufe.name());
            if let Ok(mut datei) = OpenOptions::new().create(true).append(true).open(pfad) {
                let _ = datei.write_all(zeile.as_bytes());
            }
        }
    }

    /// Schreibt eine Meldung der Stufe `DEBUG`.
    pub fn fehlersuche(&self, nachricht: &str) {
        self.schreibe(Stufe::Fehlersuche, nachricht);
    }

    /// Schreibt eine Meldung der Stufe `INFO`.
    pub fn hinweis(&self, nachricht: &str) {
        self.schreibe(Stufe::Hinweis, nachricht);
    }

    /// Schreibt eine Meldung der Stufe `WARNING`.
    pub fn warnung(&self, nachricht: &str) {
        self.schreibe(Stufe::Warnung, nachricht);
    }

    /// Schreibt eine Meldung der Stufe `ERROR`.
    pub fn fehler(&self, nachricht: &str) {
        self.schreibe(Stufe::Fehler, nachricht);
    }

    /// Schreibt eine Meldung der Stufe `CRITICAL`.
    pub fn kritisch(&self, nachricht: &str) {
        self.schreibe(Stufe::Kritisch, nachricht);
    }
}

/// Gemeinsam genutztes Protokoll des Programms.
static GEMEINSAM: OnceLock<Protokoll> = OnceLock::new();

/// Gibt das gemeinsame Protokoll zurück und legt es beim ersten Aufruf an.
pub fn hole_protokoll() -> &'static Protokoll {
    GEMEINSAM.get_or_init(|| Protokoll::aus_konfiguration(&Konfiguration::lade_standardpfad()))
}

/// Setzt das gemeinsame Protokoll, solange es noch nicht angelegt wurde.
pub fn setze_protokoll(protokoll: Protokoll) -> bool {
    GEMEINSAM.set(protokoll).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stufen_werden_gelesen_und_benannt() {
        assert_eq!(Stufe::aus_text("debug"), Stufe::Fehlersuche);
        assert_eq!(Stufe::aus_text("WARNUNG"), Stufe::Warnung);
        assert_eq!(Stufe::aus_text("unbekannt"), Stufe::Hinweis);
        assert_eq!(Stufe::Kritisch.name(), "CRITICAL");
    }

    #[test]
    fn datei_erhaelt_nur_die_hohen_stufen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("protokoll/lauf.log");
        let protokoll = Protokoll::neu(Stufe::Warnung, false, Some(pfad.clone()));
        protokoll.hinweis("wird verworfen");
        protokoll.warnung("wird geschrieben");
        protokoll.fehler("wird auch geschrieben");
        let inhalt = std::fs::read_to_string(&pfad).expect("lesen");
        assert!(!inhalt.contains("wird verworfen"));
        assert!(inhalt.contains("[WARNING] wird geschrieben"));
        assert!(inhalt.contains("[ERROR] wird auch geschrieben"));
    }

    #[test]
    fn stufe_laesst_sich_umstellen() {
        let protokoll = Protokoll::neu(Stufe::Fehler, false, None);
        assert_eq!(protokoll.stufe(), Stufe::Fehler);
        protokoll.setze_stufe(Stufe::Fehlersuche);
        assert_eq!(protokoll.stufe(), Stufe::Fehlersuche);
    }
}
