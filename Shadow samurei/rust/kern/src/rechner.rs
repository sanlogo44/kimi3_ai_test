//! Sicherer Rechner für mathematische Ausdrücke.
//!
//! Entspricht `tools.berechne` aus der Python-Fassung: erlaubt sind Zahlen,
//! die Grundrechenarten, Vorzeichen, ein festgelegter Satz Funktionen und
//! die Konstanten `pi`, `e` und `tau`. Ausgewertet wird über einen eigenen
//! Parser – es gibt weder `eval` noch sonst einen Umweg über fremden Code.
//!
//! ```
//! assert_eq!(kern::rechner::berechne("2 + 3 * 4").unwrap(), 14.0);
//! assert!(kern::rechner::berechne("1 / 0").is_err());
//! ```

use std::fmt;

/// Höchstlänge eines Ausdrucks.
const HOECHSTLAENGE: usize = 300;
/// Obergrenze für Potenzen, damit kein Ausdruck den Rechner blockiert.
const HOECHSTER_EXPONENT: f64 = 64.0;

/// Fehler bei der Auswertung eines Ausdrucks.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RechenFehler {
    /// Deutsche Fehlermeldung, wie sie die Oberfläche anzeigt.
    pub meldung: String,
}

impl RechenFehler {
    /// Erzeugt einen Fehler mit der angegebenen Meldung.
    fn neu(meldung: impl Into<String>) -> Self {
        Self {
            meldung: meldung.into(),
        }
    }
}

impl fmt::Display for RechenFehler {
    fn fmt(&self, ausgabe: &mut fmt::Formatter<'_>) -> fmt::Result {
        ausgabe.write_str(&self.meldung)
    }
}

impl std::error::Error for RechenFehler {}

/// Kurzform für Ergebnisse des Rechners.
type Ergebnis<T> = Result<T, RechenFehler>;

/// Ein Zeichen-Baustein des Ausdrucks.
#[derive(Debug, Clone, PartialEq)]
enum Baustein {
    Zahl(f64),
    Name(String),
    Klammer(char),
    Komma,
    Operator(String),
}

/// Zerlegt den Ausdruck in Bausteine.
fn zerlege(ausdruck: &str) -> Ergebnis<Vec<Baustein>> {
    let zeichen: Vec<char> = ausdruck.chars().collect();
    let mut bausteine = Vec::new();
    let mut stelle = 0usize;
    while stelle < zeichen.len() {
        let zeichen_hier = zeichen[stelle];
        if zeichen_hier.is_whitespace() {
            stelle += 1;
        } else if zeichen_hier.is_ascii_digit() || zeichen_hier == '.' {
            let beginn = stelle;
            while stelle < zeichen.len()
                && (zeichen[stelle].is_ascii_digit()
                    || zeichen[stelle] == '.'
                    || zeichen[stelle] == '_')
            {
                stelle += 1;
            }
            // Exponentialschreibweise, etwa „1e-3“.
            if stelle < zeichen.len() && (zeichen[stelle] == 'e' || zeichen[stelle] == 'E') {
                let merker = stelle;
                let mut vorschau = stelle + 1;
                if vorschau < zeichen.len()
                    && (zeichen[vorschau] == '+' || zeichen[vorschau] == '-')
                {
                    vorschau += 1;
                }
                if vorschau < zeichen.len() && zeichen[vorschau].is_ascii_digit() {
                    stelle = vorschau;
                    while stelle < zeichen.len() && zeichen[stelle].is_ascii_digit() {
                        stelle += 1;
                    }
                } else {
                    stelle = merker;
                }
            }
            let text: String = zeichen[beginn..stelle].iter().collect();
            let zahl = text.replace('_', "").parse::<f64>().map_err(|_| {
                RechenFehler::neu(format!("Ungültiger Ausdruck: „{text}“ ist keine Zahl."))
            })?;
            bausteine.push(Baustein::Zahl(zahl));
        } else if zeichen_hier.is_alphabetic() || zeichen_hier == '_' {
            let beginn = stelle;
            while stelle < zeichen.len()
                && (zeichen[stelle].is_alphanumeric() || zeichen[stelle] == '_')
            {
                stelle += 1;
            }
            bausteine.push(Baustein::Name(zeichen[beginn..stelle].iter().collect()));
        } else if zeichen_hier == '(' || zeichen_hier == ')' {
            bausteine.push(Baustein::Klammer(zeichen_hier));
            stelle += 1;
        } else if zeichen_hier == ';' {
            // Argumenttrenner, falls Kommas schon zu Punkten wurden.
            bausteine.push(Baustein::Komma);
            stelle += 1;
        } else if "+-*/%".contains(zeichen_hier) {
            let doppelt = stelle + 1 < zeichen.len() && zeichen[stelle + 1] == zeichen_hier;
            if doppelt && (zeichen_hier == '*' || zeichen_hier == '/') {
                bausteine.push(Baustein::Operator(format!("{zeichen_hier}{zeichen_hier}")));
                stelle += 2;
            } else {
                bausteine.push(Baustein::Operator(zeichen_hier.to_string()));
                stelle += 1;
            }
        } else {
            return Err(RechenFehler::neu(format!(
                "Ungültiger Ausdruck: „{zeichen_hier}“ ist nicht erlaubt."
            )));
        }
    }
    Ok(bausteine)
}

/// Wertet die Bausteine von links nach rechts aus.
struct Auswertung {
    bausteine: Vec<Baustein>,
    stelle: usize,
}

impl Auswertung {
    /// Gibt den nächsten Baustein zurück, ohne weiterzugehen.
    fn schau(&self) -> Option<&Baustein> {
        self.bausteine.get(self.stelle)
    }

    /// Prüft, ob an dieser Stelle der angegebene Operator steht.
    fn ist_operator(&self, zeichen: &str) -> bool {
        matches!(self.schau(), Some(Baustein::Operator(wert)) if wert == zeichen)
    }

    /// Summe und Differenz.
    fn summe(&mut self) -> Ergebnis<f64> {
        let mut wert = self.produkt()?;
        loop {
            if self.ist_operator("+") {
                self.stelle += 1;
                wert += self.produkt()?;
            } else if self.ist_operator("-") {
                self.stelle += 1;
                wert -= self.produkt()?;
            } else {
                return Ok(wert);
            }
        }
    }

    /// Produkt, Quotient, Ganzzahldivision und Restwert.
    fn produkt(&mut self) -> Ergebnis<f64> {
        let mut wert = self.vorzeichen()?;
        loop {
            let operator = match self.schau() {
                Some(Baustein::Operator(zeichen))
                    if ["*", "/", "//", "%"].contains(&zeichen.as_str()) =>
                {
                    zeichen.clone()
                }
                _ => return Ok(wert),
            };
            self.stelle += 1;
            let rechts = self.vorzeichen()?;
            if rechts == 0.0 && operator != "*" {
                return Err(RechenFehler::neu("Division durch Null."));
            }
            wert = match operator.as_str() {
                "*" => wert * rechts,
                "/" => wert / rechts,
                "//" => (wert / rechts).floor(),
                // Restwert mit dem Vorzeichen des Teilers, wie in Python.
                _ => wert - rechts * (wert / rechts).floor(),
            };
        }
    }

    /// Vorzeichen vor einem Wert.
    fn vorzeichen(&mut self) -> Ergebnis<f64> {
        if self.ist_operator("-") {
            self.stelle += 1;
            return Ok(-self.vorzeichen()?);
        }
        if self.ist_operator("+") {
            self.stelle += 1;
            return self.vorzeichen();
        }
        self.potenz()
    }

    /// Potenz; rechts vor links, wie in Python.
    fn potenz(&mut self) -> Ergebnis<f64> {
        let basis = self.wert()?;
        if self.ist_operator("**") {
            self.stelle += 1;
            let exponent = self.vorzeichen()?;
            if exponent.abs() > HOECHSTER_EXPONENT {
                return Err(RechenFehler::neu(format!(
                    "Der Exponent darf höchstens {} sein.",
                    HOECHSTER_EXPONENT as i64
                )));
            }
            if basis == 0.0 && exponent < 0.0 {
                return Err(RechenFehler::neu("Division durch Null."));
            }
            return Ok(basis.powf(exponent));
        }
        Ok(basis)
    }

    /// Zahl, Konstante, Klammerausdruck oder Funktionsaufruf.
    fn wert(&mut self) -> Ergebnis<f64> {
        match self.schau().cloned() {
            Some(Baustein::Zahl(zahl)) => {
                self.stelle += 1;
                Ok(zahl)
            }
            Some(Baustein::Klammer('(')) => {
                self.stelle += 1;
                let wert = self.summe()?;
                if !matches!(self.schau(), Some(Baustein::Klammer(')'))) {
                    return Err(RechenFehler::neu(
                        "Ungültiger Ausdruck: Es fehlt eine schließende Klammer.",
                    ));
                }
                self.stelle += 1;
                Ok(wert)
            }
            Some(Baustein::Name(name)) => {
                self.stelle += 1;
                if matches!(self.schau(), Some(Baustein::Klammer('('))) {
                    let argumente = self.argumente()?;
                    return funktion(&name, &argumente);
                }
                match name.as_str() {
                    "pi" => Ok(std::f64::consts::PI),
                    "e" => Ok(std::f64::consts::E),
                    "tau" => Ok(std::f64::consts::TAU),
                    _ => Err(RechenFehler::neu(format!("Unbekannter Name: {name}"))),
                }
            }
            Some(Baustein::Operator(zeichen)) => Err(RechenFehler::neu(format!(
                "Ungültiger Ausdruck: „{zeichen}“ steht an falscher Stelle."
            ))),
            Some(_) => Err(RechenFehler::neu(
                "Ungültiger Ausdruck: unerwartetes Zeichen.",
            )),
            None => Err(RechenFehler::neu("Ungültiger Ausdruck: Er endet zu früh.")),
        }
    }

    /// Liest die Argumentliste eines Funktionsaufrufs.
    fn argumente(&mut self) -> Ergebnis<Vec<f64>> {
        // Die öffnende Klammer ist geprüft, aber noch nicht übersprungen.
        self.stelle += 1;
        let mut werte = Vec::new();
        if matches!(self.schau(), Some(Baustein::Klammer(')'))) {
            self.stelle += 1;
            return Ok(werte);
        }
        loop {
            werte.push(self.summe()?);
            match self.schau() {
                Some(Baustein::Komma) => {
                    self.stelle += 1;
                }
                Some(Baustein::Klammer(')')) => {
                    self.stelle += 1;
                    return Ok(werte);
                }
                _ => {
                    return Err(RechenFehler::neu(
                        "Ungültiger Ausdruck: Es fehlt eine schließende Klammer.",
                    ))
                }
            }
        }
    }
}

/// Ruft eine der erlaubten Funktionen auf.
fn funktion(name: &str, argumente: &[f64]) -> Ergebnis<f64> {
    let eines = |zweck: &str| -> Ergebnis<f64> {
        match argumente {
            [wert] => Ok(*wert),
            _ => Err(RechenFehler::neu(format!(
                "Die Funktion {zweck} erwartet genau einen Wert."
            ))),
        }
    };
    match name {
        "abs" => Ok(eines("abs")?.abs()),
        "round" => match argumente {
            [wert] => Ok(runde(*wert, 0)),
            [wert, stellen] => Ok(runde(*wert, *stellen as i32)),
            _ => Err(RechenFehler::neu(
                "Die Funktion round erwartet einen oder zwei Werte.",
            )),
        },
        "min" | "max" | "sum" => {
            if argumente.is_empty() {
                return Err(RechenFehler::neu(format!(
                    "Die Funktion {name} erwartet mindestens einen Wert."
                )));
            }
            Ok(match name {
                "min" => argumente.iter().copied().fold(f64::INFINITY, f64::min),
                "max" => argumente.iter().copied().fold(f64::NEG_INFINITY, f64::max),
                _ => argumente.iter().sum(),
            })
        }
        "sqrt" => {
            let wert = eines("sqrt")?;
            if wert < 0.0 {
                return Err(RechenFehler::neu(
                    "Die Wurzel aus einer negativen Zahl ist nicht definiert.",
                ));
            }
            Ok(wert.sqrt())
        }
        "pow" => match argumente {
            [basis, exponent] => {
                if exponent.abs() > HOECHSTER_EXPONENT {
                    return Err(RechenFehler::neu(format!(
                        "Der Exponent darf höchstens {} sein.",
                        HOECHSTER_EXPONENT as i64
                    )));
                }
                if *basis == 0.0 && *exponent < 0.0 {
                    return Err(RechenFehler::neu("Division durch Null."));
                }
                Ok(basis.powf(*exponent))
            }
            _ => Err(RechenFehler::neu(
                "Die Funktion pow erwartet genau zwei Werte.",
            )),
        },
        "log" => match argumente {
            [wert] => logarithmus(*wert, std::f64::consts::E),
            [wert, grundzahl] => logarithmus(*wert, *grundzahl),
            _ => Err(RechenFehler::neu(
                "Die Funktion log erwartet einen oder zwei Werte.",
            )),
        },
        "log10" => logarithmus(eines("log10")?, 10.0),
        "exp" => Ok(eines("exp")?.exp()),
        "sin" => Ok(eines("sin")?.sin()),
        "cos" => Ok(eines("cos")?.cos()),
        "tan" => Ok(eines("tan")?.tan()),
        _ => Err(RechenFehler::neu(format!("Unbekannte Funktion: {name}"))),
    }
}

/// Berechnet den Logarithmus mit Prüfung des Wertebereichs.
fn logarithmus(wert: f64, grundzahl: f64) -> Ergebnis<f64> {
    if wert <= 0.0 {
        return Err(RechenFehler::neu(
            "Der Logarithmus ist nur für positive Zahlen definiert.",
        ));
    }
    if grundzahl <= 0.0 || grundzahl == 1.0 {
        return Err(RechenFehler::neu("Diese Grundzahl ist nicht erlaubt."));
    }
    // Für die üblichen Grundzahlen die genauen Rechenwege nutzen, damit
    // etwa „log10(1000)“ glatt 3 ergibt und nicht 2,999…
    if grundzahl == 10.0 {
        return Ok(wert.log10());
    }
    if grundzahl == std::f64::consts::E {
        return Ok(wert.ln());
    }
    if grundzahl == 2.0 {
        return Ok(wert.log2());
    }
    Ok(wert.ln() / grundzahl.ln())
}

/// Rundet wie Python: zur nächsten geraden Zahl bei genau 0,5.
fn runde(wert: f64, stellen: i32) -> f64 {
    let faktor = 10f64.powi(stellen);
    let verschoben = wert * faktor;
    let gerundet = if (verschoben.fract().abs() - 0.5).abs() < f64::EPSILON {
        let unten = verschoben.floor();
        if (unten / 2.0).fract() == 0.0 {
            unten
        } else {
            unten + 1.0
        }
    } else {
        verschoben.round()
    };
    gerundet / faktor
}

/// Wertet einen mathematischen Ausdruck aus.
///
/// `^` gilt als Potenz und `,` als Dezimaltrennzeichen – genau wie in der
/// bisherigen Python-Fassung.
pub fn berechne(ausdruck: &str) -> Ergebnis<f64> {
    if ausdruck.trim().is_empty() {
        return Err(RechenFehler::neu("Es wurde kein Ausdruck übergeben."));
    }
    if ausdruck.chars().count() > HOECHSTLAENGE {
        return Err(RechenFehler::neu("Der Ausdruck ist zu lang."));
    }
    let vorbereitet = ausdruck.replace('^', "**").replace(',', ".");
    let bausteine = zerlege(&vorbereitet)?;
    if bausteine.is_empty() {
        return Err(RechenFehler::neu("Es wurde kein Ausdruck übergeben."));
    }
    let mut auswertung = Auswertung {
        bausteine,
        stelle: 0,
    };
    let wert = auswertung.summe()?;
    if auswertung.stelle != auswertung.bausteine.len() {
        return Err(RechenFehler::neu(
            "Ungültiger Ausdruck: Er enthält überzählige Zeichen.",
        ));
    }
    if !wert.is_finite() {
        return Err(RechenFehler::neu("Das Ergebnis ist keine gültige Zahl."));
    }
    Ok(wert)
}

/// Gibt ein Ergebnis so aus, wie es die Oberfläche anzeigt.
///
/// Ganze Zahlen erscheinen ohne Nachkommastellen.
pub fn ergebnis_text(wert: f64) -> String {
    if wert.fract() == 0.0 && wert.abs() < 1e15 {
        format!("{}", wert as i64)
    } else {
        let text = format!("{wert}");
        text
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn wert(ausdruck: &str) -> f64 {
        berechne(ausdruck).expect("gültiger Ausdruck")
    }

    fn fehler(ausdruck: &str) -> String {
        berechne(ausdruck).expect_err("Fehler erwartet").meldung
    }

    #[test]
    fn grundrechenarten_stimmen() {
        assert_eq!(wert("1 + 2"), 3.0);
        assert_eq!(wert("2 + 3 * 4"), 14.0);
        assert_eq!(wert("(2 + 3) * 4"), 20.0);
        assert_eq!(wert("10 / 4"), 2.5);
        assert_eq!(wert("7 // 2"), 3.0);
        assert_eq!(wert("7 % 3"), 1.0);
        assert_eq!(wert("-7 % 3"), 2.0);
        assert_eq!(wert("2 ** 10"), 1024.0);
        assert_eq!(wert("2 ^ 8"), 256.0);
        assert_eq!(wert("2 ** 3 ** 2"), 512.0);
        assert_eq!(wert("-3 + 1"), -2.0);
        assert_eq!(wert("--3"), 3.0);
        assert_eq!(wert("+3"), 3.0);
    }

    #[test]
    fn komma_gilt_als_dezimaltrennzeichen() {
        assert_eq!(wert("1,5 * 2"), 3.0);
        assert_eq!(wert("0.25 + 0,25"), 0.5);
        assert_eq!(wert("1e-2 * 100"), 1.0);
    }

    #[test]
    fn funktionen_und_konstanten_stimmen() {
        assert_eq!(wert("abs(-4)"), 4.0);
        assert_eq!(wert("sqrt(16)"), 4.0);
        assert_eq!(wert("min(3;1;2)"), 1.0);
        assert_eq!(wert("max(3;1;2)"), 3.0);
        assert_eq!(wert("sum(1;2;3)"), 6.0);
        assert_eq!(wert("pow(2;5)"), 32.0);
        assert_eq!(wert("round(2.6)"), 3.0);
        assert_eq!(wert("round(2.5)"), 2.0);
        assert_eq!(wert("round(1.2345; 2)"), 1.23);
        assert_eq!(wert("log10(1000)"), 3.0);
        assert!((wert("log(e)") - 1.0).abs() < 1e-12);
        assert!((wert("exp(0)") - 1.0).abs() < 1e-12);
        assert!((wert("sin(0)")).abs() < 1e-12);
        assert!((wert("cos(0)") - 1.0).abs() < 1e-12);
        assert!((wert("tan(0)")).abs() < 1e-12);
        assert!((wert("pi") - std::f64::consts::PI).abs() < 1e-12);
        assert!((wert("tau") - std::f64::consts::TAU).abs() < 1e-12);
    }

    #[test]
    fn fehler_haben_deutsche_meldungen() {
        assert_eq!(fehler(""), "Es wurde kein Ausdruck übergeben.");
        assert_eq!(fehler("   "), "Es wurde kein Ausdruck übergeben.");
        assert_eq!(fehler(&"1+".repeat(200)), "Der Ausdruck ist zu lang.");
        assert_eq!(fehler("1 / 0"), "Division durch Null.");
        assert_eq!(fehler("5 % 0"), "Division durch Null.");
        assert_eq!(fehler("wurzel(4)"), "Unbekannte Funktion: wurzel");
        assert_eq!(fehler("unbekannt"), "Unbekannter Name: unbekannt");
        assert_eq!(fehler("2 ** 500"), "Der Exponent darf höchstens 64 sein.");
        assert!(fehler("(1 + 2").contains("schließende Klammer"));
        assert!(fehler("1 +").contains("endet zu früh"));
        assert!(fehler("1 2").contains("überzählige Zeichen"));
        assert_eq!(fehler("import os"), "Unbekannter Name: import");
        assert!(fehler("1 & 2").contains("nicht erlaubt"));
        assert!(fehler("sqrt(-1)").contains("negativen Zahl"));
        assert!(fehler("log(0)").contains("positive Zahlen"));
    }

    #[test]
    fn ganze_zahlen_werden_ohne_komma_ausgegeben() {
        assert_eq!(ergebnis_text(wert("2 + 2")), "4");
        assert_eq!(ergebnis_text(wert("10 / 4")), "2.5");
        assert_eq!(ergebnis_text(wert("6 / 3")), "2");
    }

    #[test]
    fn lange_ausdruecke_bis_zur_grenze_gehen() {
        let ausdruck = format!("1{}", " + 1".repeat(70));
        assert_eq!(wert(&ausdruck), 71.0);
    }
}
