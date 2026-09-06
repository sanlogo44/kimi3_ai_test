# kimi3_ai_test

Ein Projekt aus Python und Rust für einen Sprachassistenten mit
Werkzeugzugriff. Es enthält eine Desktop-Oberfläche im Stil von Claude, eine
Weboberfläche zur Verwaltung, ein Entwickler-Dashboard mit Diagrammen und einen
Werkzeug-Server nach dem MCP-Muster. Alle Texte, Kommentare und Oberflächen
sind deutsch – auch im Rust-Teil.

**Aufteilung:** Python bleibt dort, wo PyTorch nötig ist (Modell, Training,
Chat) und für die CustomTkinter-Oberflächen. Alles andere liegt in Rust
(Ordner `rust/`): der gemeinsame Kern und die komplette Weboberfläche. Ein
Arbeitsbereich enthält beides.

## Funktionsumfang

- **Chat-Oberfläche (CustomTkinter)** – Gesprächsblasen, laufend eintreffende
  Antworten, Abbruchknopf, Gesprächsliste in der Seitenleiste, Markdown- und
  Codeblock-Darstellung, Bewertung je Antwort.
- **Hell/Dunkel-Umschalter** – in der Seitenleiste der Desktop-Oberfläche und
  in der Weboberfläche; die Wahl wird gespeichert (`data/settings.json`).
- **Entwickler-Dashboard** – fünf Reiter (Übersicht, Metriken,
  Schicht-Training, Benchmarks, Checkpoints) mit Diagrammen auf Basis von
  matplotlib.
- **Benutzerverwaltung** – Konten anlegen, löschen, Rollen und Passwörter
  ändern, Passwortwechsel bei der ersten Anmeldung; Passwörter werden als
  Hash gespeichert.
- **Werkzeuge (MCP)** – Rechner (sichere Auswertung ohne `eval`), Wetter,
  Websuche und Uhrzeit; leicht erweiterbar.
- **Training** – Schicht-Training, SOUP (Mittelung mehrerer Modelle),
  Checkpoint-Verwaltung und Metrikaufzeichnung.

## Projektstruktur

```
kimi3_ai_test/
├── rust/                     # Rust-Arbeitsbereich (Kern und Weboberfläche)
│   ├── kern/                 #   Kern: Konfiguration, Protokoll, Einstellungen,
│   │                         #   Schalter, Metriken, Bewertungen, Konten,
│   │                         #   Checkpoints, Rechner
│   ├── web/                  #   Weboberfläche (axum) samt Seitenvorlagen
│   ├── pybindungen/          #   Python-Modul „kimi3_kern“ (PyO3)
│   └── bauen.sh              #   baut alles und legt „kimi3_kern.so“ ab
├── auth/                     # Anmeldung und Benutzerverwaltung
│   └── auth_manager.py       #   CustomTkinter-Oberfläche über dem Rust-Kern
├── dev_tools/                # Entwicklerwerkzeuge
│   ├── dev_dashboard.py      #   Dashboard mit Diagrammen
│   ├── feedback_mode.py      #   Bewertungen sammeln und anzeigen
│   ├── metrics_tracker.py    #   Metriken speichern und auswerten
│   ├── layer_trainer.py      #   Training einzelner Schichten
│   └── benchmarker.py        #   Vergleichsläufe
├── ui/                       # Bausteine der Desktop-Oberfläche
│   ├── theme.py              #   Farben, Schriften, Hell/Dunkel
│   ├── widgets.py            #   Karten, Knöpfe, Hinweise, Umschalter
│   ├── chat_interface.py     #   Chat-Oberfläche
│   ├── markdown_ansicht.py   #   Markdown- und Codedarstellung
│   ├── gespraech_speicher.py #   Gespräche speichern und laden
│   └── diagramme.py          #   matplotlib-Diagramme
├── data/                     # Laufzeitdaten (wird angelegt)
├── kimi3_kern.so             # gebautes Rust-Modul (durch rust/bauen.sh)
├── kern_modul.py             # lädt „kimi3_kern“ und erklärt fehlende Bauten
├── kern_bruecke.py           # Brücke: Rust-Web ruft damit PyTorch-Aufgaben auf
├── gui.py                    # Desktop-Oberfläche
├── cli.py                    # Terminal-Dialog
├── main.py                   # Einstiegspunkt
├── config.yaml               # Konfiguration
├── config_loader.py          # Konfiguration einlesen (Hülle um den Kern)
├── argumente.py              # deutsche Kommandozeilen-Hilfe
├── llm_engine.py             # Modell und Werkzeugschleife
├── mcp_protocol.py           # Werkzeug-Server und -Client
├── model_manager.py          # Modelle, Checkpoints, SOUP
├── settings_store.py         # Einstellungen der Oberfläche (Hülle)
├── tools.py                  # Werkzeugdefinitionen
├── logger.py                 # Farbige Protokollausgabe (Hülle)
├── analytics.py              # Kurzzugriff auf die Metriken
├── benchmarks.py             # Benchmarks im Hintergrund
└── train_tool_use.py         # Trainingsdaten für Werkzeugaufrufe
```

## Schnellstart

```bash
git clone https://github.com/sanlogo44/kimi3_ai_test.git
cd kimi3_ai_test

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

bash rust/bauen.sh              # Rust-Kern und Weboberfläche bauen (Pflicht)
```

`rust/bauen.sh` legt das Python-Modul `kimi3_kern.so` in den Projektordner und
das Programm der Weboberfläche unter `rust/target/release/kimi3-web` ab. Dafür
wird Rust benötigt (https://rustup.rs).

Starten:

```bash
python main.py                  # Desktop-Oberfläche
python main.py --modus web      # Weboberfläche auf http://localhost:5000
python main.py --modus cli      # Dialog im Terminal
```

Der Modus `web` startet das Rust-Programm `kimi3-web`; es lässt sich auch
direkt aufrufen:

```bash
rust/target/release/kimi3-web --host 127.0.0.1 --port 5000
```

Die Oberflächen starten auch ohne PyTorch. In diesem Fall bleiben Chat und
Training gesperrt und ein Hinweis nennt den Grund; Dashboard, Metriken,
Bewertungen und Benutzerverwaltung sind weiterhin bedienbar.

## Erste Anmeldung

Standardkonto: Benutzer `Admin`, Passwort `1234`. Das Passwort muss bei der
ersten Anmeldung geändert werden (`force_password_change` in `config.yaml`).
Die Konten liegen als Hash in `data/users.json`.

## Konfiguration

`config.yaml` steuert Protokollierung, Hardware, Modell und Training:

```yaml
model:
  name: "meta-llama/Meta-Llama-3-8B-Instruct"
  max_tool_iterations: 5

hardware:
  device: "auto"        # auto, cuda oder cpu
  use_4bit: true        # benötigt bitsandbytes und eine NVIDIA-Grafikkarte
  weights_dtype: "fp32"
```

## Aufbau in Rust

Der Ordner `rust/` ist ein Cargo-Arbeitsbereich mit drei Teilen:

| Teil | Inhalt |
| --- | --- |
| `kern` | Konfiguration (`config.yaml`), Protokoll, Einstellungen, Schalter, Metriken, Bewertungen, Passwort-Hash und Konten, Checkpoint-Ordner, Rechner |
| `web` | Weboberfläche mit axum: Routen, Sitzung über signiertes Cookie, Seitenvorlagen als Rust-Funktionen |
| `pybindungen` | Python-Modul `kimi3_kern` (PyO3) mit denselben Funktionen und Klassen für die Desktop-Oberfläche |

Die Python-Module `config_loader.py`, `logger.py`, `settings_store.py`,
`tools.py` (Rechner), `dev_tools/metrics_tracker.py`, `dev_tools/feedback_mode.py`
und `auth/auth_manager.py` sind dünne Hüllen über diesem Kern: gleiche
Schnittstelle, gleiche Dateiformate, gleiche deutsche Meldungen – die Logik
selbst steht nur einmal, nämlich in Rust.

Die Seitenvorlagen der Weboberfläche liegen als Rust-Funktionen in
`rust/web/src/vorlagen/` (`anmeldeseite`, `zugangsdatenseite`, `trainingsseite`,
`verwaltungsseite`). Es gibt keine Vorlagensprache und keine `.html`-Dateien;
Werte werden grundsätzlich maskiert, nur bewusst gekennzeichneter HTML-Text
wird unverändert eingesetzt.

Braucht die Weboberfläche PyTorch (Training, SOUP, Checkpoints), ruft sie über
`kern_bruecke.py` einen kurzen Python-Vorgang auf. Fehlt PyTorch, antwortet sie
mit HTTP 503 und einem deutschen Hinweis.

Nach jeder Änderung im Ordner `rust/`:

```bash
bash rust/bauen.sh
cd rust && cargo test
```

## Werkzeug ergänzen

```python
from mcp_protocol import MCPServer, ToolDefinition, ToolParameter

server = MCPServer()
server.register_tool(
    ToolDefinition(
        name="zeitzone",
        description="Nennt die Uhrzeit in einer Zeitzone.",
        parameters=[ToolParameter("zone", "string", "Name der Zeitzone")],
    ),
    lambda zone: {"zone": zone},
)
```

## Daten im Ordner `data/`

| Datei | Inhalt |
| --- | --- |
| `settings.json` | Erscheinungsbild, Fenstergröße, letzter Benutzer |
| `users.json` | Konten mit Passwort-Hash und Rolle |
| `gespraeche.json` | gespeicherte Chatverläufe |
| `metriken.json` | Trainings- und Auswertungsmetriken |
| `bewertungen.json` | Bewertungen einzelner Antworten |
| `schalter.json` | Stellung der vier Schalter der Weboberfläche |
| `werkzeug_training.jsonl` | Trainingsdaten für Werkzeugaufrufe |
| `checkpoints/` | gespeicherte Modelle |

## Bewusste Änderungen gegenüber der Python-Fassung

- Die Bewertungen der Weboberfläche liegen in `data/bewertungen.json` (früher
  eine SQLite-Datei). Damit nutzen Weboberfläche und Desktop-Oberfläche
  dieselbe Datei und dasselbe Format.
- Die Weboberfläche braucht kein Flask mehr; `requirements.txt` enthält nur
  noch Pakete für Modell, Training und Desktop-Oberfläche. Dafür ist `cargo`
  einmalig zum Bauen nötig.

## Lizenz

Privates Testprojekt ohne ausdrückliche Lizenz.
