//! Sitzungen über ein unterschriebenes Kennwort-Plätzchen (Cookie).
//!
//! Die Flask-Fassung nutzte `session` mit `SECRET_KEY`. Hier steht an ihrer
//! Stelle ein eigenes, gleich sicheres Verfahren: Der Inhalt der Sitzung
//! wird als JSON abgelegt, mit HMAC-SHA256 unterschrieben und im Plätzchen
//! `kimi3_sitzung` gespeichert. Ohne gültige Unterschrift gilt die Sitzung
//! als leer – der Inhalt lässt sich also nicht fälschen.

use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use subtle::ConstantTimeEq;

/// Name des Plätzchens.
pub const PLAETZCHEN: &str = "kimi3_sitzung";
/// Voreingestelltes Geheimnis, falls `SECRET_KEY` nicht gesetzt ist.
pub const STANDARD_GEHEIMNIS: &str = "kimi3-dev-geheimnis-bitte-aendern";

/// Inhalt einer Sitzung.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Sitzung {
    /// Angemeldeter Benutzername; leer bedeutet „nicht angemeldet“.
    #[serde(default)]
    pub benutzer: String,
    /// Hat das Konto Administratorrechte?
    #[serde(default)]
    pub ist_admin: bool,
}

impl Sitzung {
    /// Ist jemand mit Administratorrechten angemeldet?
    pub fn ist_angemeldet(&self) -> bool {
        !self.benutzer.is_empty() && self.ist_admin
    }
}

/// Liest das Geheimnis aus der Umgebungsvariablen `SECRET_KEY`.
pub fn geheimnis_aus_umgebung() -> String {
    std::env::var("SECRET_KEY").unwrap_or_else(|_| STANDARD_GEHEIMNIS.to_string())
}

/// Berechnet die Unterschrift eines Textes.
fn unterschrift(geheimnis: &str, inhalt: &str) -> String {
    let mut rechner = <Hmac<Sha256>>::new_from_slice(geheimnis.as_bytes())
        .expect("HMAC nimmt Schlüssel jeder Länge an");
    rechner.update(inhalt.as_bytes());
    hex::encode(rechner.finalize().into_bytes())
}

/// Packt eine Sitzung in den Wert des Plätzchens.
pub fn verpacke(geheimnis: &str, sitzung: &Sitzung) -> String {
    let inhalt = hex::encode(serde_json::to_vec(sitzung).unwrap_or_default());
    let zeichen = unterschrift(geheimnis, &inhalt);
    format!("{inhalt}.{zeichen}")
}

/// Liest eine Sitzung aus dem Wert des Plätzchens.
///
/// Fehlt die Unterschrift oder passt sie nicht, ist die Sitzung leer.
pub fn entpacke(geheimnis: &str, wert: &str) -> Sitzung {
    let Some((inhalt, zeichen)) = wert.split_once('.') else {
        return Sitzung::default();
    };
    let erwartet = unterschrift(geheimnis, inhalt);
    let stimmt: bool = erwartet.as_bytes().ct_eq(zeichen.as_bytes()).into();
    if !stimmt {
        return Sitzung::default();
    }
    hex::decode(inhalt)
        .ok()
        .and_then(|bytes| serde_json::from_slice(&bytes).ok())
        .unwrap_or_default()
}

/// Sucht die Sitzung im Kopfzeilenwert `Cookie`.
pub fn aus_kopfzeile(geheimnis: &str, kopfzeile: Option<&str>) -> Sitzung {
    let Some(zeile) = kopfzeile else {
        return Sitzung::default();
    };
    for teil in zeile.split(';') {
        let teil = teil.trim();
        if let Some(wert) = teil.strip_prefix(&format!("{PLAETZCHEN}=")) {
            return entpacke(geheimnis, wert);
        }
    }
    Sitzung::default()
}

/// Erzeugt den Wert für die Kopfzeile `Set-Cookie`.
pub fn setz_kopfzeile(geheimnis: &str, sitzung: &Sitzung) -> String {
    format!(
        "{PLAETZCHEN}={}; Path=/; HttpOnly; SameSite=Lax",
        verpacke(geheimnis, sitzung)
    )
}

/// Erzeugt den Wert für die Kopfzeile `Set-Cookie`, der die Sitzung löscht.
pub fn loesch_kopfzeile() -> String {
    format!("{PLAETZCHEN}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn beispiel() -> Sitzung {
        Sitzung {
            benutzer: "Admin".into(),
            ist_admin: true,
        }
    }

    #[test]
    fn verpacken_und_entpacken_ergibt_dieselbe_sitzung() {
        let wert = verpacke("geheim", &beispiel());
        assert_eq!(entpacke("geheim", &wert), beispiel());
    }

    #[test]
    fn falsches_geheimnis_ergibt_leere_sitzung() {
        let wert = verpacke("geheim", &beispiel());
        assert_eq!(entpacke("anderes", &wert), Sitzung::default());
        assert!(!entpacke("anderes", &wert).ist_angemeldet());
    }

    #[test]
    fn gefaelschter_inhalt_wird_erkannt() {
        let wert = verpacke("geheim", &beispiel());
        let (_inhalt, zeichen) = wert.split_once('.').expect("Trennzeichen");
        let gefaelscht = format!("{}.{zeichen}", hex::encode(b"{\"benutzer\":\"Wer\"}"));
        assert_eq!(entpacke("geheim", &gefaelscht), Sitzung::default());
        assert_eq!(entpacke("geheim", "ohne-trennzeichen"), Sitzung::default());
        assert_eq!(entpacke("geheim", "zz.zz"), Sitzung::default());
    }

    #[test]
    fn kopfzeilen_werden_gelesen_und_geschrieben() {
        let gesetzt = setz_kopfzeile("geheim", &beispiel());
        assert!(gesetzt.starts_with("kimi3_sitzung="));
        assert!(gesetzt.contains("HttpOnly"));
        let wert = verpacke("geheim", &beispiel());
        let zeile = format!("anderes=1; {PLAETZCHEN}={wert}; noch=2");
        assert_eq!(aus_kopfzeile("geheim", Some(&zeile)), beispiel());
        assert_eq!(aus_kopfzeile("geheim", None), Sitzung::default());
        assert_eq!(
            aus_kopfzeile("geheim", Some("nichts=hier")),
            Sitzung::default()
        );
        assert!(loesch_kopfzeile().contains("Max-Age=0"));
    }

    #[test]
    fn nur_administratoren_gelten_als_angemeldet() {
        assert!(beispiel().ist_angemeldet());
        assert!(!Sitzung {
            benutzer: "Gast".into(),
            ist_admin: false
        }
        .ist_angemeldet());
        assert!(!Sitzung::default().ist_angemeldet());
    }

    #[test]
    fn standardgeheimnis_gilt_ohne_umgebungsvariable() {
        if std::env::var("SECRET_KEY").is_err() {
            assert_eq!(geheimnis_aus_umgebung(), STANDARD_GEHEIMNIS);
        }
    }
}
