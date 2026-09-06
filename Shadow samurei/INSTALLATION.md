# Installation – kimi3_ai_test (kurz)

## Der einfache Weg: ein Befehl

```bash
python start.py
```

Das Skript `start.py` übernimmt alles: virtuelle Umgebung anlegen,
Abhängigkeiten installieren, Rust-Kern bauen (falls Rust vorhanden) und
die Desktop-Oberfläche starten.

### Startmodi

```bash
python start.py                 # Desktop-Oberfläche (Standard)
python start.py --modus web     # Weboberfläche auf http://localhost:5000
python start.py --modus cli     # Dialog im Terminal
```

### Wichtige Optionen

| Option | Bedeutung |
| --- | --- |
| `--modus <gui\|web\|cli>` | Startmodus wählen (Standard: gui) |
| `--port <Zahl>` | Port für `web` (Standard: 5000) |
| `--host <Adresse>` | Adresse für `web` (Standard: 0.0.0.0) |
| `--kein-venv` | Ohne virtuelle Umgebung starten |
| `--kein-rust` | Rust-Bau überspringen |
| `--hilfe` | Hilfe anzeigen |

## Voraussetzungen

- **Python 3.10** oder neuer
- **Rust** (`cargo`) – optional, aber empfohlen: <https://rustup.rs>
- Erstanmeldung: Benutzer `Admin`, Passwort `1234` (muss beim ersten
  Start geändert werden)

Ohne Rust startet die Oberfläche trotzdem; Chat und Training bleiben dann
gesperrt und ein Hinweis nennt den Grund. Ohne Grafikkarte läuft das
Modell automatisch auf der CPU.

## Der Schwarm (mehrere Agenten)

In der Desktop-Oberfläche gibt es in der Kopfleiste den Schalter **Schwarm**.
Ist er aktiv, bearbeiten mehrere Agenten (Planer, Bearbeiter, Kritiker,
Zusammenfasser) jede Frage gemeinsam – zusätzlich können Unteragenten
gestartet werden. Die Einstellung wird gespeichert und beim nächsten Start
wiederhergestellt.

Hinweis zur Stabilität: die Agenten sind logisch getrennt, die
Modell-Inferenz läuft aber absichtlich nacheinander (nicht parallel), damit
Transformers und Grafikkarte nicht durcheinandergeraten.

## Der Ziel-Modus (autonom bis zum Ziel)

Der Schalter **Ziel** in der Kopfleiste aktiviert einen autonomen Modus:
jede Frage wird als *Ziel* behandelt, und das System arbeitet und testet so
lange, bis das Ziel erreicht ist oder das Versuchslimit greift (Standard: 5).

So funktioniert es:

1. Der **Schwarm** bearbeitet das Ziel und liefert ein Ergebnis.
2. Der **Tester** (ein eigener, pro Versuch frischer Agent) prüft objektiv,
   ob das Ziel wirklich erreicht ist. Er antwortet nur mit `ERREICHT` oder
   `NICHT_ERREICHT: <Grund>`.
3. Ist das Ziel nicht erreicht, wird das Feedback in den nächsten Versuch
eingespeist.
4. Optional laufen **echte Prüfungen** (z. B. `py_compile` für Python-Dateien),
   die Vorrang vor dem Tester haben.

Im Terminal startet der Ziel-Modus mit:

```bash
python main.py --modus ziel
```

Dann ein Ziel eingeben – der Schwarm arbeitet autonom, Status- und
Protokollmeldungen erscheinen live.

Wichtig: ohne konfigurierte echte Prüfungen ist das eine *Prüfung durch den
Tester-Agenten* (LLM-Selbsteinschätzung), keine echte Ausführung von Tests.
Für Code-Ziele können echte Prüfungen ergänzt werden (siehe
`python_datei_pruefung` in `ziel_modus.py`).

## Test

```bash
python test_schwarm.py
python test_ziel_modus.py
python test_ziel_modus_echt.py
```

`test_schwarm.py` und `test_ziel_modus.py` pruefen den Schwarm- bzw.
Ziel-Ablauf mit einem Fake-LLM (ohne echtes Modell und ohne gebauten
Rust-Kern). `test_ziel_modus_echt.py` fuehrt zusaetzlich **echte**
Pruefungen aus: reale Python-Dateien werden mit `py_compile` kompiliert,
und erzeugter Code wird in einem Unterprozess wirklich ausgefuehrt und die
Ausgabe mit dem erwarteten Wert verglichen.

## Manuelle Schritte (falls gewünscht)

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
bash rust/bauen.sh                 # Rust-Kern bauen
python main.py
```

Laufzeitdaten liegen im Ordner `data/` und können gelöscht werden; sie werden
beim nächsten Start neu angelegt.
