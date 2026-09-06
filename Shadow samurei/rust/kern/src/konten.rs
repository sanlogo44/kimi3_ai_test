//! Benutzerkonten in `data/users.json`.
//!
//! Entspricht der bisherigen Python-Klasse `AuthManager`: dasselbe
//! Dateiformat, dieselben Regeln (mindestens vier Zeichen Passwort, der
//! letzte Administrator bleibt erhalten) und dieselben deutschen Texte.

use serde_json::{Map, Value};
use std::path::{Path, PathBuf};

use crate::konfiguration::Konfiguration;
use crate::passwort;
use crate::zeit;

/// Kleinste erlaubte Passwortlänge.
pub const MINDESTLAENGE_PASSWORT: usize = 4;

/// Gibt den Anzeigenamen einer Rolle zurück.
pub fn rollenname(rolle: &str) -> String {
    match rolle {
        "admin" => "Administrator".to_string(),
        "user" => "Benutzer".to_string(),
        anderer => anderer.to_string(),
    }
}

/// Ein einzelnes Benutzerkonto.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Konto {
    /// Anmeldename.
    pub benutzername: String,
    /// Passwort-Hash im Werkzeug-Format.
    pub passwort_hash: String,
    /// Rolle, `admin` oder `user`.
    pub rolle: String,
    /// Muss das Passwort bei der nächsten Anmeldung geändert werden?
    pub passwortwechsel_faellig: bool,
    /// Zeitpunkt der Anlage.
    pub erstellt_am: String,
    /// Zeitpunkt der letzten Anmeldung.
    pub letzte_anmeldung: String,
}

impl Konto {
    /// Erzeugt ein Konto mit frischem Passwort-Hash.
    pub fn neu(benutzername: &str, passwort_klartext: &str, rolle: &str, wechsel: bool) -> Self {
        Self {
            benutzername: benutzername.to_string(),
            passwort_hash: passwort::erzeuge_hash(passwort_klartext),
            rolle: rolle.to_string(),
            passwortwechsel_faellig: wechsel,
            erstellt_am: zeit::jetzt_iso(),
            letzte_anmeldung: String::new(),
        }
    }

    /// Liest ein Konto aus JSON-Daten; alte englische Schlüssel gelten weiter.
    pub fn aus_wert(benutzername: &str, daten: &Value) -> Self {
        let hole = |deutsch: &str, englisch: &str| -> Option<Value> {
            daten
                .get(deutsch)
                .or_else(|| daten.get(englisch))
                .cloned()
        };
        let text = |deutsch: &str, englisch: &str| -> String {
            match hole(deutsch, englisch) {
                Some(Value::String(wert)) => wert,
                Some(Value::Null) | None => String::new(),
                Some(anderer) => anderer.to_string(),
            }
        };
        let wahrheit = match hole("passwortwechsel_faellig", "force_password_change") {
            Some(Value::Bool(wert)) => wert,
            Some(Value::Number(zahl)) => zahl.as_f64().unwrap_or(0.0) != 0.0,
            Some(Value::String(wert)) => !wert.is_empty() && wert != "false" && wert != "0",
            _ => false,
        };
        let rolle = text("rolle", "role");
        Self {
            benutzername: benutzername.to_string(),
            passwort_hash: text("passwort_hash", "password_hash"),
            rolle: if rolle.is_empty() {
                "user".to_string()
            } else {
                rolle
            },
            passwortwechsel_faellig: wahrheit,
            erstellt_am: text("erstellt_am", "created_at"),
            letzte_anmeldung: text("letzte_anmeldung", "last_login"),
        }
    }

    /// Gibt das Konto als JSON-Wert zurück (ohne den Benutzernamen).
    pub fn als_wert(&self) -> Value {
        let mut karte = Map::new();
        karte.insert(
            "passwort_hash".into(),
            Value::String(self.passwort_hash.clone()),
        );
        karte.insert("rolle".into(), Value::String(self.rolle.clone()));
        karte.insert(
            "passwortwechsel_faellig".into(),
            Value::Bool(self.passwortwechsel_faellig),
        );
        karte.insert(
            "erstellt_am".into(),
            Value::String(self.erstellt_am.clone()),
        );
        karte.insert(
            "letzte_anmeldung".into(),
            Value::String(self.letzte_anmeldung.clone()),
        );
        Value::Object(karte)
    }

    /// Ist dieses Konto ein Administrator?
    pub fn ist_administrator(&self) -> bool {
        self.rolle == "admin"
    }

    /// Gibt den Anzeigenamen der Rolle zurück.
    pub fn rollenname(&self) -> String {
        rollenname(&self.rolle)
    }
}

/// Verwaltet alle Benutzerkonten.
#[derive(Debug, Clone)]
pub struct Kontenverwaltung {
    pfad: PathBuf,
    standardbenutzer: String,
    standardpasswort: String,
    wechsel_erzwingen: bool,
}

impl Kontenverwaltung {
    /// Öffnet die Verwaltung mit ausdrücklichem Pfad und Standardkonto.
    pub fn neu(pfad: &Path, benutzer: &str, passwort_klartext: &str, wechsel: bool) -> Self {
        Self {
            pfad: pfad.to_path_buf(),
            standardbenutzer: benutzer.to_string(),
            standardpasswort: passwort_klartext.to_string(),
            wechsel_erzwingen: wechsel,
        }
    }

    /// Öffnet die Verwaltung mit Werten aus der Konfiguration.
    pub fn aus_konfiguration(konfiguration: &Konfiguration) -> Self {
        Self::neu(
            &crate::pfade::datendatei("users.json"),
            &konfiguration.text(&["auth", "default_user"], "Admin"),
            &konfiguration.text(&["auth", "default_password"], "1234"),
            konfiguration.wahrheitswert(&["auth", "force_password_change"], true),
        )
    }

    /// Öffnet die Verwaltung mit der Konfiguration des Projekts.
    pub fn standardpfad() -> Self {
        Self::aus_konfiguration(&Konfiguration::lade_standardpfad())
    }

    /// Gibt den Pfad der Kontendatei zurück.
    pub fn pfad(&self) -> &Path {
        &self.pfad
    }

    /// Liest alle Konten; fehlt die Datei, wird das Standardkonto angelegt.
    pub fn lade_benutzer(&self) -> Vec<Konto> {
        let gelesen = std::fs::read_to_string(&self.pfad)
            .ok()
            .and_then(|inhalt| serde_json::from_str::<Value>(&inhalt).ok());
        if let Some(Value::Object(karte)) = gelesen {
            if !karte.is_empty() {
                return karte
                    .iter()
                    .map(|(name, daten)| Konto::aus_wert(name, daten))
                    .collect();
            }
        }
        let standard = vec![Konto::neu(
            &self.standardbenutzer,
            &self.standardpasswort,
            "admin",
            self.wechsel_erzwingen,
        )];
        self.speichere(&standard);
        standard
    }

    /// Schreibt alle Konten in die Datei.
    pub fn speichere(&self, konten: &[Konto]) {
        let mut karte = Map::new();
        for konto in konten {
            karte.insert(konto.benutzername.clone(), konto.als_wert());
        }
        if let Ok(text) = serde_json::to_string_pretty(&Value::Object(karte)) {
            let _ = crate::pfade::schreibe_atomar(&self.pfad, &text);
        }
    }

    /// Gibt ein einzelnes Konto zurück.
    pub fn hole(&self, benutzername: &str) -> Option<Konto> {
        self.lade_benutzer()
            .into_iter()
            .find(|konto| konto.benutzername == benutzername)
    }

    /// Gibt alle Benutzernamen zurück.
    pub fn liste(&self) -> Vec<String> {
        self.lade_benutzer()
            .into_iter()
            .map(|konto| konto.benutzername)
            .collect()
    }

    /// Gibt die Anzahl der Konten zurück.
    pub fn anzahl(&self) -> usize {
        self.lade_benutzer().len()
    }

    /// Ist das Konto ein Administrator?
    pub fn ist_administrator(&self, benutzername: &str) -> bool {
        self.hole(benutzername)
            .is_some_and(|konto| konto.ist_administrator())
    }

    /// Ist für dieses Konto ein Passwortwechsel fällig?
    pub fn passwortwechsel_faellig(&self, benutzername: &str) -> bool {
        self.hole(benutzername)
            .is_some_and(|konto| konto.passwortwechsel_faellig)
    }

    /// Anzahl der Administratorkonten.
    fn anzahl_administratoren(konten: &[Konto]) -> usize {
        konten
            .iter()
            .filter(|konto| konto.ist_administrator())
            .count()
    }

    /// Prüft Benutzername und Passwort und merkt die Anmeldung.
    pub fn pruefe_anmeldung(&self, benutzername: &str, passwort_klartext: &str) -> Option<Konto> {
        let mut konten = self.lade_benutzer();
        let stelle = konten
            .iter()
            .position(|konto| konto.benutzername == benutzername)?;
        if !passwort::pruefe(&konten[stelle].passwort_hash, passwort_klartext) {
            return None;
        }
        konten[stelle].letzte_anmeldung = zeit::jetzt_iso();
        let konto = konten[stelle].clone();
        self.speichere(&konten);
        Some(konto)
    }

    /// Legt ein neues Konto an.
    ///
    /// Fehler: Name schon vergeben, Name leer oder Passwort zu kurz.
    pub fn fuege_benutzer_hinzu(
        &self,
        benutzername: &str,
        passwort_klartext: &str,
        rolle: &str,
        wechsel: bool,
    ) -> Result<Konto, String> {
        let name = benutzername.trim();
        if name.is_empty() {
            return Err("Bitte einen Benutzernamen eingeben.".into());
        }
        if passwort_klartext.len() < MINDESTLAENGE_PASSWORT {
            return Err(format!(
                "Das Passwort muss mindestens {MINDESTLAENGE_PASSWORT} Zeichen haben."
            ));
        }
        let mut konten = self.lade_benutzer();
        if konten.iter().any(|konto| konto.benutzername == name) {
            return Err(format!("Der Benutzername „{name}“ ist schon vergeben."));
        }
        let konto = Konto::neu(name, passwort_klartext, rolle, wechsel);
        konten.push(konto.clone());
        self.speichere(&konten);
        Ok(konto)
    }

    /// Löscht ein Konto; der letzte Administrator bleibt erhalten.
    pub fn loesche_benutzer(&self, benutzername: &str) -> Result<(), String> {
        let mut konten = self.lade_benutzer();
        let Some(stelle) = konten
            .iter()
            .position(|konto| konto.benutzername == benutzername)
        else {
            return Err(format!("Das Konto „{benutzername}“ gibt es nicht."));
        };
        if konten[stelle].ist_administrator() && Self::anzahl_administratoren(&konten) <= 1 {
            return Err("Der letzte Administrator kann nicht gelöscht werden.".into());
        }
        konten.remove(stelle);
        self.speichere(&konten);
        Ok(())
    }

    /// Ändert das Passwort eines Kontos.
    pub fn aendere_passwort(
        &self,
        benutzername: &str,
        neues_passwort: &str,
        wechsel: bool,
    ) -> Result<(), String> {
        if neues_passwort.len() < MINDESTLAENGE_PASSWORT {
            return Err(format!(
                "Das Passwort muss mindestens {MINDESTLAENGE_PASSWORT} Zeichen haben."
            ));
        }
        let mut konten = self.lade_benutzer();
        let Some(stelle) = konten
            .iter()
            .position(|konto| konto.benutzername == benutzername)
        else {
            return Err(format!("Das Konto „{benutzername}“ gibt es nicht."));
        };
        konten[stelle].passwort_hash = passwort::erzeuge_hash(neues_passwort);
        konten[stelle].passwortwechsel_faellig = wechsel;
        self.speichere(&konten);
        Ok(())
    }

    /// Ändert die Rolle eines Kontos; der letzte Administrator bleibt es.
    pub fn aendere_rolle(&self, benutzername: &str, rolle: &str) -> Result<(), String> {
        let mut konten = self.lade_benutzer();
        let Some(stelle) = konten
            .iter()
            .position(|konto| konto.benutzername == benutzername)
        else {
            return Err(format!("Das Konto „{benutzername}“ gibt es nicht."));
        };
        if konten[stelle].ist_administrator()
            && rolle != "admin"
            && Self::anzahl_administratoren(&konten) <= 1
        {
            return Err("Der letzte Administrator behält seine Rolle.".into());
        }
        konten[stelle].rolle = rolle.to_string();
        self.speichere(&konten);
        Ok(())
    }

    /// Ändert Benutzernamen und Passwort in einem Schritt.
    ///
    /// Wird nach der ersten Anmeldung mit dem Standardkonto genutzt.
    pub fn aendere_zugangsdaten(
        &self,
        alter_name: &str,
        neuer_name: &str,
        neues_passwort: &str,
    ) -> Result<Konto, String> {
        let name = neuer_name.trim();
        if name.is_empty() {
            return Err("Bitte einen Benutzernamen eingeben.".into());
        }
        if neues_passwort.len() < MINDESTLAENGE_PASSWORT {
            return Err(format!(
                "Das Passwort muss mindestens {MINDESTLAENGE_PASSWORT} Zeichen haben."
            ));
        }
        let mut konten = self.lade_benutzer();
        let Some(stelle) = konten
            .iter()
            .position(|konto| konto.benutzername == alter_name)
        else {
            return Err(format!("Das Konto „{alter_name}“ gibt es nicht."));
        };
        if name != alter_name && konten.iter().any(|konto| konto.benutzername == name) {
            return Err(format!("Der Benutzername „{name}“ ist schon vergeben."));
        }
        konten[stelle].benutzername = name.to_string();
        konten[stelle].passwort_hash = passwort::erzeuge_hash(neues_passwort);
        konten[stelle].passwortwechsel_faellig = false;
        let konto = konten[stelle].clone();
        self.speichere(&konten);
        Ok(konto)
    }

    /// Merkt, dass die Erstanmeldung erledigt ist.
    pub fn markiere_erstanmeldung_erledigt(&self, benutzername: &str) -> Result<(), String> {
        let mut konten = self.lade_benutzer();
        let Some(stelle) = konten
            .iter()
            .position(|konto| konto.benutzername == benutzername)
        else {
            return Err(format!("Das Konto „{benutzername}“ gibt es nicht."));
        };
        konten[stelle].passwortwechsel_faellig = false;
        self.speichere(&konten);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn verwaltung() -> (tempfile::TempDir, Kontenverwaltung) {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let verwaltung =
            Kontenverwaltung::neu(&ordner.path().join("data/users.json"), "Admin", "1234", true);
        (ordner, verwaltung)
    }

    #[test]
    fn standardkonto_wird_angelegt() {
        let (_ordner, verwaltung) = verwaltung();
        let konten = verwaltung.lade_benutzer();
        assert_eq!(konten.len(), 1);
        assert_eq!(konten[0].benutzername, "Admin");
        assert!(konten[0].ist_administrator());
        assert!(konten[0].passwortwechsel_faellig);
        assert!(verwaltung.pfad().exists());
        assert_eq!(konten[0].rollenname(), "Administrator");
    }

    #[test]
    fn anmeldung_prueft_das_passwort() {
        let (_ordner, verwaltung) = verwaltung();
        assert!(verwaltung.pruefe_anmeldung("Admin", "falsch").is_none());
        assert!(verwaltung.pruefe_anmeldung("Gibtsnicht", "1234").is_none());
        let konto = verwaltung
            .pruefe_anmeldung("Admin", "1234")
            .expect("Anmeldung");
        assert!(!konto.letzte_anmeldung.is_empty());
        assert!(verwaltung.passwortwechsel_faellig("Admin"));
        assert!(verwaltung.ist_administrator("Admin"));
    }

    #[test]
    fn konten_werden_angelegt_und_geloescht() {
        let (_ordner, verwaltung) = verwaltung();
        verwaltung
            .fuege_benutzer_hinzu("Testkonto", "geheim", "user", false)
            .expect("anlegen");
        assert_eq!(verwaltung.anzahl(), 2);
        assert!(verwaltung.liste().contains(&"Testkonto".to_string()));
        assert!(verwaltung
            .fuege_benutzer_hinzu("Testkonto", "geheim", "user", false)
            .is_err());
        assert!(verwaltung
            .fuege_benutzer_hinzu("Kurz", "abc", "user", false)
            .is_err());
        assert!(verwaltung.fuege_benutzer_hinzu("  ", "geheim", "user", false).is_err());
        verwaltung.loesche_benutzer("Testkonto").expect("löschen");
        assert_eq!(verwaltung.anzahl(), 1);
        assert!(verwaltung.loesche_benutzer("Gibtsnicht").is_err());
    }

    #[test]
    fn letzter_administrator_bleibt_erhalten() {
        let (_ordner, verwaltung) = verwaltung();
        assert!(verwaltung.loesche_benutzer("Admin").is_err());
        assert!(verwaltung.aendere_rolle("Admin", "user").is_err());
        verwaltung
            .fuege_benutzer_hinzu("Zweiter", "geheim", "admin", false)
            .expect("anlegen");
        verwaltung.aendere_rolle("Admin", "user").expect("Rolle");
        assert!(!verwaltung.ist_administrator("Admin"));
    }

    #[test]
    fn passwort_und_zugangsdaten_lassen_sich_aendern() {
        let (_ordner, verwaltung) = verwaltung();
        assert!(verwaltung.aendere_passwort("Admin", "abc", false).is_err());
        verwaltung
            .aendere_passwort("Admin", "neuesPasswort", false)
            .expect("Passwort");
        assert!(verwaltung.pruefe_anmeldung("Admin", "1234").is_none());
        assert!(verwaltung.pruefe_anmeldung("Admin", "neuesPasswort").is_some());
        assert!(!verwaltung.passwortwechsel_faellig("Admin"));
        let konto = verwaltung
            .aendere_zugangsdaten("Admin", "Chefin", "sehrGeheim")
            .expect("Zugangsdaten");
        assert_eq!(konto.benutzername, "Chefin");
        assert!(verwaltung.pruefe_anmeldung("Chefin", "sehrGeheim").is_some());
        assert!(verwaltung.hole("Admin").is_none());
        assert!(verwaltung
            .aendere_zugangsdaten("Chefin", "", "sehrGeheim")
            .is_err());
        assert!(verwaltung.aendere_zugangsdaten("Chefin", "Neu", "ab").is_err());
    }

    #[test]
    fn alte_englische_schluessel_werden_gelesen() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("users.json");
        let hash = passwort::erzeuge_hash("1234");
        std::fs::write(
            &pfad,
            format!(
                "{{\"Admin\": {{\"password_hash\": \"{hash}\", \"role\": \"admin\", \
\"force_password_change\": true, \"created_at\": \"2025-01-01T00:00:00\", \
\"last_login\": \"\"}}}}"
            ),
        )
        .expect("schreiben");
        let verwaltung = Kontenverwaltung::neu(&pfad, "Admin", "1234", true);
        let konto = verwaltung.hole("Admin").expect("Konto");
        assert!(konto.ist_administrator());
        assert!(konto.passwortwechsel_faellig);
        assert_eq!(konto.erstellt_am, "2025-01-01T00:00:00");
        assert!(verwaltung.pruefe_anmeldung("Admin", "1234").is_some());
    }

    #[test]
    fn defekte_datei_ergibt_das_standardkonto() {
        let ordner = tempfile::tempdir().expect("Temporärordner");
        let pfad = ordner.path().join("users.json");
        std::fs::write(&pfad, "kein JSON").expect("schreiben");
        let verwaltung = Kontenverwaltung::neu(&pfad, "Admin", "1234", true);
        assert_eq!(verwaltung.liste(), vec!["Admin".to_string()]);
    }

    #[test]
    fn erstanmeldung_laesst_sich_abhaken() {
        let (_ordner, verwaltung) = verwaltung();
        verwaltung
            .markiere_erstanmeldung_erledigt("Admin")
            .expect("abhaken");
        assert!(!verwaltung.passwortwechsel_faellig("Admin"));
        assert!(verwaltung
            .markiere_erstanmeldung_erledigt("Gibtsnicht")
            .is_err());
    }
}
