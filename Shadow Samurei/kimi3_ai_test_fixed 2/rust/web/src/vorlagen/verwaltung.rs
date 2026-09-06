//! Der Verwaltungsbereich der Weboberfläche.

use super::bausteine::{
    element, hinweis, kachel, karte, kommazahl, leer, leermeldung, prozent, schalterzeile, tabelle,
    text, verbinde, wert, zeitpunkt, RohHtml,
};
use super::grundgeruest::seite;
use super::training::checkpoint_tabelle;
use super::typen::{Adressen, Checkpoint, Metrik, Schalter, Zusammenfassung};

/// Beschreibung der vier globalen Schalter: Feldkennung, Titel, Text.
///
/// Der Zugriff auf den zugehörigen Schalterwert erfolgt über den Index.
pub const SCHALTER_BESCHREIBUNG: [(&str, &str, &str); 4] = [
    (
        "schalter-bewertung",
        "Bewertungsmodus",
        "Erlaubt das Bewerten von Antworten",
    ),
    (
        "schalter-diagramm",
        "Metriken anzeigen",
        "Zeigt Diagramme und Tabellen im Trainingsbereich",
    ),
    (
        "schalter-schichten",
        "Schicht-Training",
        "Erlaubt das gezielte Training einzelner Schichten",
    ),
    (
        "schalter-benchmarks",
        "Automatische Benchmarks",
        "Vergleichsläufe im Hintergrund",
    ),
];

/// JavaScript des Verwaltungsbereichs.
pub const SKRIPT_VERWALTUNG: &str = r#"
const SCHALTER_FELDER = {
    bewertungsmodus: 'schalter-bewertung',
    zeige_diagramm: 'schalter-diagramm',
    schicht_training: 'schalter-schichten',
    auto_benchmarks: 'schalter-benchmarks',
};

async function aktualisiereSchalter() {
    const status = document.getElementById('schalter-status');
    const inhalt = {};
    Object.entries(SCHALTER_FELDER).forEach(([name, kennung]) => {
        inhalt[name] = document.getElementById(kennung).checked;
    });
    status.textContent = 'Wird gespeichert ...';
    status.style.color = 'var(--gedaempft)';
    try {
        const daten = await sendeJson('/api/toggles', inhalt);
        status.textContent = 'Gespeichert. Benchmarks: '
            + (daten.benchmarks_laeuft ? 'laufen' : 'gestoppt');
        status.style.color = 'var(--erfolg)';
    } catch (fehler) {
        status.textContent = fehler.message;
        status.style.color = 'var(--gefahr)';
        document.getElementById(SCHALTER_FELDER.auto_benchmarks).checked = false;
    }
}

Object.values(SCHALTER_FELDER).forEach((kennung) => {
    document.getElementById(kennung).addEventListener('change', aktualisiereSchalter);
});

async function ladeCheckpoint(kennung) {
    try {
        await sendeJson('/api/checkpoints/' + kennung + '/use');
        alert('Checkpoint als Arbeitsmodell geladen.');
    } catch (fehler) {
        alert(fehler.message);
    }
}

async function loescheCheckpoint(kennung) {
    if (!confirm('Checkpoint wirklich löschen?')) { return; }
    try {
        await sendeJson('/api/checkpoints/' + kennung + '/delete');
        location.reload();
    } catch (fehler) {
        alert(fehler.message);
    }
}
"#;

/// Erzeugt die Karte mit den vier globalen Schaltern.
fn schalterkarte(schalter: &Schalter) -> RohHtml {
    let werte = [
        schalter.bewertungsmodus,
        schalter.zeige_diagramm,
        schalter.schicht_training,
        schalter.auto_benchmarks,
    ];
    let zeilen: Vec<RohHtml> = SCHALTER_BESCHREIBUNG
        .iter()
        .zip(werte.iter())
        .map(|((feld, titel, beschreibung), aktiv)| {
            schalterzeile(feld, titel, beschreibung, *aktiv)
        })
        .collect();
    karte(
        "Globale Schalter",
        &[
            element(
                "div",
                &[(
                    "style",
                    wert("display:flex;flex-direction:column;gap:16px;"),
                )],
                &[verbinde(&zeilen, "\n")],
            ),
            element(
                "div",
                &[
                    ("id", wert("schalter-status")),
                    (
                        "style",
                        wert("margin-top:12px;font-size:0.9rem;color:var(--gedaempft);"),
                    ),
                ],
                &[],
            ),
        ],
        None,
        "",
    )
}

/// Erzeugt die Karte mit dem Systemzustand.
fn zustandskarte(
    anzahl_checkpoints: usize,
    anzahl_metriken: usize,
    benchmarks_aktiv: bool,
    benutzer: &str,
    zusammenfassung: Option<&Zusammenfassung>,
) -> RohHtml {
    let kacheln = element(
        "div",
        &[("class", wert("raster-2")), ("style", wert("gap:16px;"))],
        &[
            kachel(&anzahl_checkpoints.to_string(), "Checkpoints", ""),
            kachel(&anzahl_metriken.to_string(), "Metrik-Einträge", ""),
            kachel(
                if benchmarks_aktiv { "Aktiv" } else { "Aus" },
                "Benchmarks",
                "",
            ),
            kachel(
                if benutzer.is_empty() { "–" } else { benutzer },
                "Angemeldet als",
                "font-size:1.1rem;",
            ),
        ],
    );
    let mut inhalt = vec![kacheln];
    if let Some(werte) = zusammenfassung {
        if werte.anzahl > 0 {
            inhalt.push(element(
                "div",
                &[
                    ("class", wert("raster-2")),
                    ("style", wert("gap:16px;margin-top:16px;")),
                ],
                &[
                    kachel(
                        &prozent(Some(werte.beste_genauigkeit), 2),
                        "Beste Genauigkeit",
                        "",
                    ),
                    kachel(&werte.tokens_gesamt.to_string(), "Tokens insgesamt", ""),
                ],
            ));
        }
    }
    karte("Systemzustand", &inhalt, None, "")
}

/// Erzeugt die Tabelle aller Metrik-Einträge, neueste zuerst.
pub fn metriktabelle(metriken: &[Metrik]) -> RohHtml {
    if metriken.is_empty() {
        return leermeldung("Noch keine Metriken vorhanden.");
    }
    let zeilen: Vec<Vec<RohHtml>> = metriken
        .iter()
        .rev()
        .map(|eintrag| {
            vec![
                text(&zeitpunkt(&eintrag.zeitstempel)),
                if eintrag.modell.is_empty() {
                    text("–")
                } else {
                    text(&eintrag.modell)
                },
                text(&prozent(Some(eintrag.genauigkeit), 2)),
                text(&kommazahl(Some(eintrag.verlust), 4, "")),
                text(&kommazahl(Some(eintrag.trainingszeit), 2, "s")),
                text(&eintrag.tokens.to_string()),
                text(&eintrag.epochen.to_string()),
            ]
        })
        .collect();
    tabelle(
        &[
            "Zeitpunkt",
            "Modell",
            "Genauigkeit",
            "Verlust",
            "Dauer",
            "Tokens",
            "Epochen",
        ],
        &zeilen,
    )
}

/// Baut die Seite des Verwaltungsbereichs.
#[allow(clippy::too_many_arguments)]
pub fn verwaltungsseite(
    schalter: &Schalter,
    checkpoints: &[Checkpoint],
    metriken: &[Metrik],
    zusammenfassung: Option<&Zusammenfassung>,
    benchmarks_aktiv: bool,
    benutzer: &str,
    kern_fehler: Option<&str>,
    adressen: &Adressen,
) -> String {
    let bereiche = vec![
        element(
            "h1",
            &[("style", wert("margin-bottom:20px;"))],
            &[text("Verwaltungsbereich")],
        ),
        match kern_fehler {
            Some(meldung) => hinweis(meldung, "warnung"),
            None => leer(),
        },
        element(
            "div",
            &[("class", wert("raster-2"))],
            &[
                schalterkarte(schalter),
                zustandskarte(
                    checkpoints.len(),
                    metriken.len(),
                    benchmarks_aktiv,
                    benutzer,
                    zusammenfassung,
                ),
            ],
        ),
        karte(
            "Alle Metriken",
            &[metriktabelle(metriken)],
            None,
            "margin-top:20px;",
        ),
        karte(
            "Checkpoint-Verwaltung",
            &[checkpoint_tabelle(checkpoints, true)],
            None,
            "margin-top:20px;",
        ),
    ];
    seite(
        "Verwaltung – Kimi3",
        &bereiche,
        SKRIPT_VERWALTUNG,
        true,
        benutzer,
        adressen,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn beispiel_metrik() -> Metrik {
        Metrik {
            zeitstempel: "2026-01-01T10:00:00".to_string(),
            modell: "Kimi3 <klein>".to_string(),
            genauigkeit: 0.8712,
            verlust: 0.1234,
            trainingszeit: 12.5,
            tokens: 4096,
            epochen: 10,
        }
    }

    #[test]
    fn verwaltungsseite_enthaelt_alle_schalter() {
        let html = verwaltungsseite(
            &Schalter {
                auto_benchmarks: true,
                ..Schalter::default()
            },
            &[],
            &[beispiel_metrik()],
            Some(&Zusammenfassung {
                anzahl: 1,
                beste_genauigkeit: 0.9,
                tokens_gesamt: 4096,
            }),
            true,
            "admin",
            None,
            &Adressen::default(),
        );
        assert!(html.starts_with("<!DOCTYPE html>"));
        assert!(html.contains("<title>Verwaltung – Kimi3</title>"));
        for kennung in [
            "schalter-bewertung",
            "schalter-diagramm",
            "schalter-schichten",
            "schalter-benchmarks",
            "schalter-status",
        ] {
            assert!(html.contains(kennung), "{} fehlt", kennung);
        }
        assert!(html.contains("Beste Genauigkeit"));
        assert!(html.contains("Kimi3 &lt;klein&gt;"));
        assert!(html.contains("aktualisiereSchalter"));
    }

    #[test]
    fn nur_aktive_schalter_sind_angekreuzt() {
        let html = verwaltungsseite(
            &Schalter {
                auto_benchmarks: true,
                ..Schalter::default()
            },
            &[],
            &[],
            None,
            false,
            "admin",
            None,
            &Adressen::default(),
        );
        assert!(html.contains("id=\"schalter-benchmarks\" checked"));
        assert!(html.contains("id=\"schalter-bewertung\">"));
    }

    #[test]
    fn leere_listen_ergeben_leermeldungen() {
        let html = verwaltungsseite(
            &Schalter::default(),
            &[],
            &[],
            None,
            false,
            "",
            None,
            &Adressen::default(),
        );
        assert!(html.contains("Noch keine Metriken vorhanden."));
        assert!(html.contains("Noch keine Checkpoints vorhanden."));
        assert!(!html.contains("Beste Genauigkeit"));
        assert!(html.contains(">–</div>"));
    }

    #[test]
    fn metriktabelle_zeigt_neueste_zuerst() {
        let mut erste = beispiel_metrik();
        erste.modell = "alt".to_string();
        let mut zweite = beispiel_metrik();
        zweite.modell = "neu".to_string();
        let html = metriktabelle(&[erste, zweite]).in_zeichenkette();
        let stelle_neu = html.find("neu").unwrap_or(usize::MAX);
        let stelle_alt = html.find("alt").unwrap_or(0);
        assert!(stelle_neu < stelle_alt);
        assert!(html.contains("12.50 s"));
        assert!(html.contains("0.1234"));
    }
}
