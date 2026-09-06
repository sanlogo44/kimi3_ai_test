//! Brücke zum Modellkern in Python.
//!
//! Alles, was PyTorch braucht, bleibt Python. Die Weboberfläche startet
//! dazu einmalig den Prozess `python3 kern_bruecke.py` und tauscht mit ihm
//! zeilenweise JSON aus (siehe `bruecke_protokoll.md` im Projektordner).
//! Weil der Prozess läuft, solange der Server läuft, behält er sein
//! Arbeitsmodell und die Hintergrund-Benchmarks – genau wie die frühere
//! Flask-Fassung im eigenen Prozess.

use serde_json::{json, Value};
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, ChildStdout, Command};
use tokio::sync::Mutex;

/// Antwort der Brücke bei einem Fehler.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BrueckenFehler {
    /// HTTP-Status, den die Weboberfläche weitergibt.
    pub status: u16,
    /// Deutsche Fehlermeldung.
    pub meldung: String,
}

impl BrueckenFehler {
    /// Erzeugt einen Fehler mit Status und Meldung.
    pub fn neu(status: u16, meldung: impl Into<String>) -> Self {
        Self {
            status,
            meldung: meldung.into(),
        }
    }
}

/// Kurzform für Ergebnisse der Brücke.
pub type BrueckenErgebnis = Result<Value, BrueckenFehler>;

/// Der laufende Python-Prozess samt seinen Kanälen.
struct Prozess {
    kind: Child,
    eingang: ChildStdin,
    ausgang: BufReader<ChildStdout>,
}

/// Verbindung zum Modellkern in Python.
pub struct Bruecke {
    programm: String,
    skript: std::path::PathBuf,
    arbeitsordner: std::path::PathBuf,
    prozess: Mutex<Option<Prozess>>,
    /// Zuletzt gemeldeter Grund, warum der Kern fehlt.
    kern_fehler: Mutex<Option<String>>,
}

impl Bruecke {
    /// Legt die Brücke an, ohne den Prozess schon zu starten.
    pub fn neu() -> Self {
        let ordner = kern::pfade::projektordner();
        Self {
            programm: std::env::var("PYTHON").unwrap_or_else(|_| "python3".to_string()),
            skript: ordner.join("kern_bruecke.py"),
            arbeitsordner: ordner,
            prozess: Mutex::new(None),
            kern_fehler: Mutex::new(None),
        }
    }

    /// Gibt den zuletzt gemeldeten Grund für einen fehlenden Kern zurück.
    pub async fn kern_fehler(&self) -> Option<String> {
        self.kern_fehler.lock().await.clone()
    }

    /// Startet den Python-Prozess, falls er nicht läuft.
    async fn starte(&self, halter: &mut Option<Prozess>) -> Result<(), BrueckenFehler> {
        if halter.is_some() {
            return Ok(());
        }
        if !self.skript.exists() {
            return Err(BrueckenFehler::neu(
                503,
                format!(
                    "Die Brücke zum Modellkern fehlt ({}).",
                    self.skript.display()
                ),
            ));
        }
        let mut kind = Command::new(&self.programm)
            .arg(&self.skript)
            .current_dir(&self.arbeitsordner)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .kill_on_drop(true)
            .spawn()
            .map_err(|fehler| {
                BrueckenFehler::neu(
                    503,
                    format!(
                        "Python konnte nicht gestartet werden ({fehler}). \
Bitte „pip install -r requirements.txt“ ausführen."
                    ),
                )
            })?;
        let eingang = kind.stdin.take().ok_or_else(|| {
            BrueckenFehler::neu(503, "Die Brücke zum Modellkern nimmt keine Eingaben an.")
        })?;
        let ausgang = kind.stdout.take().ok_or_else(|| {
            BrueckenFehler::neu(503, "Die Brücke zum Modellkern antwortet nicht.")
        })?;
        *halter = Some(Prozess {
            kind,
            eingang,
            ausgang: BufReader::new(ausgang),
        });
        Ok(())
    }

    /// Schickt einen Befehl und wartet auf die Antwort.
    pub async fn rufe(&self, befehl: &str, daten: Value) -> BrueckenErgebnis {
        let mut halter = self.prozess.lock().await;
        self.starte(&mut halter).await?;
        let ergebnis = self.rufe_intern(&mut halter, befehl, daten).await;
        if let Err(fehler) = &ergebnis {
            // Nach einem Abbruch der Verbindung den Prozess verwerfen, damit
            // der nächste Aufruf neu startet.
            if fehler.status == 503 && fehler.meldung.contains("antwortet nicht") {
                if let Some(mut prozess) = halter.take() {
                    let _ = prozess.kind.start_kill();
                }
            }
        }
        match &ergebnis {
            Err(fehler) if fehler.status == 503 => {
                *self.kern_fehler.lock().await = Some(fehler.meldung.clone());
            }
            Ok(_) => {
                *self.kern_fehler.lock().await = None;
            }
            _ => {}
        }
        ergebnis
    }

    /// Führt den Austausch einer Zeile durch.
    async fn rufe_intern(
        &self,
        halter: &mut Option<Prozess>,
        befehl: &str,
        daten: Value,
    ) -> BrueckenErgebnis {
        let prozess = halter.as_mut().ok_or_else(|| {
            BrueckenFehler::neu(503, "Die Brücke zum Modellkern antwortet nicht.")
        })?;
        let anfrage = json!({"befehl": befehl, "daten": daten});
        let mut zeile = serde_json::to_string(&anfrage).unwrap_or_default();
        zeile.push('\n');
        prozess
            .eingang
            .write_all(zeile.as_bytes())
            .await
            .map_err(|_| {
                BrueckenFehler::neu(503, "Die Brücke zum Modellkern antwortet nicht.")
            })?;
        prozess.eingang.flush().await.map_err(|_| {
            BrueckenFehler::neu(503, "Die Brücke zum Modellkern antwortet nicht.")
        })?;
        let mut antwort = String::new();
        let gelesen = prozess
            .ausgang
            .read_line(&mut antwort)
            .await
            .map_err(|_| {
                BrueckenFehler::neu(503, "Die Brücke zum Modellkern antwortet nicht.")
            })?;
        if gelesen == 0 {
            return Err(BrueckenFehler::neu(
                503,
                "Die Brücke zum Modellkern antwortet nicht.",
            ));
        }
        deute_antwort(&antwort)
    }

    /// Beendet den Prozess, falls er läuft.
    pub async fn beende(&self) {
        if let Some(mut prozess) = self.prozess.lock().await.take() {
            let _ = prozess.eingang.shutdown().await;
            let _ = prozess.kind.start_kill();
        }
    }
}

/// Wertet eine Antwortzeile der Brücke aus.
pub fn deute_antwort(zeile: &str) -> BrueckenErgebnis {
    let wert: Value = serde_json::from_str(zeile.trim()).map_err(|_| {
        BrueckenFehler::neu(500, "Die Brücke zum Modellkern hat unklar geantwortet.")
    })?;
    if wert.get("ok").and_then(Value::as_bool) == Some(true) {
        return Ok(wert.get("daten").cloned().unwrap_or_else(|| json!({})));
    }
    let status = wert
        .get("status")
        .and_then(Value::as_u64)
        .unwrap_or(500) as u16;
    let meldung = wert
        .get("fehler")
        .and_then(Value::as_str)
        .unwrap_or("Unbekannter Fehler im Modellkern.")
        .to_string();
    Err(BrueckenFehler::neu(status, meldung))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gute_antwort_wird_gelesen() {
        let wert = deute_antwort("{\"ok\": true, \"daten\": {\"tokens\": 5}}").expect("Antwort");
        assert_eq!(wert["tokens"], json!(5));
        assert_eq!(deute_antwort("{\"ok\": true}").expect("Antwort"), json!({}));
    }

    #[test]
    fn fehlerantwort_behaelt_status_und_meldung() {
        let fehler = deute_antwort("{\"ok\": false, \"fehler\": \"weg\", \"status\": 404}")
            .expect_err("Fehler");
        assert_eq!(fehler.status, 404);
        assert_eq!(fehler.meldung, "weg");
    }

    #[test]
    fn unklare_antwort_ergibt_500() {
        let fehler = deute_antwort("kein JSON").expect_err("Fehler");
        assert_eq!(fehler.status, 500);
        let ohne = deute_antwort("{\"ok\": false}").expect_err("Fehler");
        assert_eq!(ohne.status, 500);
        assert_eq!(ohne.meldung, "Unbekannter Fehler im Modellkern.");
    }
}
