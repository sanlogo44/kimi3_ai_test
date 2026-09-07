# Shadow

Ein Projekt in Python für einen Sprachassistenten mit Werkzeugzugriff. Es
enthält eine Desktop-Oberfläche im Stil von Claude, eine Weboberfläche zur
Verwaltung, ein Entwickler-Dashboard mit Diagrammen und einen Werkzeug-Server
nach dem MCP-Muster. Alle Texte, Kommentare und Oberflächen sind deutsch.
Neu dazu kommen ein **LLM-Trainer** für LoRA-Fine-Tuning und ein
**selbstständig navigierender Webscraper**, der Trainingsdaten sammelt.

## Aufteilung

Python bleibt dort, wo PyTorch nötig ist (Modell, Training, Chat) und für die
CustomTkinter-Oberflächen. Der gemeinsame Kern und die komplette Weboberfläche
liegen ebenfalls in Python (Ordner `kern/` und `web/`). Es gibt keinen
Rust-Anteil mehr.

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
  Websuche, Uhrzeit und Webscraper; leicht erweiterbar.
- **Training** – Schicht-Training, LoRA-Fine-Tuning (`trainer.py`), SOUP
  (Mittelung mehrerer Modelle), Checkpoint-Verwaltung und
  Metrikaufzeichnung.
- **Webscraper (`webscraper.py`)** – crawlt eine Website automatisch, folgt
  Links derselben Domain und speichert die Inhalte als Trainingsdaten (JSONL)
  ab; direkt als Eingabe für `trainer.py` verwendbar.

## Projektstruktur

```
Shadow/
├── kern/                     # Python-Kern (Konfiguration, Protokoll, Einstellungen,
│   ├── __init__.py           #   Re-Export aller Module
│   ├── zeit.py               #   Zeitfunktionen
│   ├── pfade.py               #   Pfadfunktionen
│   ├── protokoll.py          #   Protokollierung
│   ├── konfiguration.py      #   Konfiguration laden
│   ├── einstellungen.py      #   Einstellungen (JSON-Speicher)
│   ├── schalter.py            #   Schalter der Weboberfläche
│   ├── metriken.py            #   MetrikSpeicher
│   ├── bewertungen.py        #   BewertungsSpeicher
│   ├── passwort.py            #   Passwort-Hashing (werkzeug-kompatibel)
│   ├── konten.py              #   Kontenverwaltung
│   ├── checkpoints.py         #   Checkpoint-Verwaltung
│   └── rechner.py             #   Mathematischer Ausdrucksparser
├── web/                      # Weboberfläche (Flask)
│   ├── __init__.py
│   ├── app.py                #   Flask-App mit allen Routen
│   ├── sitzung.py             #   Sitzung über signiertes Cookie
│   ├── zustand.py             #   Gemeinsamer Zustand
│   ├── vorlagen.py            #   HTML-Vorlagen als Python-Funktionen
│   └── bruecke.py             #   Brücke zu kern_bruecke.py
├── auth/                     # Anmeldung und Benutzerverwaltung
│   └── auth_manager.py       #   CustomTkinter-Oberfläche über dem Kern
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
├── shadow_kern.py             # Re-Export-Modul (leitet an kern weiter)
├── kern_modul.py             # lädt das Kern-Paket und erklärt fehlende Importe
├── kern_bruecke.py           # Brücke: Webserver ruft damit PyTorch-Aufgaben auf
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
├── train_tool_use.py         # Trainingsdaten für Werkzeugaufrufe
├── trainer.py                # LLM-Trainer (LoRA-Fine-Tuning)
└── webscraper.py             # automatisch navigierender Webscraper
```

## Schnellstart

```
git clone https://github.com/sanlogo44/Shadow.git
cd Shadow

python -m venv venv
source venv/bin/activate        # macOS und Linux: source venv/bin/activate
                                # Windows:        venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium     # nur für den Webscraper nötig
```

Es ist kein Rust-Bau mehr nötig – der gesamte Kern und die Weboberfläche
liegen in Python.

Starten:

```
python main.py                  # Desktop-Oberfläche
python main.py --modus web      # Weboberfläche auf http://localhost:5000
python main.py --modus cli      # Dialog im Terminal
```

Der Modus `web` startet den Python-Webserver (Flask); er lässt sich auch
direkt aufrufen:

```
python -m web.app --host 127.0.0.1 --port 5000
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

```
model:
  name: "meta-llama/Meta-Llama-3-8B-Instruct"
  max_tool_iterations: 5

hardware:
  device: "auto"        # auto, cuda, mps, npu, tpu, xpu oder cpu
  use_4bit: true        # benötigt bitsandbytes und eine NVIDIA-Grafikkarte
  weights_dtype: "fp32"
  npu:
    enabled: true       # NPU-Unterstützung (Intel NPU, Huawei Ascend, ...)
    backend: "auto"     # auto, openvino oder ascend
  tpu:
    enabled: true       # TPU-Unterstützung (Google Cloud TPU)
    backend: "auto"     # auto, pjrt oder xla
  parallel:
    enabled: true       # paralleles Training mehrerer Aufgaben gleichzeitig
    max_workers: 4      # Anzahl gleichzeitiger Trainingsaufträge (0 = automatisch)
    strategy: "balance" # balance (Last verteilen) oder pin (Gerät fest zuweisen)
```

### Geräte im Überblick

| Gerät               | Wert  | Beschreibung                            |
| ------------------- | ----- | --------------------------------------- |
| NVIDIA-Grafikkarte  | `cuda`| CUDA; 4-Bit-Quantisierung möglich       |
| Apple Silicon       | `mps` | Metal Performance Shaders (macOS)       |
| NPU                 | `npu` | Intel NPU (OpenVINO), Huawei Ascend u. a. |
| TPU                 | `tpu` | Google Cloud TPU (PJRT/XLA)             |
| Intel/AMD-Grafik    | `xpu` | Intel oneAPI / AMD ROCm-Pfad            |
| CPU                 | `cpu` | Langsamster Pfad, immer verfügbar       |

Mit `device: "auto"` wählt Shadow das erste verfügbare Gerät in der Reihenfolge
CUDA, MPS, NPU, TPU, XPU, CPU. Jedes Training und jeder Inferenz-Aufruf prüft
dabei erneut die Geräte – so lassen sich im selben Lauf NVIDIA-Karte, Apple NPU
und Cloud-TPU gleichzeitig nutzen.

## Training auf NPU und TPU

Shadow nutzt neben CPU, CUDA und MPS auch **NPUs** und **TPUs** für Training und
Inferenz, sofern die passende Vendor-Runtime installiert ist. Die Erkennung
läuft über `shadow.backend`:

- **NPU (Huawei Ascend):** nur mit installiertem `torch_npu` (CANN). Ohne
  passenden Treiber fällt das Training auf das nächste Gerät zurück.
- **TPU (Google Cloud):** nur mit installiertem `torch_xla`. Der
  Optimierungsschritt läuft dann über `xm.optimizer_step`/`xm.mark_step`.
- **XPU (Intel oneAPI):** nur mit `intel_extension_for_pytorch`.
- **Intel OpenVINO:** wird nur zur Inferenz erkannt, nicht als Trainings-Gerät
  über `torch.Tensor.to("npu")`. OpenVINO-Training ist nicht implementiert.

NPU/TPU werden nur mit `--mit-torch` aktiviert; ohne dieses Flag läuft die App
ohne AI-Abhängigkeiten. Mit `SKIP_DRIVER_CHECK=1` wird die Treiberprüfung
übersprungen (z. B. in Containern mit weitergereichtem Treiber).

## LLM-Training mit trainer.py (LoRA-Fine-Tuning)

`trainer.py` feinjustiert das in `config.yaml` eingestellte Basismodell mit
LoRA-Adaptern (nur ein Bruchteil der Parameter ist trainierbar, dadurch läuft
das Training auch auf kleinerer Hardware). Trainingsdaten werden als JSONL mit
den Feldern `anweisung` und `antwort` erwartet – genau das Format, das
`webscraper.py` erzeugt.

Vorbereitung (einmalig):

```
pip install transformers peft datasets accelerate
pip install bitsandbytes        # nur mit NVIDIA-Grafikkarte
playwright install chromium     # nur für den Webscraper
```

Trainingsdaten sammeln (optional, alternativ eigene `trainingsdaten.jsonl`):

```
python webscraper.py https://beispiel.de 50
# erzeugt data/gescraped.jsonl
```

Training starten:

```
python trainer.py --daten data/trainingsdaten.jsonl
python trainer.py --daten data/gescraped.jsonl --epochen 5 --lernrate 1e-4 \
                  --batch 2 --ausgabe data/checkpoints/mein_modell
```

Parameter:

| Parameter   | Bedeutung                                      | Standard |
| ----------- | ---------------------------------------------- | -------- |
| `--daten`   | Pfad zur JSONL-Datei (Pflicht)                 | –        |
| `--epochen` | Anzahl der Trainingsdurchläufe                 | `3`      |
| `--lernrate`| Lernrate für den LoRA-Adapter                  | `2e-4`   |
| `--batch`   | Batchgröße pro Schritt                         | `4`      |
| `--ausgabe` | Ordner für den fertigen Adapter                | `data/checkpoints/letztes_training` |

Nach dem Training liegen der Adapter und der Tokenizer im Ausgabeordner;
Metriken (Dauer, Beispielzahl) werden automatisch in `data/metriken.json`
eingetragen und erscheinen im Entwickler-Dashboard.

## Webscraper (webscraper.py)

Der Scraper bewegt sich automatisch durch eine Website: Er startet auf einer
URL, folgt allen Links derselben Domain (Anker und Dateien wie PDFs/Bilder
werden herausgefiltert) bis zur gewünschten Seitenzahl und speichert aus jedem
Inhalt ein Trainingsbeispiel. Er nutzt Playwright (headless Chromium), führt
also JavaScript aus wie ein echter Browser.

```
python webscraper.py https://beispiel.de 25        # 25 Seiten crawlen
```

Das Ergebnis wird als JSONL an `data/gescraped.jsonl` angehängt und kann
direkt mit `trainer.py` weiterverwendet werden. Der Scraper lässt sich auch
als MCP-Werkzeug registrieren:

```
from mcp_protocol import MCPServer, ToolDefinition, ToolParameter
from webscraper import crawl

server.register_tool(
    ToolDefinition(
        name="webscraper",
        description="Crawlt eine Website automatisch und sammelt Text.",
        parameters=[
            ToolParameter("start_url", "string", "Einstiegs-URL"),
            ToolParameter("max_seiten", "integer", "Höchstzahl Seiten"),
        ],
    ),
    lambda start_url, max_seiten=25: crawl(start_url, max_seiten),
)
```

Hinweis: Beim Scraping robots.txt und Nutzungsbedingungen der Zielseiten
beachten.

## Training auf NPU und TPU

Shadow nutzt neben CPU, CUDA und MPS auch **NPUs** und **TPUs** für Training und
Inferenz, sofern die passende Vendor-Runtime installiert ist. (Details siehe
Abschnitt oben; `trainer.py` erbt die Gerätewahl aus `config.yaml`.)

## Paralleles Training mehrerer Aufgaben

Mit `hardware.parallel.enabled: true` trainiert Shadow **mehrere Aufgaben**
**gleichzeitig** – nicht nur nacheinander. Jeder Trainingsauftrag (Schicht-
Training, LoRA-Fine-Tuning, SOUP, Checkpoint, Benchmark) wird als eigener
Auftrag an die `AuftragsWarteschlange` übergeben und auf dem nächsten freien
Gerät ausgeführt.

So funktioniert es:

1. Die Warteschlange nimmt beliebig viele Aufträge entgegen (`einreihen` kehrt
   sofort zurück).
2. Bis zu `max_workers` Aufträge laufen gleichzeitig, jeweils auf einem anderen
   Gerät (CUDA-Karte 0, NPU, TPU, …) oder – bei nur einem Gerät – in
   getrennten Streams auf derselben Karte.
3. `strategy: "balance"` verteilt neue Aufträge auf das Gerät mit der geringsten
   Auslastung; `strategy: "pin"` weist jedem Auftrag ein festes Gerät zu.
4. Ergebnisse und Metriken landen pro Auftrag getrennt in `data/metriken.json`.

Im Terminal startet das parallele Training mit:

```
python main.py --modus train --parallel 4    # 4 Aufträge gleichzeitig
python main.py --modus train --geraet npu     # nur auf der NPU trainieren
python main.py --modus train --geraet tpu     # nur auf der TPU trainieren
```

Hinweis zur Stabilität: Transformere und PyTorch-Inferenz laufen innerhalb
eines einzelnen Auftrags weiterhin nacheinander (damit sich Streams nicht
überlappen). Die Parallelität gilt zwischen verschiedenen Aufträgen, nicht
innerhalb eines Modellschritts.

## Aufbau des Kerns

Der Ordner `kern/` ist ein Python-Paket mit den folgenden Modulen:

| Modul                 | Inhalt                                          |
| --------------------- | ----------------------------------------------- |
| `kern.konfiguration`  | Konfiguration (`config.yaml`), Standardwerte    |
| `kern.protokoll`      | Farbige Protokollausgabe, optionale Protokolldatei |
| `kern.einstellungen`  | Einstellungen (`data/settings.json`)            |
| `kern.schalter`       | Schalter der Weboberfläche (`data/schalter.json`) |
| `kern.metriken`       | MetrikSpeicher (`data/metriken.json`)           |
| `kern.bewertungen`    | BewertungsSpeicher (`data/bewertungen.json`)    |
| `kern.passwort`       | Passwort-Hash (werkzeug-kompatibel: scrypt/pbkdf2) |
| `kern.konten`         | Kontenverwaltung (`data/users.json`)            |
| `kern.checkpoints`    | Checkpoint-Ordner (`data/checkpoints/`)         |
| `kern.rechner`        | Sicherer mathematischer Ausdrucksparser (kein `eval`) |
| `kern.pfade`          | Projektordner, Datenordner, Datendateien        |
| `kern.zeit`           | Zeitstempel und Formatierung                    |

Die Python-Module `config_loader.py`, `logger.py`, `settings_store.py`,
`tools.py` (Rechner), `dev_tools/metrics_tracker.py`, `dev_tools/feedback_mode.py`
und `auth/auth_manager.py` sind dünne Hüllen über diesem Kern: gleiche
Schnittstelle, gleiche Dateiformate, gleiche deutsche Meldungen – die Logik
selbst steht nur einmal, nämlich im Python-Kern. `trainer.py` und
`webscraper.py` schließen direkt an diese Hüllen an (`config_loader`, `logger`,
`analytics`).

Die Seitenvorlagen der Weboberfläche liegen als Python-Funktionen in
`web/vorlagen.py` (`anmeldeseite`, `zugangsdatenseite`, `trainingsseite`,
`verwaltungsseite`). Es gibt keine Vorlagensprache und keine `.html`-Dateien;
Werte werden grundsätzlich maskiert, nur bewusst gekennzeichneter HTML-Text
wird unverändert eingesetzt.

Braucht die Weboberfläche PyTorch (Training, SOUP, Checkpoints), ruft sie über
`kern_bruecke.py` einen kurzen Python-Vorgang auf. Fehlt PyTorch, antwortet sie
mit HTTP 503 und einem deutschen Hinweis.

Nach jeder Änderung im Ordner `kern/` oder `web/` genügt ein Neustart –
es ist kein Kompilierschritt mehr nötig.

## Werkzeug ergänzen

```
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

| Datei                   | Inhalt                              |
| ----------------------- | ----------------------------------- |
| `settings.json`         | Erscheinungsbild, Fenstergröße, letzter Benutzer |
| `users.json`            | Konten mit Passwort-Hash und Rolle  |
| `gespraeche.json`       | gespeicherte Chatverläufe           |
| `metriken.json`         | Trainings- und Auswertungsmetriken  |
| `bewertungen.json`      | Bewertungen einzelner Antworten     |
| `schalter.json`         | Stellung der vier Schalter der Weboberfläche |
| `werkzeug_training.jsonl` | Trainingsdaten für Werkzeugaufrufe  |
| `gescraped.jsonl`       | vom Webscraper gesammelte Trainingsdaten |
| `trainingsdaten.jsonl`  | eigene Trainingsdaten (anweisung/antwort) |
| `checkpoints/`          | gespeicherte Modelle und LoRA-Adapter |

## Lizenz

Privates Testprojekt ohne ausdrückliche Lizenz.
