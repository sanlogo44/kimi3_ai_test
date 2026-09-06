//! Seitenvorlagen der Weboberfläche – geschrieben in reinem Rust.
//!
//! Statt Vorlagendateien erzeugen diese Module den HTML-Text als
//! Zeichenkette. Vorteile: die Vorlagen lassen sich mit den üblichen
//! Werkzeugen prüfen (Übersetzer, Typprüfung, Tests), sie sind ohne
//! laufenden Server aufrufbar, und alle Werte laufen über eine gemeinsame
//! Maskierung.
//!
//! Die Aufteilung entspricht eins zu eins der Python-Fassung im Ordner
//! `vorlagen/`:
//!
//! * [`bausteine`] – Maskierung, Elemente, Formatierer, Sammelbausteine
//! * [`grundgeruest`] – Kopf, Stilangaben, Navigation, Basis-Skript
//! * [`anmeldung`] – Anmeldung und Ändern der Zugangsdaten
//! * [`training`] – Trainingsseite
//! * [`verwaltung`] – Verwaltungsbereich
//! * [`typen`] – Datentypen, die die Seiten entgegennehmen
//!
//! Beispiel:
//!
//! ```
//! use web::vorlagen::{anmeldeseite, Adressen};
//!
//! let html = anmeldeseite(Some("Ungültige Zugangsdaten."), &Adressen::default());
//! assert!(html.starts_with("<!DOCTYPE html>"));
//! ```

pub mod anmeldung;
pub mod bausteine;
pub mod grundgeruest;
pub mod training;
pub mod typen;
pub mod verwaltung;

pub use anmeldung::{anmeldeseite, zugangsdatenseite};
pub use bausteine::{
    attribute, auswahlkasten, eingabefeld, element, hinweis, kachel, karte, knopf, kommazahl, leer,
    leermeldung, prozent, roh, schalterzeile, schieber, sicher, sicher_wahl, tabelle, text,
    text_wahl, verbinde, wahrheit, wenn, wert, wert_falls_gefuellt, Attribut, RohHtml,
    LEERE_ELEMENTE,
};
pub use grundgeruest::{
    erscheinungsbild_knopf, navigation, seite, GRUNDSKRIPT, STILANGABEN,
};
pub use training::{checkpoint_tabelle, trainingsseite, SKRIPT_METRIKEN, SKRIPT_TRAINING};
pub use typen::{Adressen, Checkpoint, Metrik, Schalter, Zusammenfassung};
pub use verwaltung::{metriktabelle, verwaltungsseite, SCHALTER_BESCHREIBUNG, SKRIPT_VERWALTUNG};

#[cfg(test)]
mod tests {
    use super::*;

    /// Prüft die Verschachtelung eines HTML-Textes mit einem einfachen Stapel.
    ///
    /// Rückgabe ist `Ok(())`, wenn jede Marke wieder geschlossen wird, sonst
    /// eine Beschreibung der ersten gefundenen Abweichung. Skript- und
    /// Stilbereiche werden übersprungen, da sie beliebigen Text enthalten.
    fn pruefe_verschachtelung(html: &str) -> Result<(), String> {
        let leere_marken = ["input", "meta", "br", "hr", "img", "link"];
        let zeichen: Vec<char> = html.chars().collect();
        let mut stapel: Vec<String> = Vec::new();
        let mut stelle = 0usize;
        while stelle < zeichen.len() {
            if zeichen[stelle] != '<' {
                stelle += 1;
                continue;
            }
            let Some(ende) = zeichen[stelle..].iter().position(|z| *z == '>') else {
                return Err("Nicht geschlossene Marke am Textende".to_string());
            };
            let roher_inhalt: String = zeichen[stelle + 1..stelle + ende].iter().collect();
            stelle += ende + 1;
            if roher_inhalt.starts_with('!') {
                continue;
            }
            let schliessend = roher_inhalt.starts_with('/');
            let name: String = roher_inhalt
                .trim_start_matches('/')
                .split_whitespace()
                .next()
                .unwrap_or_default()
                .to_ascii_lowercase();
            if name.is_empty() {
                return Err("Marke ohne Namen gefunden".to_string());
            }
            if schliessend {
                match stapel.pop() {
                    Some(offen) if offen == name => {}
                    Some(offen) => {
                        return Err(format!("</{}> schließt stattdessen <{}>", name, offen))
                    }
                    None => return Err(format!("</{}> ohne öffnende Marke", name)),
                }
                continue;
            }
            if leere_marken.contains(&name.as_str()) {
                continue;
            }
            // Skript- und Stilinhalte enthalten Zeichen wie „<“ und werden
            // deshalb bis zur schließenden Marke übersprungen.
            if name == "script" || name == "style" {
                let schluss = format!("</{}>", name);
                let rest: String = zeichen[stelle..].iter().collect();
                match rest.find(&schluss) {
                    Some(abstand) => {
                        stelle += rest[..abstand + schluss.len()].chars().count();
                    }
                    None => return Err(format!("<{}> wird nie geschlossen", name)),
                }
                continue;
            }
            stapel.push(name);
        }
        if stapel.is_empty() {
            Ok(())
        } else {
            Err(format!("Offen geblieben: {}", stapel.join(", ")))
        }
    }

    fn beispielseiten() -> Vec<(&'static str, String)> {
        let adressen = Adressen::default();
        let checkpoints = vec![Checkpoint {
            kennung: "cp-1".to_string(),
            name: "Lauf <B>".to_string(),
            genauigkeit: Some(0.8712),
            gespeichert_am: "2026-01-01T10:00:00".to_string(),
        }];
        let metriken = vec![Metrik {
            zeitstempel: "2026-01-01T10:00:00".to_string(),
            modell: "Kimi3".to_string(),
            genauigkeit: 0.8712,
            verlust: 0.1234,
            trainingszeit: 12.5,
            tokens: 4096,
            epochen: 10,
        }];
        let voll = Schalter {
            bewertungsmodus: true,
            zeige_diagramm: true,
            schicht_training: true,
            auto_benchmarks: true,
        };
        let zusammenfassung = Zusammenfassung {
            anzahl: 1,
            beste_genauigkeit: 0.9,
            tokens_gesamt: 4096,
        };
        vec![
            ("anmeldung", anmeldeseite(None, &adressen)),
            (
                "anmeldung mit Fehler",
                anmeldeseite(Some("Ungültige Zugangsdaten."), &adressen),
            ),
            (
                "zugangsdaten",
                zugangsdatenseite("admin", Some("Zu kurz"), true, &adressen),
            ),
            (
                "training leer",
                trainingsseite(
                    &Schalter::default(),
                    &[],
                    &[],
                    "admin",
                    None,
                    &adressen,
                ),
            ),
            (
                "training voll",
                trainingsseite(
                    &voll,
                    &checkpoints,
                    &["schicht.0".to_string(), "schicht.1".to_string()],
                    "admin",
                    Some("Kern nicht verfügbar"),
                    &adressen,
                ),
            ),
            (
                "verwaltung leer",
                verwaltungsseite(
                    &Schalter::default(),
                    &[],
                    &[],
                    None,
                    false,
                    "",
                    None,
                    &adressen,
                ),
            ),
            (
                "verwaltung voll",
                verwaltungsseite(
                    &voll,
                    &checkpoints,
                    &metriken,
                    Some(&zusammenfassung),
                    true,
                    "admin",
                    Some("Kern nicht verfügbar"),
                    &adressen,
                ),
            ),
        ]
    }

    #[test]
    fn alle_seiten_sind_sauber_verschachtelt() {
        for (name, html) in beispielseiten() {
            if let Err(fehler) = pruefe_verschachtelung(&html) {
                panic!("Seite „{}“ ist fehlerhaft: {}", name, fehler);
            }
        }
    }

    #[test]
    fn stapelpruefer_erkennt_offene_marken() {
        assert!(pruefe_verschachtelung("<div><p>Text</p></div>").is_ok());
        assert!(pruefe_verschachtelung("<div><p>Text</div>").is_err());
        assert!(pruefe_verschachtelung("<div><input></div>").is_ok());
        assert!(pruefe_verschachtelung("<div>Text").is_err());
    }

    #[test]
    fn alle_seiten_haben_dokumenttyp_und_titel() {
        for (name, html) in beispielseiten() {
            assert!(html.starts_with("<!DOCTYPE html>\n"), "{} ohne Dokumenttyp", name);
            assert!(html.contains("</html>"), "{} ohne Abschluss", name);
            assert!(html.contains("Kimi3</title>"), "{} ohne Titel", name);
        }
    }

    #[test]
    fn seitenlaengen_liegen_in_der_groessenordnung_der_python_vorlagen() {
        // Vergleichswerte der Python-Vorlagen (Zeichenzahl):
        //   anmeldeseite       10874
        //   zugangsdatenseite  10866
        //   trainingsseite     16635 (leer) … 19676 (voll)
        //   verwaltungsseite   14543 (leer)
        let adressen = Adressen::default();
        let erwartungen: [(&str, usize, usize); 4] = [
            ("anmeldung", anmeldeseite(None, &adressen).chars().count(), 10874),
            (
                "zugangsdaten",
                zugangsdatenseite("admin", None, true, &adressen)
                    .chars()
                    .count(),
                10866,
            ),
            (
                "training",
                trainingsseite(&Schalter::default(), &[], &[], "admin", None, &adressen)
                    .chars()
                    .count(),
                16635,
            ),
            (
                "verwaltung",
                verwaltungsseite(
                    &Schalter::default(),
                    &[],
                    &[],
                    None,
                    false,
                    "admin",
                    None,
                    &adressen,
                )
                .chars()
                .count(),
                14543,
            ),
        ];
        for (name, gemessen, erwartet) in erwartungen {
            let abweichung = gemessen.abs_diff(erwartet) as f64 / erwartet as f64;
            assert!(
                abweichung < 0.05,
                "Seite „{}“ weicht zu stark ab: {} statt {}",
                name,
                gemessen,
                erwartet
            );
        }
    }
}
