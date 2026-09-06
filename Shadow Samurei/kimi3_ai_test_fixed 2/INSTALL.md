# Installationsanleitung

## Systemvoraussetzungen

- **Python**: 3.10 oder neuer
- **Rust**: 1.75 oder neuer (`cargo`), siehe https://rustup.rs
- **Betriebssystem**: Windows 10/11, macOS 12 oder neuer, Linux (Ubuntu 22.04+)
- **Arbeitsspeicher**: mindestens 8 GB, empfohlen 16 GB
- **Grafikkarte**: optional; für 4-Bit-Modelle eine NVIDIA-Karte mit CUDA 11.8+
- **Festplatte**: etwa 10 GB für das Basismodell

Für die Desktop-Oberfläche genügen Python, `customtkinter`, `matplotlib`,
`pyyaml` und `pillow`. PyTorch und Transformers werden nur für Chat und
Training benötigt und erst bei Bedarf geladen.

Alles außer dem Modellkern ist in Rust geschrieben (Ordner `rust/`): der
gemeinsame Kern für Konfiguration, Protokoll, Einstellungen, Schalter,
Metriken, Bewertungen, Konten, Checkpoints und Rechner sowie die vollständige
Weboberfläche. Python greift über das gebaute Modul `kimi3_kern` darauf zu,
deshalb ist `cargo` eine Voraussetzung.

## Schritt 1: Umgebung einrichten

```bash
python --version

python -m venv venv

# Linux und macOS
source venv/bin/activate
# Windows
venv\Scripts\activate
```

## Schritt 2: Abhängigkeiten installieren

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Nur die Oberflächen ohne Modell:

```bash
pip install customtkinter matplotlib pyyaml pillow
```

## Schritt 2b: Rust-Teil bauen (Pflicht)

```bash
bash rust/bauen.sh
```

Das Skript baut den Arbeitsbereich in `rust/` mit `cargo build --release`,
legt das Python-Modul als `kimi3_kern.so` in den Projektordner und erzeugt das
Programm der Weboberfläche unter `rust/target/release/kimi3-web`. Ohne diesen
Schritt melden die Python-Module beim Start: „Der Rust-Kern „kimi3_kern“ wurde
nicht gefunden. Bitte einmal bauen: bash rust/bauen.sh“.

Hinweis zu `bitsandbytes` (4-Bit-Quantisierung): Das Paket ist in
`requirements.txt` bewusst abgeschaltet, weil es nur mit NVIDIA-Grafikkarten
sinnvoll ist. Bei Bedarf die Zeile in `requirements.txt` einkommentieren.

## Schritt 3: Modellzugang (optional)

Für Modelle mit Zugangsbeschränkung bei Hugging Face:

```bash
pip install huggingface-hub
huggingface-cli login
```

## Schritt 4: Konfiguration anpassen

In `config.yaml`:

```yaml
model:
  name: "meta-llama/Meta-Llama-3-8B-Instruct"   # oder ein kleineres Modell
  max_tool_iterations: 5

hardware:
  device: "auto"      # auto, cuda oder cpu
  use_4bit: true      # bei wenig Grafikspeicher sinnvoll
  weights_dtype: "fp32"
```

## Schritt 5: Anwendung starten

```bash
python main.py                  # Desktop-Oberfläche (Standard)
python main.py --modus web      # Weboberfläche, http://localhost:5000
python main.py --modus cli      # Dialog im Terminal
```

Einzelne Bausteine lassen sich zum Testen direkt starten:

```bash
python -m ui.chat_interface           # Chat mit Beispielantworten
python -m dev_tools.dev_dashboard     # Entwickler-Dashboard
python -m auth.auth_manager           # Anmeldung und Benutzerverwaltung
python train_tool_use.py --trockenlauf --beispiele 40
```

## Schritt 6: Erste Anmeldung

- Benutzername: `Admin`
- Passwort: `1234`

Das Passwort muss beim ersten Anmelden geändert werden. Die Konten liegen als
Hash in `data/users.json`; diese Datei sollte nicht in die Versionsverwaltung
gelangen (siehe `.gitignore`).

## Fehlerbehebung

**`ModuleNotFoundError: No module named 'yaml'`**

```bash
pip install pyyaml
```

**`PyTorch ist nicht verfügbar` / `PyTorch und Transformers sind nicht installiert`**

Die Oberfläche läuft, aber Chat und Training sind gesperrt. Lösung:

```bash
pip install torch transformers accelerate
```

**`Der Rust-Kern „kimi3_kern“ wurde nicht gefunden`**

```bash
bash rust/bauen.sh
```

Fehlt dabei `cargo`, zuerst Rust einrichten (https://rustup.rs) und eine neue
Terminal-Sitzung öffnen.

**`Das Programm der Weboberfläche „kimi3-web“ wurde nicht gefunden`**

`python main.py --modus web` startet `rust/target/release/kimi3-web`. Nach
`bash rust/bauen.sh` ist es vorhanden; ein anderer Ort lässt sich über die
Umgebungsvariable `KIMI3_WEB_BINAER` angeben.

**Keine Diagramme im Dashboard**

```bash
pip install matplotlib
```

Ohne matplotlib zeigt das Dashboard an dieser Stelle einen Hinweis; alle
übrigen Reiter bleiben nutzbar.

**`CUDA out of memory`**

- `use_4bit: true` in `config.yaml` setzen
- `max_length` im Abschnitt `training` verkleinern
- oder `device: "cpu"` verwenden (langsamer)

**Oberfläche startet nicht unter Linux**

Tkinter muss vorhanden sein:

```bash
sudo apt install python3-tk
```

**Fehlende Schriftzeichen in der Oberfläche**

Die Oberfläche verwendet bewusst nur Text und keine Symbolzeichen, damit sie
auch mit sehr sparsam bestückten Schriftarten korrekt aussieht.

## Deinstallation

```bash
deactivate

rm -rf venv          # Linux und macOS
rmdir /s /q venv     # Windows
```

Laufzeitdaten liegen ausschließlich im Ordner `data/` und können gelöscht
werden; sie werden beim nächsten Start neu angelegt.
