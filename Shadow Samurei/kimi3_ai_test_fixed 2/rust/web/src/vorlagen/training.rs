//! Die Trainingsseite der Weboberfläche.

use super::bausteine::{
    auswahlkasten, eingabefeld, element, hinweis, karte, knopf, leer, leermeldung, prozent, text,
    tabelle, verbinde, wert, RohHtml,
};
use super::grundgeruest::seite;
use super::typen::{Adressen, Checkpoint, Schalter};

/// JavaScript der Trainingsseite.
pub const SKRIPT_TRAINING: &str = r#"
// ------------------------------------------------------------------ Training
document.getElementById('training-formular').addEventListener('submit', async (ereignis) => {
    ereignis.preventDefault();
    const knopf = document.getElementById('training-knopf');
    const status = document.getElementById('training-status');
    const leiste = document.getElementById('fortschritt-leiste');
    const wert = document.getElementById('fortschritt-wert');
    const bereich = document.getElementById('training-ergebnis');
    const meldung = document.getElementById('training-meldung');

    knopf.disabled = true;
    knopf.textContent = 'Training läuft ...';
    status.textContent = 'Läuft';
    status.className = 'marke marke-akzent';
    leiste.style.display = 'block';
    wert.style.width = '10%';
    bereich.style.display = 'none';

    const felder = new FormData(ereignis.target);
    const schichten = Array.from(
        ereignis.target.querySelectorAll('input[name="layers"]:checked')
    ).map((feld) => feld.value);

    try {
        wert.style.width = '50%';
        const daten = await sendeJson('/api/train', {
            epochs: parseInt(felder.get('epochs'), 10),
            lr: parseFloat(felder.get('lr')),
            base_model: felder.get('base_model') || null,
            layers: schichten.length ? schichten : null,
        });
        wert.style.width = '100%';
        meldung.className = 'hinweis hinweis-erfolg';
        meldung.textContent =
            'Training abgeschlossen. Genauigkeit: '
            + (daten.genauigkeit * 100).toFixed(2) + ' % | Dauer: '
            + daten.trainingszeit.toFixed(2) + ' s | Tokens: ' + daten.tokens
            + ' | Schichten: '
            + (Array.isArray(daten.trainierte_schichten)
                ? daten.trainierte_schichten.join(', ')
                : daten.trainierte_schichten);
        bereich.style.display = 'block';
        status.textContent = 'Bereit';
        status.className = 'marke marke-gruen';
        setTimeout(() => location.reload(), 1800);
    } catch (fehler) {
        meldung.className = 'hinweis hinweis-fehler';
        meldung.textContent = fehler.message;
        bereich.style.display = 'block';
        status.textContent = 'Fehler';
        status.className = 'marke marke-rot';
    } finally {
        knopf.disabled = false;
        knopf.textContent = 'Training starten';
    }
});

// --------------------------------------------------------------- Checkpoints
async function speichereCheckpoint() {
    const name = prompt('Name des Checkpoints:');
    if (!name) { return; }
    try {
        await sendeJson('/api/checkpoints', {name: name, genauigkeit: null});
        location.reload();
    } catch (fehler) {
        alert(fehler.message);
    }
}

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

// ---------------------------------------------------------------------- SOUP
async function starteSoup() {
    const kennungen = Array.from(
        document.querySelectorAll('#soup-auswahl input:checked')
    ).map((feld) => feld.value);
    const bereich = document.getElementById('soup-ergebnis');
    if (kennungen.length < 2) {
        bereich.innerHTML =
            '<div class="hinweis hinweis-warnung">Bitte mindestens zwei Checkpoints wählen.</div>';
        return;
    }
    bereich.innerHTML = '<p style="color:var(--gedaempft)">SOUP wird erstellt ...</p>';
    try {
        const daten = await sendeJson('/api/train/soup', {checkpoint_ids: kennungen});
        bereich.innerHTML =
            '<div class="hinweis hinweis-erfolg">SOUP erstellt. Genauigkeit: '
            + (daten.genauigkeit * 100).toFixed(2) + ' % | Kennung: '
            + daten.checkpoint_kennung + '</div>';
        setTimeout(() => location.reload(), 2000);
    } catch (fehler) {
        bereich.innerHTML = '<div class="hinweis hinweis-fehler">' + fehler.message + '</div>';
    }
}
"#;

/// JavaScript zum Nachladen der Metriken.
pub const SKRIPT_METRIKEN: &str = r#"
// ------------------------------------------------------------------ Metriken
async function ladeMetriken() {
    const bereich = document.getElementById('metrik-bereich');
    try {
        const antwort = await fetch('/api/metrics');
        const daten = await antwort.json();
        const metriken = daten.metriken || [];
        if (!metriken.length) {
            bereich.innerHTML =
                '<p style="color:var(--gedaempft)">Noch keine Metriken vorhanden.</p>';
            return;
        }
        const letzte = metriken.slice(-8).reverse();
        const zeilen = letzte.map((eintrag) => {
            const anteil = Math.max(0, Math.min(1, eintrag.genauigkeit || 0));
            return '<tr>'
                + '<td>' + (eintrag.zeitstempel || '').replace('T', ' ').slice(0, 16) + '</td>'
                + '<td>' + eintrag.modell + '</td>'
                + '<td><div class="balken-reihe"><div class="balken-spur">'
                + '<div class="balken-wert" style="width:' + (anteil * 100).toFixed(1) + '%"></div>'
                + '</div><span class="balken-text">'
                + (anteil * 100).toFixed(2) + ' %</span></div></td>'
                + '<td>' + (eintrag.verlust || 0).toFixed(4) + '</td>'
                + '<td>' + (eintrag.trainingszeit || 0).toFixed(2) + ' s</td>'
                + '<td>' + eintrag.tokens + '</td>'
                + '</tr>';
        }).join('');
        bereich.innerHTML =
            '<table><thead><tr><th>Zeitpunkt</th><th>Modell</th><th>Genauigkeit</th>'
            + '<th>Verlust</th><th>Dauer</th><th>Tokens</th></tr></thead><tbody>'
            + zeilen + '</tbody></table>';
    } catch (fehler) {
        bereich.innerHTML =
            '<div class="hinweis hinweis-fehler">Metriken konnten nicht geladen werden.</div>';
    }
}

ladeMetriken();
setInterval(ladeMetriken, 5000);
"#;

/// Erzeugt das Auswahlfeld für den Basis-Checkpoint.
fn checkpoint_auswahl(checkpoints: &[Checkpoint]) -> RohHtml {
    let mut eintraege = vec![element(
        "option",
        &[("value", wert(""))],
        &[text("Ursprungsmodell")],
    )];
    for punkt in checkpoints {
        let mut beschriftung = punkt.name.clone();
        if punkt.genauigkeit.is_some() {
            beschriftung.push_str(&format!(" ({})", prozent(punkt.genauigkeit, 2)));
        }
        eintraege.push(element(
            "option",
            &[("value", wert(punkt.kennung.clone()))],
            &[text(&beschriftung)],
        ));
    }
    element(
        "div",
        &[("class", wert("form-group"))],
        &[
            element(
                "label",
                &[("for", wert("basis_modell"))],
                &[text("Basis-Checkpoint (optional)")],
            ),
            element(
                "select",
                &[("name", wert("base_model")), ("id", wert("basis_modell"))],
                &[verbinde(&eintraege, "")],
            ),
        ],
    )
}

/// Erzeugt die Ankreuzfelder für einzelne Schichten.
fn schichtauswahl(schichten: &[String], erlaubt: bool) -> RohHtml {
    if !erlaubt {
        return element(
            "p",
            &[(
                "style",
                wert("color:var(--gedaempft);font-size:0.85rem;margin-bottom:12px;"),
            )],
            &[text("Schicht-Training ist in der Verwaltung abgeschaltet.")],
        );
    }
    let kaesten: Vec<RohHtml> = schichten
        .iter()
        .map(|schicht| auswahlkasten(schicht, schicht, Some("layers")))
        .collect();
    element(
        "div",
        &[("class", wert("form-group"))],
        &[
            element("label", &[], &[text("Zu trainierende Schichten")]),
            element(
                "div",
                &[("class", wert("auswahlgruppe"))],
                &[verbinde(&kaesten, "\n")],
            ),
            element(
                "p",
                &[(
                    "style",
                    wert("color:var(--gedaempft);font-size:0.82rem;margin-top:6px;"),
                )],
                &[text("Ohne Auswahl werden alle Schichten trainiert.")],
            ),
        ],
    )
}

/// Erzeugt die Karte mit dem Trainingsformular.
fn trainingskarte(
    checkpoints: &[Checkpoint],
    schichten: &[String],
    schicht_training: bool,
) -> RohHtml {
    let formular = element(
        "form",
        &[("id", wert("training-formular"))],
        &[
            checkpoint_auswahl(checkpoints),
            eingabefeld(
                "epochen",
                "Epochen",
                "number",
                None,
                &[
                    ("name", wert("epochs")),
                    ("value", wert("10")),
                    ("min", wert("1")),
                    ("max", wert("1000")),
                ],
            ),
            eingabefeld(
                "lernrate",
                "Lernrate",
                "number",
                None,
                &[
                    ("name", wert("lr")),
                    ("value", wert("0.01")),
                    ("step", wert("0.001")),
                    ("min", wert("0.0001")),
                    ("max", wert("1")),
                ],
            ),
            schichtauswahl(schichten, schicht_training),
            knopf(
                "Training starten",
                "btn btn-primaer",
                &[("type", wert("submit")), ("id", wert("training-knopf"))],
            ),
        ],
    );
    karte(
        "Training starten",
        &[
            formular,
            element(
                "div",
                &[
                    ("id", wert("training-ergebnis")),
                    ("style", wert("margin-top:16px;display:none;")),
                ],
                &[element(
                    "div",
                    &[
                        ("class", wert("hinweis hinweis-erfolg")),
                        ("id", wert("training-meldung")),
                    ],
                    &[],
                )],
            ),
            element(
                "div",
                &[
                    ("class", wert("fortschritt")),
                    ("id", wert("fortschritt-leiste")),
                    ("style", wert("display:none;")),
                ],
                &[element(
                    "div",
                    &[
                        ("class", wert("fortschritt-fuellung")),
                        ("id", wert("fortschritt-wert")),
                        ("style", wert("width:0%")),
                    ],
                    &[],
                )],
            ),
        ],
        Some(element(
            "span",
            &[
                ("id", wert("training-status")),
                ("class", wert("marke marke-akzent")),
            ],
            &[text("Bereit")],
        )),
        "",
    )
}

/// Erzeugt die Tabelle der gespeicherten Checkpoints.
pub fn checkpoint_tabelle(checkpoints: &[Checkpoint], mit_kennung: bool) -> RohHtml {
    if checkpoints.is_empty() {
        return leermeldung("Noch keine Checkpoints vorhanden.");
    }
    let mut zeilen: Vec<Vec<RohHtml>> = Vec::new();
    for punkt in checkpoints {
        let aktionen = verbinde(
            &[
                knopf(
                    "Laden",
                    "btn btn-klein btn-primaer",
                    &[(
                        "onclick",
                        wert(format!("ladeCheckpoint('{}')", punkt.kennung)),
                    )],
                ),
                knopf(
                    "Löschen",
                    "btn btn-klein btn-gefahr",
                    &[(
                        "onclick",
                        wert(format!("loescheCheckpoint('{}')", punkt.kennung)),
                    )],
                ),
            ],
            " ",
        );
        let name_feld = if mit_kennung {
            element("code", &[], &[text(&punkt.kennung)])
        } else {
            element(
                "span",
                &[],
                &[
                    element("strong", &[], &[text(&punkt.name)]),
                    element("br", &[], &[]),
                    element(
                        "small",
                        &[("style", wert("color:var(--gedaempft)"))],
                        &[text(&punkt.kennung)],
                    ),
                ],
            )
        };
        let mut zeile = vec![name_feld];
        if mit_kennung {
            zeile.push(text(&punkt.name));
        }
        zeile.push(text(&prozent(punkt.genauigkeit, 2)));
        zeile.push(element(
            "span",
            &[(
                "style",
                wert("color:var(--gedaempft);font-size:0.85rem;"),
            )],
            &[text(&punkt.gespeichert_am)],
        ));
        zeile.push(aktionen);
        zeilen.push(zeile);
    }
    let spalten: &[&str] = if mit_kennung {
        &["Kennung", "Name", "Genauigkeit", "Gespeichert", "Aktionen"]
    } else {
        &["Name", "Genauigkeit", "Datum", "Aktionen"]
    };
    tabelle(spalten, &zeilen)
}

/// Erzeugt die Karte zum Mitteln mehrerer Modelle.
fn soupkarte(checkpoints: &[Checkpoint]) -> RohHtml {
    let kaesten: Vec<RohHtml> = checkpoints
        .iter()
        .map(|punkt| auswahlkasten(&punkt.kennung, &punkt.name, None))
        .collect();
    karte(
        "SOUP – Gewichte mitteln",
        &[
            element(
                "p",
                &[("style", wert("color:var(--gedaempft);margin-bottom:12px;"))],
                &[text(
                    "Wähle mindestens zwei Checkpoints aus. Ihre Gewichte werden gemittelt \
                     und als neues Modell gespeichert; die Ursprungsmodelle bleiben erhalten.",
                )],
            ),
            element(
                "div",
                &[
                    ("class", wert("auswahlgruppe")),
                    ("id", wert("soup-auswahl")),
                ],
                &[verbinde(&kaesten, "\n")],
            ),
            knopf(
                "SOUP erstellen",
                "btn btn-primaer",
                &[
                    ("style", wert("margin-top:12px;")),
                    ("onclick", wert("starteSoup()")),
                ],
            ),
            element(
                "div",
                &[("id", wert("soup-ergebnis")), ("style", wert("margin-top:12px;"))],
                &[],
            ),
        ],
        None,
        "margin-top:20px;",
    )
}

/// Baut die Trainingsseite.
pub fn trainingsseite(
    schalter: &Schalter,
    checkpoints: &[Checkpoint],
    schichten: &[String],
    benutzer: &str,
    kern_fehler: Option<&str>,
    adressen: &Adressen,
) -> String {
    let mut bereiche = vec![
        element(
            "h1",
            &[("style", wert("margin-bottom:20px;"))],
            &[text("Modell-Training")],
        ),
        match kern_fehler {
            Some(meldung) => hinweis(meldung, "warnung"),
            None => leer(),
        },
        element(
            "div",
            &[("class", wert("raster-2"))],
            &[
                trainingskarte(checkpoints, schichten, schalter.schicht_training),
                karte(
                    "Checkpoints",
                    &[checkpoint_tabelle(checkpoints, false)],
                    Some(knopf(
                        "Speichern",
                        "btn btn-klein btn-erfolg",
                        &[("onclick", wert("speichereCheckpoint()"))],
                    )),
                    "",
                ),
            ],
        ),
        soupkarte(checkpoints),
    ];
    let mut skript = SKRIPT_TRAINING.to_string();
    if schalter.zeige_diagramm {
        bereiche.push(karte(
            "Metriken",
            &[element(
                "div",
                &[("id", wert("metrik-bereich"))],
                &[element(
                    "p",
                    &[("style", wert("color:var(--gedaempft);"))],
                    &[text("Metriken werden geladen ...")],
                )],
            )],
            Some(element(
                "span",
                &[("class", wert("marke marke-gruen"))],
                &[text("Aktualisiert sich")],
            )),
            "margin-top:20px;",
        ));
        skript.push_str(SKRIPT_METRIKEN);
    }
    seite(
        "Training – Kimi3",
        &bereiche,
        &skript,
        true,
        benutzer,
        adressen,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn beispiel_checkpoints() -> Vec<Checkpoint> {
        vec![Checkpoint {
            kennung: "cp-1".to_string(),
            name: "Lauf <B>".to_string(),
            genauigkeit: Some(0.8712),
            gespeichert_am: "2026-01-01T10:00:00".to_string(),
        }]
    }

    #[test]
    fn trainingsseite_enthaelt_alle_kennungen() {
        let html = trainingsseite(
            &Schalter {
                schicht_training: true,
                zeige_diagramm: true,
                ..Schalter::default()
            },
            &beispiel_checkpoints(),
            &["schicht.0".to_string()],
            "admin",
            None,
            &Adressen::default(),
        );
        assert!(html.starts_with("<!DOCTYPE html>"));
        assert!(html.contains("<title>Training – Kimi3</title>"));
        for kennung in [
            "training-formular",
            "training-knopf",
            "training-status",
            "training-ergebnis",
            "training-meldung",
            "fortschritt-leiste",
            "fortschritt-wert",
            "soup-auswahl",
            "soup-ergebnis",
            "metrik-bereich",
        ] {
            assert!(html.contains(kennung), "{} fehlt", kennung);
        }
        assert!(html.contains("ladeMetriken"));
        assert!(html.contains("starteSoup()"));
    }

    #[test]
    fn checkpoint_name_wird_maskiert() {
        let html = trainingsseite(
            &Schalter::default(),
            &beispiel_checkpoints(),
            &[],
            "admin",
            None,
            &Adressen::default(),
        );
        assert!(html.contains("Lauf &lt;B&gt;"));
        assert!(!html.contains("Lauf <B>"));
        assert!(html.contains("87.12 %"));
    }

    #[test]
    fn leere_checkpointliste_ergibt_leermeldung() {
        let html = trainingsseite(
            &Schalter::default(),
            &[],
            &[],
            "admin",
            None,
            &Adressen::default(),
        );
        assert!(html.contains("Noch keine Checkpoints vorhanden."));
        assert!(html.contains("Schicht-Training ist in der Verwaltung abgeschaltet."));
        assert!(!html.contains("metrik-bereich"));
    }

    #[test]
    fn kernfehler_erscheint_als_warnung() {
        let html = trainingsseite(
            &Schalter::default(),
            &[],
            &[],
            "admin",
            Some("Kern nicht verfügbar"),
            &Adressen::default(),
        );
        assert!(html.contains("class=\"hinweis hinweis-warnung\""));
        assert!(html.contains("Kern nicht verfügbar"));
    }

    #[test]
    fn tabelle_mit_kennung_hat_fuenf_spalten() {
        let mit = checkpoint_tabelle(&beispiel_checkpoints(), true);
        assert!(mit.als_text().contains("<th>Kennung</th>"));
        assert!(mit.als_text().contains("<code>cp-1</code>"));
        let ohne = checkpoint_tabelle(&beispiel_checkpoints(), false);
        assert!(ohne.als_text().contains("<th>Datum</th>"));
        assert!(!ohne.als_text().contains("<th>Kennung</th>"));
    }
}
