//! Kleine Bausteine zum Erzeugen von HTML in reinem Rust.
//!
//! Die Weboberfläche verwendet keine Vorlagendateien. Stattdessen bauen die
//! Funktionen in diesem Modul den HTML-Text zusammen. Alle Werte, die aus
//! Daten stammen, laufen dabei über [`sicher`] und werden maskiert.

use std::fmt;

/// Zeichenkette, die unverändert in die Seite geschrieben wird.
///
/// Das Gegenstück zur Python-Klasse `RohHtml`: Inhalt vom Typ [`RohHtml`]
/// wurde bereits maskiert oder ist bewusst als fertiges HTML gedacht.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RohHtml(String);

impl RohHtml {
    /// Gibt den enthaltenen HTML-Text aus.
    pub fn als_text(&self) -> &str {
        &self.0
    }

    /// Wandelt den Baustein in eine gewöhnliche Zeichenkette um.
    pub fn in_zeichenkette(self) -> String {
        self.0
    }

    /// Meldet, ob der Baustein leer ist.
    pub fn ist_leer(&self) -> bool {
        self.0.is_empty()
    }
}

impl fmt::Display for RohHtml {
    fn fmt(&self, ausgabe: &mut fmt::Formatter<'_>) -> fmt::Result {
        ausgabe.write_str(&self.0)
    }
}

/// Markiert fertigen HTML-Text als „nicht mehr maskieren“.
pub fn roh(text: impl Into<String>) -> RohHtml {
    RohHtml(text.into())
}

/// Erzeugt einen leeren Baustein (Entsprechung zu `roh("")`).
pub fn leer() -> RohHtml {
    RohHtml(String::new())
}

/// Maskiert einen Wert für die Ausgabe in HTML.
///
/// Maskiert werden `&`, `<`, `>`, `"` und `'` – genau wie
/// `html.escape(..., quote=True)` in Python.
pub fn sicher(wert: &str) -> String {
    let mut ausgabe = String::with_capacity(wert.len());
    for zeichen in wert.chars() {
        match zeichen {
            '&' => ausgabe.push_str("&amp;"),
            '<' => ausgabe.push_str("&lt;"),
            '>' => ausgabe.push_str("&gt;"),
            '"' => ausgabe.push_str("&quot;"),
            '\'' => ausgabe.push_str("&#x27;"),
            sonst => ausgabe.push(sonst),
        }
    }
    ausgabe
}

/// Maskiert einen wahlweisen Wert; `None` wird zu einem Gedankenstrich.
pub fn sicher_wahl(wert: Option<&str>) -> String {
    match wert {
        Some(inhalt) => sicher(inhalt),
        None => "–".to_string(),
    }
}

/// Gibt einen Wahrheitswert als „ja“ oder „nein“ aus.
pub fn wahrheit(wert: bool) -> &'static str {
    if wert {
        "ja"
    } else {
        "nein"
    }
}

/// Erzeugt einen maskierten Textknoten.
pub fn text(wert: &str) -> RohHtml {
    roh(sicher(wert))
}

/// Erzeugt einen maskierten Textknoten; `None` wird zu einem Gedankenstrich.
pub fn text_wahl(wert: Option<&str>) -> RohHtml {
    roh(sicher_wahl(wert))
}

/// Der Wert eines HTML-Attributs.
///
/// `Ja` erzeugt ein Attribut ohne Wert (zum Beispiel `required`),
/// `Nein` lässt das Attribut ganz weg.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Attribut {
    /// Attribut mit maskiertem Wert.
    Wert(String),
    /// Attribut ohne Wert.
    Ja,
    /// Attribut wird weggelassen.
    Nein,
}

/// Kurzform für ein Attribut mit Wert.
pub fn wert(inhalt: impl Into<String>) -> Attribut {
    Attribut::Wert(inhalt.into())
}

/// Attribut ohne Wert, das nur bei `true` erscheint.
pub fn wenn(bedingung: bool) -> Attribut {
    if bedingung {
        Attribut::Ja
    } else {
        Attribut::Nein
    }
}

/// Attribut mit Wert, das bei leerem Text weggelassen wird.
pub fn wert_falls_gefuellt(inhalt: &str) -> Attribut {
    if inhalt.is_empty() {
        Attribut::Nein
    } else {
        Attribut::Wert(inhalt.to_string())
    }
}

/// Baut eine Attributliste für ein HTML-Element.
pub fn attribute(angaben: &[(&str, Attribut)]) -> String {
    let mut teile: Vec<String> = Vec::new();
    for (name, angabe) in angaben {
        match angabe {
            Attribut::Nein => continue,
            Attribut::Ja => teile.push((*name).to_string()),
            Attribut::Wert(inhalt) => teile.push(format!("{}=\"{}\"", name, sicher(inhalt))),
        }
    }
    if teile.is_empty() {
        String::new()
    } else {
        format!(" {}", teile.join(" "))
    }
}

/// HTML-Elemente ohne Inhalt und ohne schließendes Kennzeichen.
pub const LEERE_ELEMENTE: [&str; 6] = ["input", "meta", "br", "hr", "img", "link"];

/// Erzeugt ein HTML-Element mit Attributen und Inhalt.
pub fn element(marke: &str, angaben: &[(&str, Attribut)], inhalt: &[RohHtml]) -> RohHtml {
    let kopf = format!("<{}{}>", marke, attribute(angaben));
    if LEERE_ELEMENTE.contains(&marke) {
        return roh(kopf);
    }
    let mut ausgabe = kopf;
    for teil in inhalt {
        ausgabe.push_str(teil.als_text());
    }
    ausgabe.push_str(&format!("</{}>", marke));
    roh(ausgabe)
}

/// Fügt mehrere Bausteine mit einem Trenner zusammen.
pub fn verbinde(teile: &[RohHtml], trenner: &str) -> RohHtml {
    let gesammelt: Vec<&str> = teile.iter().map(RohHtml::als_text).collect();
    roh(gesammelt.join(trenner))
}

// --------------------------------------------------------------- Formatierung

/// Formatiert einen Anteil zwischen 0 und 1 als Prozentangabe.
pub fn prozent(anteil: Option<f64>, stellen: usize) -> String {
    match anteil {
        Some(zahl) if zahl.is_finite() => format!("{:.*} %", stellen, zahl * 100.0),
        _ => "–".to_string(),
    }
}

/// Formatiert eine Zahl mit fester Nachkommastellenzahl.
///
/// `None` wird – wie `float(wert or 0)` in Python – als Null behandelt.
pub fn kommazahl(zahl: Option<f64>, stellen: usize, einheit: &str) -> String {
    let sicherer_wert = match zahl {
        Some(inhalt) if inhalt.is_finite() => inhalt,
        Some(_) => return "–".to_string(),
        None => 0.0,
    };
    let text = format!("{:.*}", stellen, sicherer_wert);
    if einheit.is_empty() {
        text
    } else {
        format!("{} {}", text, einheit)
    }
}

/// Wandelt einen ISO-Zeitstempel in eine lesbare Form.
pub fn zeitpunkt(wert: &str) -> String {
    if wert.is_empty() {
        return "–".to_string();
    }
    wert.replace('T', " ").chars().take(19).collect()
}

// ------------------------------------------------------------- Sammelbausteine

/// Erzeugt einen farbigen Hinweiskasten (info, erfolg, warnung, fehler).
pub fn hinweis(inhalt: &str, stufe: &str) -> RohHtml {
    element(
        "div",
        &[("class", wert(format!("hinweis hinweis-{}", stufe)))],
        &[text(inhalt)],
    )
}

/// Erzeugt eine Karte mit Überschrift und beliebigem Inhalt.
pub fn karte(titel: &str, inhalt: &[RohHtml], kopf_zusatz: Option<RohHtml>, stil: &str) -> RohHtml {
    let kopf = element(
        "div",
        &[("class", wert("card-header"))],
        &[
            element("span", &[("class", wert("card-title"))], &[text(titel)]),
            kopf_zusatz.unwrap_or_else(leer),
        ],
    );
    let mut teile = vec![kopf];
    teile.extend_from_slice(inhalt);
    element(
        "div",
        &[("class", wert("card")), ("style", wert_falls_gefuellt(stil))],
        &teile,
    )
}

/// Erzeugt eine Schaltfläche.
///
/// Fehlt in `angaben` ein `type`, wird – wie `setdefault` in Python – am Ende
/// `type="button"` ergänzt.
pub fn knopf(beschriftung: &str, klasse: &str, angaben: &[(&str, Attribut)]) -> RohHtml {
    let mut alle: Vec<(&str, Attribut)> = vec![("class", wert(klasse))];
    alle.extend(angaben.iter().cloned());
    if !angaben.iter().any(|(name, _)| *name == "type") {
        alle.push(("type", wert("button")));
    }
    element("button", &alle, &[text(beschriftung)])
}

/// Erzeugt eine Tabelle aus Spaltentiteln und Zeileninhalten.
pub fn tabelle(spalten: &[&str], zeilen: &[Vec<RohHtml>]) -> RohHtml {
    let kopfzellen: Vec<RohHtml> = spalten
        .iter()
        .map(|name| element("th", &[], &[text(name)]))
        .collect();
    let kopf = element(
        "thead",
        &[],
        &[element("tr", &[], &[verbinde(&kopfzellen, "")])],
    );
    let koerperzeilen: Vec<RohHtml> = zeilen
        .iter()
        .map(|zeile| {
            let zellen: Vec<RohHtml> = zeile
                .iter()
                .map(|feld| element("td", &[], &[feld.clone()]))
                .collect();
            element("tr", &[], &[verbinde(&zellen, "")])
        })
        .collect();
    let koerper = element("tbody", &[], &[verbinde(&koerperzeilen, "\n")]);
    element("table", &[], &[kopf, koerper])
}

/// Erzeugt den Hinweis „noch keine Daten vorhanden“.
pub fn leermeldung(inhalt: &str) -> RohHtml {
    element(
        "p",
        &[(
            "style",
            wert("color:var(--gedaempft);text-align:center;padding:20px;"),
        )],
        &[text(inhalt)],
    )
}

/// Erzeugt eine Kennzahlkachel.
pub fn kachel(anzeigewert: &str, beschreibung: &str, wert_stil: &str) -> RohHtml {
    element(
        "div",
        &[("class", wert("kachel"))],
        &[
            element(
                "div",
                &[
                    ("class", wert("kennzahl")),
                    ("style", wert_falls_gefuellt(wert_stil)),
                ],
                &[text(anzeigewert)],
            ),
            element(
                "div",
                &[("class", wert("kennzahl-text"))],
                &[text(beschreibung)],
            ),
        ],
    )
}

/// Erzeugt ein beschriftetes Eingabefeld.
pub fn eingabefeld(
    kennung: &str,
    beschriftung: &str,
    typ: &str,
    hinweistext: Option<&str>,
    angaben: &[(&str, Attribut)],
) -> RohHtml {
    let feldname = angaben
        .iter()
        .find(|(name, _)| *name == "name")
        .and_then(|(_, angabe)| match angabe {
            Attribut::Wert(inhalt) => Some(inhalt.clone()),
            _ => None,
        })
        .unwrap_or_else(|| kennung.to_string());
    let mut alle: Vec<(&str, Attribut)> = vec![
        ("type", wert(typ)),
        ("id", wert(kennung)),
        ("name", wert(feldname)),
    ];
    alle.extend(
        angaben
            .iter()
            .filter(|(name, _)| *name != "name")
            .cloned(),
    );
    let fusszeile = match hinweistext {
        Some(inhalt) if !inhalt.is_empty() => element(
            "p",
            &[(
                "style",
                wert("color:var(--gedaempft);font-size:0.82rem;margin-top:6px;"),
            )],
            &[text(inhalt)],
        ),
        _ => leer(),
    };
    element(
        "div",
        &[("class", wert("form-group"))],
        &[
            element("label", &[("for", wert(kennung))], &[text(beschriftung)]),
            element("input", &alle, &[]),
            fusszeile,
        ],
    )
}

/// Erzeugt einen Schiebeschalter.
pub fn schieber(kennung: &str, aktiv: bool) -> RohHtml {
    element(
        "label",
        &[("class", wert("schalter"))],
        &[
            element(
                "input",
                &[
                    ("type", wert("checkbox")),
                    ("id", wert(kennung)),
                    ("checked", wenn(aktiv)),
                ],
                &[],
            ),
            element("span", &[("class", wert("regler"))], &[]),
        ],
    )
}

/// Erzeugt eine Zeile aus Titel, Beschreibung und Schiebeschalter.
pub fn schalterzeile(kennung: &str, titel: &str, beschreibung: &str, aktiv: bool) -> RohHtml {
    element(
        "div",
        &[(
            "style",
            wert("display:flex;justify-content:space-between;align-items:center;gap:12px;"),
        )],
        &[
            element(
                "div",
                &[],
                &[
                    element("strong", &[], &[text(titel)]),
                    element(
                        "p",
                        &[("style", wert("color:var(--gedaempft);font-size:0.85rem;"))],
                        &[text(beschreibung)],
                    ),
                ],
            ),
            schieber(kennung, aktiv),
        ],
    )
}

/// Erzeugt ein Ankreuzfeld mit Beschriftung.
pub fn auswahlkasten(kastenwert: &str, beschriftung: &str, name: Option<&str>) -> RohHtml {
    let namensangabe = match name {
        Some(inhalt) => wert(inhalt),
        None => Attribut::Nein,
    };
    element(
        "label",
        &[("class", wert("auswahl"))],
        &[
            element(
                "input",
                &[
                    ("type", wert("checkbox")),
                    ("value", wert(kastenwert)),
                    ("name", namensangabe),
                ],
                &[],
            ),
            roh(format!(" {}", sicher(beschriftung))),
        ],
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maskierung_greift_bei_spitzen_klammern() {
        assert_eq!(sicher("Lauf <B>"), "Lauf &lt;B&gt;");
        assert_eq!(sicher("a&b\"c'd"), "a&amp;b&quot;c&#x27;d");
    }

    #[test]
    fn fehlender_wert_wird_zum_gedankenstrich() {
        assert_eq!(sicher_wahl(None), "–");
        assert_eq!(text_wahl(Some("Lauf <B>")).als_text(), "Lauf &lt;B&gt;");
    }

    #[test]
    fn wahrheitswerte_werden_deutsch_ausgegeben() {
        assert_eq!(wahrheit(true), "ja");
        assert_eq!(wahrheit(false), "nein");
    }

    #[test]
    fn attribute_folgen_den_python_regeln() {
        let ausgabe = attribute(&[
            ("class", wert("card")),
            ("required", Attribut::Ja),
            ("style", Attribut::Nein),
        ]);
        assert_eq!(ausgabe, " class=\"card\" required");
        assert_eq!(attribute(&[]), "");
    }

    #[test]
    fn leere_elemente_haben_kein_schliessendes_kennzeichen() {
        let feld = element("input", &[("type", wert("text"))], &[]);
        assert_eq!(feld.als_text(), "<input type=\"text\">");
    }

    #[test]
    fn zahlformatierer_verhalten_sich_wie_python() {
        assert_eq!(prozent(Some(0.8712), 2), "87.12 %");
        assert_eq!(prozent(None, 2), "–");
        assert_eq!(kommazahl(Some(1.5), 4, ""), "1.5000");
        assert_eq!(kommazahl(None, 2, "s"), "0.00 s");
        assert_eq!(zeitpunkt("2026-01-01T10:00:00.123"), "2026-01-01 10:00:00");
        assert_eq!(zeitpunkt(""), "–");
    }

    #[test]
    fn knopf_ergaenzt_den_standardtyp() {
        let ohne = knopf("Laden", "btn", &[("onclick", wert("x()"))]);
        assert!(ohne.als_text().ends_with("type=\"button\">Laden</button>"));
        let mit = knopf("Senden", "btn", &[("type", wert("submit"))]);
        assert!(!mit.als_text().contains("button\""));
    }
}
