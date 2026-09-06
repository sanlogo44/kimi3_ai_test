# shadow-Integration – homogenes Programm

Shadow ist jetzt ein einziges homogenes Programm: Das shadow-Setup-Tooling ist nicht mehr ein separater Ordner, sondern als Python-Subpaket `shadow/` direkt in die App integriert. Ein einziger Aufruf richtet alles ein und startet die Anwendung.

## Starten

```bash
python start.py                 # Desktop-Oberfläche (GUI) – OHNE AI-Abhängigkeiten
python start.py --modus web     # Weboberfläche auf Port 5000
python start.py --modus cli     # Dialog im Terminal – OHNE AI-Abhängigkeiten
python start.py --mit-torch     # AI-Abhängigkeiten + PyTorch installieren (Chat aktivieren)
python start.py --modus shadow  # lokale shadow-Inferenz (nur mit --mit-torch)
python start.py --kein-venv     # ohne virtuelle Umgebung
```

## Zwei Betriebsmodi

Die App läuft standardmäßig **ohne AI-Abhängigkeiten** (kein PyTorch,
transformers oder Modell-Download). GUI, Web, CLI und alle Werkzeuge
starten; der Chat ist deaktiviert und zeigt einen Hinweis – analog zum
fehlenden Rust-Kern.

| Modus | Kommando | Chat | AI-Abhängigkeiten |
|-------|----------|------|-------------------|
| AI-frei (Standard) | `python start.py` | deaktiviert (Hinweis) | keine |
| Mit AI | `python start.py --mit-torch` | aktiv | PyTorch + transformers |

Im AI-freien CLI-Modus funktioniert der Rechner direkt:

```
Du: 2+3*4
2+3*4 = 14
Du: sqrt(16)
sqrt(16) = 4
```

`start.py` führt nacheinander aus:

1. **Python-Version prüfen** (≥ 3.10).
2. **Venv anlegen** (`venv/`).
3. **App-Abhängigkeiten** aus `requirements.txt` (customtkinter, matplotlib, pyyaml – **keine** AI-Bibliotheken).
4. **Rust-Kern bauen** (optional, wenn `cargo` vorhanden).
5. **Anwendung starten** im gewählten Modus.

Mit `--mit-torch` wird zusätzlich PyTorch backend-spezifisch installiert
und `requirements-ai.txt` (transformers, accelerate, datasets) gezogen.

## Drei LLM-Quellen

Das Sprachmodell kommt aus einer von drei Quellen (Priorität in dieser
Reihenfolge, wenn `model.source: auto` in `config.yaml`):

1. **Lokal trainiertes Modell** – wenn unter `model.local_path`
   (Standard `./tool_model`) ein trainiertes Modell liegt (Ordner mit
   `config.json` + `*.safetensors`/`*.bin`/`*.gguf`), wird dieses geladen.
   Kein Download, kein API-Schlüssel – das eigene LLM.
2. **OpenAI-kompatibler API-Server** – wenn `model.api_key` gesetzt ist
   (oder Env `LLM_API_KEY`), werden Anfragen an `model.api_base` geroutet
   (LM Studio, Ollama, vLLM, `platform.shadow.ai`). Funktioniert **ohne**
   PyTorch/transformers – nur `requests` (bereits in `requirements.txt`).
3. **Hugging-Face-Modell** – sonst wird `model.name` geladen. Achtung:
   `meta-llama/...` ist ein *gated* Repo und braucht einen `HF_TOKEN`.

Damit ist die App nicht mehr von einem gated Llama-Modell abhängig.
Eigentliches Ziel: eigenes trainiertes Modell (Quelle 1). Der API-Schlüssel
bleibt als optionaler Fallback für gehostete Server verfügbar.

```
# config.yaml
model:
  source: "auto"            # auto, local oder api
  local_path: "./tool_model"
  api_key: ""               # oder Env LLM_API_KEY
  api_base: "http://localhost:1234/v1"
  api_model: "local-model"
  name: "meta-llama/Meta-Llama-3-8B-Instruct"  # Fallback (gated)
```

Quelle 1 und 3 benötigen PyTorch + transformers (`--mit-torch`). Quelle 2
läuft auch im AI-freien Modus – nur `requests` wird gebraucht.

Bash-Nutzer können alternativ `./run_inference.sh` für die Inferenz aufrufen (dünnen Wrapper um `python -m shadow.inference`).

## Warteschlange (Auftrags-Queue)

LLM-/Tool-Aufträge werden über eine thread-sichere FIFO-Warteschlange serialisiert (`warteschlange.py`), damit sich überlappende Chat-Anfragen geordnet verarbeiten. Sie ist in CLI und GUI integriert und funktioniert auch ohne AI-Abhängigkeiten. Details siehe [README_WARTESCHLANGE.md](README_WARTESCHLANGE.md).

## Das `shadow/`-Subpaket

| Datei | Zweck |
|-------|-------|
| `backend.py` | Hardware-/Treibererkennung + PyTorch-Installation (reines Python, plattformübergreifend) |
| `diagnose.py` | GPU-Verfügbarkeitsdiagnose + Matmul-Smokertest (`python -m shadow.diagnose`) |
| `inference.py` | Lokale Inferenz (transformers) + OpenAI-kompatibler API-Client (`python -m shadow.inference`) |

## Treiberkompatibilität

Vor jeder PyTorch-Installation prüft `shadow.backend` den GPU-/NPU-/TPU-Treiber:

- **CUDA:** NVIDIA-Treiber wird gegen die Mindestversion je CUDA-Release geprüft (z. B. cu124 braucht Linux-Treiber ≥ 550.54.14 / Windows ≥ 551.61; cu128 ≥ 570.26 / 570.65), laut [NVIDIA CUDA Toolkit Release Notes](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html). Bei zu altem Treiber wird die Installation abgebrochen und ein Update empfohlen.
- **MPS (Apple Silicon):** macOS ≥ 13 mit Metal-Unterstützung wird vorausgesetzt; ohne Metal fällt Shadow auf die CPU zurück.
- **NPU (Intel):** OpenVINO-Runtime wird gesucht; der Treiber wird gegen die Mindestversion je OpenVINO-Release geprüft. Ohne passenden Treiber bleibt die NPU deaktiviert.
- **NPU (Huawei Ascend):** Der amdgpu-Kerneltreiber wird geprüft und die installierte CANN-Version mit dem angeforderten Wheel abgeglichen (±2-Release-Kompatibilität).
- **TPU (Google Cloud):** Die PJRT-Runtime wird gesucht; fehlt sie (z. B. lokal), bleibt die TPU deaktiviert und ein Hinweis nennt den Grund.

Mit `SKIP_DRIVER_CHECK=1` wird die Prüfung übersprungen (z. B. in Containern mit weitergereichtem Treiber). PyTorch wird nur mit `--mit-torch` installiert; ohne dieses Flag läuft die App ohne AI-Abhängigkeiten.

## Paralleles Training mehrerer Aufgaben

Shadow kann **mehrere Aufgaben gleichzeitig** trainieren – auf mehreren Geräten
(CUDA-Karte, NPU, TPU, MPS) oder in getrennten Streams auf demselben Gerät.
Gesteuert wird das über `hardware.parallel` in `config.yaml`:

```yaml
hardware:
  parallel:
    enabled: true     # paralleles Training aktivieren
    max_workers: 4    # gleichzeitige Aufträge (0 = automatisch nach Gerät Anzahl)
    strategy: balance # balance (Last verteilen) oder pin (Gerät fest zuweisen)
```

Jeder Trainingsauftrag läuft als eigener Auftrag durch die
`AuftragsWarteschlange`; bis zu `max_workers` davon gleichzeitig. Details zur
Warteschlange siehe [README_WARTESCHLANGE.md](README_WARTESCHLANGE.md).

## Umgebungsvariablen

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `CUDA_VERSION` | `cu124` | `cu121\|cu124\|cu126\|cu128` |
| `ROCM_VERSION` | `rocm6.2` | `rocm6.1\|rocm6.2` (nur Linux) |
| `SKIP_DRIVER_CHECK` | – | `1` = Treiberprüfung überspringen |
| `SHADOW_START_KEIN_RUST` | – | `1` = Rust-Bau überspringen |
| `MODEL_ID` | `moonshotai/shadow` | Modell für den `shadow`-Modus |
| `LLM_API_KEY` | – | API-Schlüssel für LLM-Quelle 2 (OpenAI-kompatibel) |
| `LLM_API_BASE` | `http://localhost:1234/v1` | Basis-URL des API-Servers |
| `PROMPT` / `MAX_NEW_TOKENS` | – | Prompt-Parameter für die Inferenz |

## Hinweis zur Modellgröße

Das zugrundeliegende Modell (shadow) ist ein 2.8T-Parameter-MoE-Modell (~1.56 TB MXFP4-Gewichte). Lokale Inferenz ist ein Multi-GPU-Cluster-Task. Die Skripte liefern den korrekten, plattformübergreifenden Stack und die richtigen Einstiegspunkte; für ernsthaftes lokales Serving vLLM auf einem CUDA-Cluster verwenden oder die gehostete API unter `platform.shadow.ai` aufrufen.
