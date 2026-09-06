//! Startprogramm der Weboberfläche.
//!
//! Aufruf: `kimi3-web [--host 0.0.0.0] [--port 5000]`.
//! Die Adresse lässt sich auch über die Umgebungsvariablen `KIMI3_HOST`
//! und `KIMI3_PORT` setzen.

use std::net::SocketAddr;
use std::process::ExitCode;

use serde_json::json;
use web::routen::baue_router;
use web::zustand::Zustand;

/// Aufrufparameter des Servers.
#[derive(Debug, PartialEq)]
struct Aufruf {
    /// Netzwerkadresse, an der gelauscht wird.
    host: String,
    /// Anschlussnummer.
    port: u16,
}

impl Default for Aufruf {
    fn default() -> Self {
        Self {
            host: std::env::var("KIMI3_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
            port: std::env::var("KIMI3_PORT")
                .ok()
                .and_then(|text| text.parse().ok())
                .unwrap_or(5000),
        }
    }
}

/// Liest die Aufrufparameter aus der Kommandozeile.
fn lese_aufruf<I: IntoIterator<Item = String>>(argumente: I) -> Result<Aufruf, String> {
    let mut aufruf = Aufruf::default();
    let mut reste = argumente.into_iter();
    while let Some(argument) = reste.next() {
        match argument.as_str() {
            "--host" => {
                aufruf.host = reste
                    .next()
                    .ok_or_else(|| "Nach „--host“ fehlt die Adresse.".to_string())?;
            }
            "--port" => {
                let text = reste
                    .next()
                    .ok_or_else(|| "Nach „--port“ fehlt die Nummer.".to_string())?;
                aufruf.port = text
                    .parse()
                    .map_err(|_| format!("„{text}“ ist keine gültige Anschlussnummer."))?;
            }
            "--hilfe" | "--help" | "-h" => {
                return Err("HILFE".to_string());
            }
            unbekannt => {
                return Err(format!("Unbekannte Angabe: „{unbekannt}“."));
            }
        }
    }
    Ok(aufruf)
}

/// Gibt die Kurzhilfe aus.
fn zeige_hilfe() {
    println!("Weboberfläche von Kimi3");
    println!();
    println!("Aufruf: kimi3-web [--host ADRESSE] [--port NUMMER]");
    println!("  --host   Netzwerkadresse (Standard: 0.0.0.0)");
    println!("  --port   Anschlussnummer (Standard: 5000)");
    println!("  --hilfe  Diese Hilfe anzeigen");
}

#[tokio::main]
async fn main() -> ExitCode {
    let aufruf = match lese_aufruf(std::env::args().skip(1)) {
        Ok(aufruf) => aufruf,
        Err(meldung) if meldung == "HILFE" => {
            zeige_hilfe();
            return ExitCode::SUCCESS;
        }
        Err(meldung) => {
            eprintln!("Fehler: {meldung}");
            zeige_hilfe();
            return ExitCode::FAILURE;
        }
    };

    let zustand = Zustand::neu();

    // Wie im früheren `starte_server`: laufen die Vergleichsläufe
    // automatisch, werden sie beim Start angestoßen.
    if zustand.schalter().await.auto_benchmarks {
        match zustand.bruecke.rufe("benchmarks_starten", json!({})).await {
            Ok(_) => *zustand.benchmarks_laeuft.lock().await = true,
            Err(fehler) => eprintln!("Hinweis: {}", fehler.meldung),
        }
    }

    let adresse: SocketAddr = match format!("{}:{}", aufruf.host, aufruf.port).parse() {
        Ok(adresse) => adresse,
        Err(_) => {
            eprintln!(
                "Fehler: „{}:{}“ ist keine gültige Adresse.",
                aufruf.host, aufruf.port
            );
            return ExitCode::FAILURE;
        }
    };

    let lauscher = match tokio::net::TcpListener::bind(adresse).await {
        Ok(lauscher) => lauscher,
        Err(fehler) => {
            eprintln!("Fehler: Adresse {adresse} nicht belegbar ({fehler}).");
            return ExitCode::FAILURE;
        }
    };
    println!("Weboberfläche läuft auf http://{adresse}");
    println!("Beenden mit Strg+C.");

    let router = baue_router(zustand.clone());
    let ergebnis = axum::serve(lauscher, router)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
            println!("\nServer wird beendet.");
        })
        .await;
    zustand.bruecke.beende().await;
    match ergebnis {
        Ok(()) => ExitCode::SUCCESS,
        Err(fehler) => {
            eprintln!("Fehler: Server abgebrochen ({fehler}).");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standardwerte_werden_genutzt() {
        let aufruf = lese_aufruf(Vec::<String>::new()).expect("Aufruf");
        assert_eq!(aufruf.port, 5000);
    }

    #[test]
    fn host_und_port_werden_gelesen() {
        let argumente = ["--host", "127.0.0.1", "--port", "8080"]
            .iter()
            .map(|text| text.to_string())
            .collect::<Vec<_>>();
        let aufruf = lese_aufruf(argumente).expect("Aufruf");
        assert_eq!(aufruf.host, "127.0.0.1");
        assert_eq!(aufruf.port, 8080);
    }

    #[test]
    fn falsche_angaben_ergeben_fehler() {
        let fehler = lese_aufruf(vec!["--port".to_string(), "abc".to_string()]);
        assert!(fehler.is_err());
        let fehler = lese_aufruf(vec!["--unsinn".to_string()]);
        assert!(fehler.is_err());
        let fehler = lese_aufruf(vec!["--host".to_string()]);
        assert!(fehler.is_err());
    }
}
