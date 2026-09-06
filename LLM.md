# Aufbau der Anwendung – Shadow

Diese Datei beschreibt, wie die Module zusammenspielen. Der frühere Ordner
`core/` existiert nicht mehr: die Kernmodule liegen direkt im Projektordner.

Die Anwendung besteht aus zwei Sprachen: Python für alles, was PyTorch braucht
(Modell, Training, Chat) und für die CustomTkinter-Oberflächen; Rust für den
gemeinsamen Kern und die komplette Weboberfläche (Ordner `rust/`).

## Ordner

```
Shadow/
├── rust/            Cargo-Arbeitsbereich: kern, web, pybindungen
├── auth/            Anmeldung und Benutzerverwaltung (Hülle über dem Kern)
├── dev_tools/       Dashboard, Metriken, Bewertungen, Schicht-Training, Benchmarks
├── ui/              Theme, Widgets, Chat, Markdown, Gespräche, Diagramme
├── data/            Laufzeitdaten (wird beim ersten Start angelegt)
└── *.py             Modellkern, Hüllen und Einstiegspunkte
```

## Ablauf einer Anfrage

1. `gui.py` (oder `cli.py`) nimmt die Frage entgegen.
2. `llm_engine.ToolAugmentedLLM.chat_with_tools` erzeugt eine Antwort und
   erkennt darin Werkzeugaufrufe.
3. `mcp_protocol.MCPClient` liest den Aufruf aus dem Text
   (`{"tool_call": {"name": ..., "arguments": {...}}}`) und lässt ihn vom
   `MCPServer` ausführen.
4. Das Ergebnis geht zurück in den Verlauf, bis das Modell eine Antwort ohne
   Werkzeugaufruf liefert oder `max_tool_iterations` erreicht ist.
5. Teilstücke werden über `teilstueck_rueckmeldung` sofort angezeigt,
   `abbruch` (ein `threading.Event`) bricht die Erzeugung ab.

## Wichtige Schnittstellen

| Modul | Aufruf | Zweck |
| --- | --- | --- |
| `llm_engine` | `chat_with_tools(frage, client, conversation_history=, teilstueck_rueckmeldung=, abbruch=)` | Antwort samt Werkzeugschleife |
| `ui.chat_interface` | `ChatOberflaeche(eltern, theme=, antwort_funktion=)` | Chatfenster |
| `ui.theme` | `hole_theme().setze_modus("Hell"/"Dunkel"/"System")` | Erscheinungsbild |
| `auth.auth_manager` | `AuthManager()`, `AnmeldeFenster`, `AuthManagerUI` | Konten |
| `dev_tools.metrics_tracker` | `hole_verfolgung().add(...)`, `zusammenfassung()` | Metriken |
| `dev_tools.feedback_mode` | `BewertungsSpeicher().fuege_hinzu(...)` | Bewertungen |
| `model_manager` | `train_step`, `soup`, `save_checkpoint`, `load_checkpoint` | Modelle |
| `kern_modul` | `from kern_modul import kern` | Zugriff auf das Rust-Modul `shadow_kern` |

Die Antwortfunktion der Chat-Oberfläche hat die Form:

```python
def antwort(frage, verlauf, melde_teilstueck, abbruch_ereignis) -> dict:
    return {"antwort": "...", "werkzeuge": ["calculator"]}
```

## Erscheinungsbild

`ui/theme.py` hält alle Farben als Paar `(hell, dunkel)`. Widgets fragen die
Farben über `FARBEN["name"]` ab; CustomTkinter wählt anhand des Modus
selbständig den passenden Wert. Wer auf einen Wechsel reagieren muss
(zum Beispiel die Diagramme), meldet sich mit
`theme.registriere_beobachter(funktion)` an.

## Rust-Kern und Python-Hüllen

`rust/kern` enthält die Logik und Datenhaltung genau einmal: Konfiguration,
Protokoll, Einstellungen, Schalter, Metriken, Bewertungen, Passwort-Hash und
Konten, Checkpoint-Ordner, Rechner. `rust/pybindungen` macht daraus mit PyO3
das Python-Modul `shadow_kern`.

Auf Python-Seite gilt: `kern_modul.kern` ist der einzige Einstieg, und
`config_loader.py`, `logger.py`, `settings_store.py`, `tools.py` (Rechner),
`dev_tools/metrics_tracker.py`, `dev_tools/feedback_mode.py` und
`auth/auth_manager.py` sind dünne Hüllen darüber. Sie behalten Schnittstelle,
Aliasnamen und Meldungstexte; es gibt keine zweite Fassung derselben Logik in
Python. Neue Regeln oder Formate gehören daher in den Rust-Kern, nicht in die
Hülle.

## Weboberfläche in Rust

`rust/web` ist die Weboberfläche (axum, Programm `shadow-web`):

- `routen.rs` – alle Seiten und Schnittstellen, gleiche Adressen, Statuscodes
  und JSON-Felder wie vorher (englische Zweitschlüssel bleiben erhalten)
- `sitzung.rs` – Sitzung als signiertes Cookie `shadow_sitzung` (`SECRET_KEY`)
- `zustand.rs` – gemeinsamer Zustand samt Schalter, Metriken, Bewertungen
- `vorlagen/` – Seiten als Rust-Funktionen (`anmeldeseite`,
  `zugangsdatenseite`, `trainingsseite`, `verwaltungsseite`); keine
  Vorlagensprache, keine `.html`-Dateien, Werte werden maskiert
- `bruecke.rs` – ruft für PyTorch-Aufgaben `kern_bruecke.py` als kurzen
  Python-Vorgang auf (Zeilenprotokoll aus JSON)

`python main.py --modus web` sucht das Programm über `SHADOW_WEB_BINAER`,
`rust/target/release`, `rust/target/debug` und den `PATH`.

## Ohne PyTorch

`gui.py`, `kern_bruecke.py` und das Dashboard laden `torch`, `transformers` und
`model_manager` erst bei Bedarf. Fehlt ein Paket, bleibt die Oberfläche
bedienbar; betroffene Aktionen melden den Grund in deutscher Sprache
(Weboberfläche: HTTP 503 mit dem Feld `fehler`).
