//! Grundgerüst aller Seiten: Kopf, Stilangaben, Navigation und Basis-Skript.

use super::bausteine::{element, leer, roh, text, verbinde, wert, RohHtml};
use super::typen::Adressen;

/// Alle CSS-Regeln der Oberfläche (Dunkel- und Hellmodus).
pub const STILANGABEN: &str = r#"
        /* Farbwerte für den Dunkelmodus (Standard) */
        :root,
        html[data-erscheinungsbild="dunkel"] {
            --hintergrund: #1c1a17;
            --flaeche: #26241f;
            --text: #f2efe9;
            --gedaempft: #a8a29a;
            --akzent: #c96442;
            --akzent-hover: #b5563a;
            --gefahr: #ef4444;
            --erfolg: #22c55e;
            --warnung: #f59e0b;
            --rahmen: #3a3630;
            --radius: 12px;
            --schatten: 0 4px 10px -2px rgba(0, 0, 0, 0.45);
        }
        /* Farbwerte für den Hellmodus */
        html[data-erscheinungsbild="hell"] {
            --hintergrund: #f7f5f2;
            --flaeche: #ffffff;
            --text: #24211d;
            --gedaempft: #6f6a62;
            --akzent: #c96442;
            --akzent-hover: #b5563a;
            --gefahr: #dc2626;
            --erfolg: #15803d;
            --warnung: #b45309;
            --rahmen: #e3ded6;
            --schatten: 0 4px 10px -4px rgba(0, 0, 0, 0.18);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, sans-serif;
            background: var(--hintergrund);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.5;
        }
        a { color: var(--akzent); text-decoration: none; }
        a:hover { text-decoration: underline; }
        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
        .card {
            background: var(--flaeche);
            border: 1px solid var(--rahmen);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: var(--schatten);
            margin-bottom: 20px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--rahmen);
        }
        .card-title { font-size: 1.2rem; font-weight: 600; }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 18px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.15s;
            color: #ffffff;
        }
        .btn[disabled] { opacity: 0.6; cursor: not-allowed; }
        .btn-primaer { background: var(--akzent); }
        .btn-primaer:hover { background: var(--akzent-hover); }
        .btn-gefahr { background: var(--gefahr); }
        .btn-erfolg { background: var(--erfolg); }
        .btn-klein { padding: 6px 12px; font-size: 0.85rem; }
        .btn-neben {
            background: transparent;
            color: var(--text);
            border: 1px solid var(--rahmen);
        }
        .form-group { margin-bottom: 16px; }
        label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            color: var(--gedaempft);
            font-size: 0.9rem;
        }
        input[type="text"], input[type="password"], input[type="number"], select {
            width: 100%;
            padding: 10px 14px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 8px;
            color: var(--text);
            font-size: 1rem;
        }
        input:focus, select:focus { outline: none; border-color: var(--akzent); }
        .hinweis {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 0.95rem;
            border: 1px solid var(--rahmen);
        }
        .hinweis-fehler { background: rgba(239, 68, 68, 0.14); color: var(--gefahr); }
        .hinweis-erfolg { background: rgba(34, 197, 94, 0.14); color: var(--erfolg); }
        .hinweis-info { background: rgba(201, 100, 66, 0.14); color: var(--akzent); }
        .hinweis-warnung { background: rgba(245, 158, 11, 0.14); color: var(--warnung); }
        .raster-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .raster-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        @media (max-width: 768px) {
            .raster-2, .raster-3 { grid-template-columns: 1fr; }
            .container { padding: 16px; }
        }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--rahmen); }
        th {
            color: var(--gedaempft);
            font-weight: 600;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .marke {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid var(--rahmen);
        }
        .marke-gruen { background: rgba(34, 197, 94, 0.18); color: var(--erfolg); }
        .marke-rot { background: rgba(239, 68, 68, 0.18); color: var(--gefahr); }
        .marke-akzent { background: rgba(201, 100, 66, 0.18); color: var(--akzent); }
        .schalter { position: relative; display: inline-block; width: 48px; height: 26px; }
        .schalter input { opacity: 0; width: 0; height: 0; }
        .regler {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background: var(--rahmen);
            border-radius: 26px;
            transition: 0.25s;
        }
        .regler:before {
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 3px;
            bottom: 3px;
            background: #ffffff;
            border-radius: 50%;
            transition: 0.25s;
        }
        input:checked + .regler { background: var(--akzent); }
        input:checked + .regler:before { transform: translateX(22px); }
        .navigation {
            display: flex;
            gap: 16px;
            padding: 16px 24px;
            background: var(--flaeche);
            border-bottom: 1px solid var(--rahmen);
            align-items: center;
        }
        .nav-marke { font-weight: 700; font-size: 1.1rem; color: var(--akzent); }
        .nav-abstand { flex: 1; }
        .nav-benutzer { color: var(--gedaempft); font-size: 0.9rem; }
        .kennzahl { font-size: 1.5rem; font-weight: 700; }
        .kennzahl-text { font-size: 0.85rem; color: var(--gedaempft); }
        .kachel {
            text-align: center;
            padding: 16px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 8px;
        }
        .fortschritt {
            height: 8px;
            background: var(--rahmen);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .fortschritt-fuellung {
            height: 100%;
            background: var(--akzent);
            border-radius: 4px;
            transition: width 0.3s;
        }
        .auswahlgruppe { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
        .auswahl {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 8px;
            cursor: pointer;
            user-select: none;
        }
        .auswahl input { accent-color: var(--akzent); }
        .balken-reihe { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
        .balken-spur {
            flex: 1;
            height: 14px;
            background: var(--hintergrund);
            border: 1px solid var(--rahmen);
            border-radius: 7px;
            overflow: hidden;
        }
        .balken-wert { height: 100%; background: var(--akzent); }
        .balken-text { width: 150px; font-size: 0.85rem; color: var(--gedaempft); }
"#;

/// JavaScript, das auf jeder Seite eingebunden wird.
pub const GRUNDSKRIPT: &str = r#"
    // Erscheinungsbild (hell/dunkel) wird im Browser gespeichert.
    function setzeErscheinungsbild(modus) {
        document.documentElement.setAttribute('data-erscheinungsbild', modus);
        localStorage.setItem('kimi3-erscheinungsbild', modus);
        const knopf = document.getElementById('erscheinungsbild-knopf');
        if (knopf) {
            knopf.textContent = modus === 'dunkel' ? 'Hell' : 'Dunkel';
        }
    }

    function wechsleErscheinungsbild() {
        const aktuell = document.documentElement.getAttribute('data-erscheinungsbild');
        setzeErscheinungsbild(aktuell === 'dunkel' ? 'hell' : 'dunkel');
    }

    setzeErscheinungsbild(localStorage.getItem('kimi3-erscheinungsbild') || 'dunkel');

    // Hilfsfunktion für alle Seiten: JSON an eine Schnittstelle senden.
    async function sendeJson(adresse, inhalt = {}) {
        const antwort = await fetch(adresse, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(inhalt),
        });
        const daten = await antwort.json();
        if (daten.fehler) {
            throw new Error(daten.fehler);
        }
        return daten;
    }
"#;

/// Erzeugt die Schaltfläche zum Wechsel zwischen Hell und Dunkel.
pub fn erscheinungsbild_knopf() -> RohHtml {
    element(
        "button",
        &[
            ("class", wert("btn btn-klein btn-neben")),
            ("id", wert("erscheinungsbild-knopf")),
            ("type", wert("button")),
            ("onclick", wert("wechsleErscheinungsbild()")),
        ],
        &[text("Hell")],
    )
}

/// Erzeugt die Navigationsleiste für angemeldete Administratoren.
pub fn navigation(benutzer: &str, adressen: &Adressen) -> RohHtml {
    element(
        "nav",
        &[("class", wert("navigation"))],
        &[
            element("div", &[("class", wert("nav-marke"))], &[text("Kimi3")]),
            element(
                "a",
                &[("href", wert(adressen.training.clone()))],
                &[text("Training")],
            ),
            element(
                "a",
                &[("href", wert(adressen.verwaltung.clone()))],
                &[text("Verwaltung")],
            ),
            element("div", &[("class", wert("nav-abstand"))], &[]),
            element("span", &[("class", wert("nav-benutzer"))], &[text(benutzer)]),
            erscheinungsbild_knopf(),
            element(
                "a",
                &[
                    ("href", wert(adressen.abmeldung.clone())),
                    ("style", wert("font-size:0.9rem;")),
                ],
                &[text("Abmelden")],
            ),
        ],
    )
}

/// Baut eine vollständige HTML-Seite.
///
/// `titel` steht im Browserfenster, `inhalt` sind fertige Bausteine und
/// `skript` ist zusätzlicher JavaScript-Text für diese Seite.
pub fn seite(
    titel: &str,
    inhalt: &[RohHtml],
    skript: &str,
    ist_admin: bool,
    benutzer: &str,
    adressen: &Adressen,
) -> String {
    let kopfleiste = if ist_admin {
        navigation(benutzer, adressen)
    } else {
        element(
            "div",
            &[("style", wert("position:fixed;top:16px;right:16px;"))],
            &[erscheinungsbild_knopf()],
        )
    };
    let seitenskript = if skript.trim().is_empty() {
        leer()
    } else {
        element("script", &[], &[roh(skript)])
    };
    let dokument = element(
        "html",
        &[
            ("lang", wert("de")),
            ("data-erscheinungsbild", wert("dunkel")),
        ],
        &[
            element(
                "head",
                &[],
                &[
                    element("meta", &[("charset", wert("UTF-8"))], &[]),
                    element(
                        "meta",
                        &[
                            ("name", wert("viewport")),
                            ("content", wert("width=device-width, initial-scale=1.0")),
                        ],
                        &[],
                    ),
                    element("title", &[], &[text(titel)]),
                    element("style", &[], &[roh(STILANGABEN)]),
                ],
            ),
            element(
                "body",
                &[],
                &[
                    kopfleiste,
                    element(
                        "div",
                        &[("class", wert("container"))],
                        &[verbinde(inhalt, "\n")],
                    ),
                    element("script", &[], &[roh(GRUNDSKRIPT)]),
                    seitenskript,
                ],
            ),
        ],
    );
    format!("<!DOCTYPE html>\n{}", dokument)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seite_hat_kopf_und_grundskript() {
        let html = seite(
            "Prüfseite – Kimi3",
            &[element("h1", &[], &[text("Inhalt")])],
            "",
            false,
            "",
            &Adressen::default(),
        );
        assert!(html.starts_with("<!DOCTYPE html>\n<html lang=\"de\""));
        assert!(html.contains("<title>Prüfseite – Kimi3</title>"));
        assert!(html.contains("--akzent: #c96442;"));
        assert!(html.contains("wechsleErscheinungsbild"));
        assert!(html.contains("erscheinungsbild-knopf"));
    }

    #[test]
    fn navigation_erscheint_nur_fuer_administratoren() {
        let adressen = Adressen::default();
        let mit = seite("A", &[], "", true, "admin", &adressen);
        assert!(mit.contains("class=\"navigation\""));
        assert!(mit.contains(">Abmelden</a>"));
        let ohne = seite("A", &[], "", false, "", &adressen);
        assert!(!ohne.contains("class=\"navigation\""));
    }

    #[test]
    fn seitenskript_wird_nur_bei_inhalt_eingebunden() {
        let adressen = Adressen::default();
        let mit = seite("A", &[], "alert(1);", false, "", &adressen);
        assert!(mit.contains("alert(1);"));
        let ohne = seite("A", &[], "   ", false, "", &adressen);
        assert_eq!(ohne.matches("<script>").count(), 1);
    }

    #[test]
    fn benutzername_wird_maskiert() {
        let html = seite("A", &[], "", true, "Lauf <B>", &Adressen::default());
        assert!(html.contains("Lauf &lt;B&gt;"));
        assert!(!html.contains("Lauf <B>"));
    }
}
