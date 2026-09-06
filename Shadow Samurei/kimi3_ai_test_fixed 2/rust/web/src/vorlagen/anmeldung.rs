//! Die Anmeldeseite und die Seite zum Ändern der Zugangsdaten.

use super::bausteine::{
    eingabefeld, element, hinweis, knopf, leer, roh, text, wert, Attribut, RohHtml,
};
use super::grundgeruest::seite;
use super::typen::Adressen;

/// Erzeugt die breite Schaltfläche unter einem Formular.
fn absenden(beschriftung: &str) -> RohHtml {
    knopf(
        beschriftung,
        "btn btn-primaer",
        &[
            ("type", wert("submit")),
            ("style", wert("width:100%;justify-content:center;")),
        ],
    )
}

/// Baut die Anmeldeseite.
pub fn anmeldeseite(fehler: Option<&str>, adressen: &Adressen) -> String {
    let formular = element(
        "form",
        &[
            ("method", wert("POST")),
            ("action", wert(adressen.anmeldung.clone())),
        ],
        &[
            element(
                "div",
                &[
                    ("class", wert("form-group")),
                    ("style", wert("text-align:left;")),
                ],
                &[
                    element(
                        "label",
                        &[("for", wert("username"))],
                        &[text("Benutzername")],
                    ),
                    element(
                        "input",
                        &[
                            ("type", wert("text")),
                            ("id", wert("username")),
                            ("name", wert("username")),
                            ("required", Attribut::Ja),
                            ("autofocus", Attribut::Ja),
                            ("autocomplete", wert("username")),
                        ],
                        &[],
                    ),
                ],
            ),
            element(
                "div",
                &[
                    ("class", wert("form-group")),
                    ("style", wert("text-align:left;")),
                ],
                &[
                    element("label", &[("for", wert("password"))], &[text("Passwort")]),
                    element(
                        "input",
                        &[
                            ("type", wert("password")),
                            ("id", wert("password")),
                            ("name", wert("password")),
                            ("required", Attribut::Ja),
                            ("autocomplete", wert("current-password")),
                        ],
                        &[],
                    ),
                ],
            ),
            absenden("Anmelden"),
        ],
    );
    let kasten = element(
        "div",
        &[("class", wert("card")), ("style", wert("text-align:center;"))],
        &[
            element(
                "h1",
                &[("style", wert("margin-bottom:4px;color:var(--akzent);"))],
                &[text("Kimi3")],
            ),
            element(
                "p",
                &[("style", wert("color:var(--gedaempft);margin-bottom:24px;"))],
                &[text("Verwaltungsbereich")],
            ),
            match fehler {
                Some(meldung) => hinweis(meldung, "fehler"),
                None => leer(),
            },
            formular,
            element(
                "p",
                &[(
                    "style",
                    wert("color:var(--gedaempft);font-size:0.82rem;margin-top:16px;"),
                )],
                &[roh(
                    "Beim ersten Start gilt das Standardkonto aus der Datei \
                     <code>config.yaml</code>. Das Passwort muss danach geändert werden.",
                )],
            ),
        ],
    );
    seite(
        "Anmeldung – Kimi3",
        &[element(
            "div",
            &[("style", wert("max-width:420px;margin:80px auto;"))],
            &[kasten],
        )],
        "",
        false,
        "",
        adressen,
    )
}

/// Baut die Seite zum Ändern von Benutzername und Passwort.
pub fn zugangsdatenseite(
    benutzer: &str,
    meldung: Option<&str>,
    erzwungen: bool,
    adressen: &Adressen,
) -> String {
    let formular = element(
        "form",
        &[
            ("method", wert("POST")),
            ("action", wert(adressen.zugangsdaten.clone())),
        ],
        &[
            eingabefeld(
                "username",
                "Neuer Benutzername",
                "text",
                None,
                &[
                    ("value", wert(benutzer)),
                    ("required", Attribut::Ja),
                    ("autocomplete", wert("username")),
                ],
            ),
            eingabefeld(
                "password",
                "Neues Passwort",
                "password",
                None,
                &[
                    ("required", Attribut::Ja),
                    ("placeholder", wert("Mindestens 4 Zeichen")),
                    ("autocomplete", wert("new-password")),
                ],
            ),
            eingabefeld(
                "password2",
                "Passwort wiederholen",
                "password",
                None,
                &[
                    ("required", Attribut::Ja),
                    ("autocomplete", wert("new-password")),
                ],
            ),
            absenden("Speichern"),
        ],
    );
    let kasten = element(
        "div",
        &[("class", wert("card"))],
        &[
            element(
                "h2",
                &[("style", wert("margin-bottom:16px;"))],
                &[text("Zugangsdaten ändern")],
            ),
            if erzwungen {
                hinweis(
                    "Bitte lege bei der ersten Anmeldung eigene Zugangsdaten fest.",
                    "info",
                )
            } else {
                leer()
            },
            match meldung {
                Some(inhalt) => hinweis(inhalt, "fehler"),
                None => leer(),
            },
            formular,
        ],
    );
    seite(
        "Zugangsdaten ändern – Kimi3",
        &[element(
            "div",
            &[("style", wert("max-width:440px;margin:60px auto;"))],
            &[kasten],
        )],
        "",
        false,
        benutzer,
        adressen,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn anmeldeseite_enthaelt_formular_und_titel() {
        let html = anmeldeseite(None, &Adressen::default());
        assert!(html.starts_with("<!DOCTYPE html>"));
        assert!(html.contains("<title>Anmeldung – Kimi3</title>"));
        assert!(html.contains("action=\"/login\""));
        assert!(html.contains("id=\"username\""));
        assert!(html.contains("id=\"password\""));
        assert!(html.contains(">Anmelden</button>"));
        assert!(html.contains("<code>config.yaml</code>"));
    }

    #[test]
    fn anmeldeseite_zeigt_fehlermeldung_maskiert() {
        let html = anmeldeseite(Some("Ungültig <B>"), &Adressen::default());
        assert!(html.contains("class=\"hinweis hinweis-fehler\""));
        assert!(html.contains("Ungültig &lt;B&gt;"));
    }

    #[test]
    fn zugangsdatenseite_enthaelt_alle_felder() {
        let html = zugangsdatenseite("admin", None, false, &Adressen::default());
        assert!(html.starts_with("<!DOCTYPE html>"));
        assert!(html.contains("<title>Zugangsdaten ändern – Kimi3</title>"));
        assert!(html.contains("action=\"/change-credentials\""));
        assert!(html.contains("id=\"password2\""));
        assert!(html.contains("value=\"admin\""));
        assert!(!html.contains("class=\"hinweis hinweis-info\""));
    }

    #[test]
    fn erzwungene_aenderung_zeigt_hinweis() {
        let html = zugangsdatenseite("admin", Some("Zu kurz"), true, &Adressen::default());
        assert!(html.contains("class=\"hinweis hinweis-info\""));
        assert!(html.contains("class=\"hinweis hinweis-fehler\""));
        assert!(html.contains("Zu kurz"));
    }
}
