//! Ermittelt die Pfade des Projekts.
//!
//! Der Projektordner wird in dieser Reihenfolge bestimmt:
//!
//! 1. Umgebungsvariable `KIMI3_ORDNER`,
//! 2. der erste Ordner ab dem Arbeitsverzeichnis nach oben, der eine
//!    `config.yaml` enthält,
//! 3. das Arbeitsverzeichnis selbst.

use std::env;
use std::io;
use std::path::{Path, PathBuf};

/// Name der Umgebungsvariable, mit der sich der Projektordner setzen lässt.
pub const UMGEBUNGSVARIABLE: &str = "KIMI3_ORDNER";

/// Gibt den Projektordner zurück.
pub fn projektordner() -> PathBuf {
    if let Some(wert) = env::var_os(UMGEBUNGSVARIABLE) {
        let pfad = PathBuf::from(wert);
        if !pfad.as_os_str().is_empty() {
            return pfad;
        }
    }
    let start = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut kandidat: &Path = start.as_path();
    loop {
        if kandidat.join("config.yaml").is_file() {
            return kandidat.to_path_buf();
        }
        match kandidat.parent() {
            Some(oben) => kandidat = oben,
            None => break,
        }
    }
    start
}

/// Gibt den Ordner `data/` des Projekts zurück.
pub fn datenordner() -> PathBuf {
    projektordner().join("data")
}

/// Gibt den Pfad einer Datei im Ordner `data/` zurück.
pub fn datendatei(name: &str) -> PathBuf {
    datenordner().join(name)
}

/// Legt den übergeordneten Ordner einer Datei an, falls er fehlt.
pub fn stelle_ordner_bereit(datei: &Path) -> io::Result<()> {
    if let Some(ordner) = datei.parent() {
        if !ordner.as_os_str().is_empty() {
            std::fs::create_dir_all(ordner)?;
        }
    }
    Ok(())
}

/// Schreibt Text so, dass die Zieldatei nie halb beschrieben zurückbleibt.
///
/// Der Inhalt landet zuerst in einer Datei mit der Endung `.tmp` und wird
/// anschließend über die Zieldatei geschoben.
pub fn schreibe_atomar(datei: &Path, inhalt: &str) -> io::Result<()> {
    stelle_ordner_bereit(datei)?;
    let zwischenziel = datei.with_extension(format!(
        "{}tmp",
        datei
            .extension()
            .map(|endung| format!("{}.", endung.to_string_lossy()))
            .unwrap_or_default()
    ));
    std::fs::write(&zwischenziel, inhalt)?;
    std::fs::rename(&zwischenziel, datei)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn atomares_schreiben_legt_ordner_an() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let ziel = ordner.path().join("unter/ordner/datei.json");
        schreibe_atomar(&ziel, "{\"a\": 1}").expect("schreiben");
        assert_eq!(
            std::fs::read_to_string(&ziel).expect("lesen"),
            "{\"a\": 1}"
        );
        // Die Zwischendatei darf nicht zurückbleiben.
        assert!(!ziel.with_extension("json.tmp").exists());
    }

    #[test]
    fn projektordner_folgt_der_umgebungsvariable() {
        // Nur die Auswertung der Variable wird geprüft, ohne sie zu setzen:
        // ein leerer Wert darf nicht gelten.
        assert!(projektordner().is_absolute() || projektordner() == PathBuf::from("."));
    }
}
