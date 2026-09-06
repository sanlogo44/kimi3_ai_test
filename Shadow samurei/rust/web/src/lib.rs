//! Weboberfläche des Kimi3-Projekts.
//!
//! Das Kistenmodul enthält die Seitenvorlagen (reines HTML aus Rust), die
//! Sitzungsverwaltung, die Brücke zum Modellkern in Python, den gemeinsamen
//! Zustand und alle Routen. Alles ist ohne laufenden Server testbar.
//!
//! ```
//! use web::vorlagen::{trainingsseite, Adressen, Schalter};
//!
//! let html = trainingsseite(&Schalter::default(), &[], &[], "admin", None, &Adressen::default());
//! assert!(html.contains("training-formular"));
//! ```

pub mod bruecke;
pub mod routen;
pub mod sitzung;
pub mod vorlagen;
pub mod zustand;
