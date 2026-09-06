//! Kern der Anwendung: Logik und Datenhaltung in Rust.
//!
//! Diese Kiste enthält alles, was weder PyTorch noch eine Oberfläche
//! braucht: Konfiguration, Protokollierung, Einstellungen, Schalter,
//! Metriken, Bewertungen, Konten samt Passwortprüfung, die Verwaltung der
//! Checkpoint-Dateien und den sicheren Rechner.
//!
//! Die Kiste wird an zwei Stellen genutzt:
//!
//! * von der Weboberfläche (`web`), die daraus vollständig in Rust läuft,
//! * von Python über das Modul `kimi3_kern` (Kiste `pybindungen`), damit
//!   Desktop-Oberfläche und Modellkern dieselbe Logik verwenden und es
//!   keine zweite Umsetzung derselben Regeln gibt.
//!
//! Alle Dateien liegen wie bisher im Ordner `data/` des Projekts und
//! behalten ihr Format, damit alte Daten weiter gelesen werden.

pub mod bewertungen;
pub mod checkpoints;
pub mod einstellungen;
pub mod konfiguration;
pub mod konten;
pub mod metriken;
pub mod passwort;
pub mod pfade;
pub mod protokoll;
pub mod rechner;
pub mod schalter;
pub mod zeit;

pub use bewertungen::{BewertungsEintrag, BewertungsSpeicher};
pub use checkpoints::Checkpoint;
pub use einstellungen::Einstellungen;
pub use konfiguration::Konfiguration;
pub use konten::{Konto, Kontenverwaltung};
pub use metriken::{Metrik, MetrikSpeicher, Zusammenfassung};
pub use protokoll::{Protokoll, Stufe};
pub use rechner::{berechne, RechenFehler};
pub use schalter::Schalter;

/// Version der Kiste, wie sie in `Cargo.toml` steht.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
