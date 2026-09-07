# Warteschlange – Auftrags-Queue für LLM- und Tool-Aufträge (Shadow)

Die `AuftragsWarteschlange` reiht Chat-Anfragen und Werkzeugaufrufe in einer
FIFO-Reihenfolge ein und verarbeitet sie nacheinander in einem eigenen
Hintergrund-Thread. So bleiben Oberfläche und Antwort-Streaming flüssig,
während langlaufende Modellaufrufe serialisiert werden.

Das Modul lebt in `warteschlange.py` und ist thread-sicher — `einreihen`
kann aus jedem Thread (GUI, CLI, Schwarm) aufgerufen werden.

## Schnellstart

```python
from warteschlange import AuftragsWarteschlange

queue = AuftragsWarteschlange()
queue.starten()

# Auftrag einreihen (nicht-blockierend), Ergebnis später abholen
ergebnis = queue.einreihen(
    "chat",
    ausfuehren=lambda: llm.chat_with_tools(frage, client),
    fortschritt=lambda stueck: print(stueck, end="", flush=True),
)

wert = ergebnis.abholen()   # blockiert bis fertig
queue.stoppen()
```

## API

### `AuftragsWarteschlange`

| Methode / Eigenschaft | Beschreibung |
|----------------------|---------------|
| `AuftragsWarteschlange(max_groesse=0)` | Erzeugt die Queue. `max_groesse=0` = unbegrenzt. |
| `starten()` | Startet den Hintergrund-Worker (idempotent). |
| `stoppen(warten=False)` | Stoppt den Worker; laufende Aufträge werden abgebrochen. |
| `einreihen(art, ausfuehren, fortschritt=None)` → `AuftragErgebnis` | Reiht einen Auftrag ein. `art` ist ein frei wählbares Label (z. B. `"chat"`, `"tool"`). |
| `groesse` | Anzahl offener Aufträge in der Warteschlange. |
| `laeuft` | `True`, solange der Worker aktiv ist. |

### `AuftragErgebnis`

Wird von `einreihen` zurückgegeben. Blockiert nicht beim Einreihen.

| Methode / Eigenschaft | Beschreibung |
|----------------------|---------------|
| `warten(zeitspanne=None)` → `bool` | Blockiert bis fertig (oder Timeout). |
| `abholen()` → `Any` | Liefert das Ergebnis oder wirft bei Fehler. |
| `abbrechen()` | Bricht den Auftrag ab (sofern noch nicht fertig). |
| `status` | Einer der Statuswerte (siehe unten). |
| `fehler` | Fehlermeldung oder `None`. |

### Statuswerte

| Konstante | Bedeutung |
|-----------|-----------|
| `STATUS_OFFEN` | Auftrag wartet in der Warteschlange. |
| `STATUS_IN_BEARBEITUNG` | Worker führt den Auftrag aus. |
| `STATUS_FERTIG` | Auftrag erfolgreich abgeschlossen. |
| `STATUS_FEHLER` | Ausführung hat eine Exception geworfen. |
| `STATUS_ABGEBROCHEN` | Auftrag wurde vor der Ausführung abgebrochen. |

## Funktionsweise

- **FIFO-Reihenfolge:** Aufträge werden strikt in der Reihenfolge verarbeitet,
  in der sie eingereiht wurden — unabhängig von ihrer Dauer. Ein kurzer
  Auftrag, der nach einem langen eingereiht wird, wartet bis der lange fertig ist.
- **Hintergrund-Worker:** Ein Daemon-Thread (`_arbeite`) nimmt Aufträge aus der
  internen `queue.Queue` und führt sie nacheinander aus. `einreihen` kehrt sofort
  zurück.
- **Streaming:** Der `fortschritt`-Callback wird bei jedem Teilstück der
  Modell-Ausgabe aufgerufen (für Live-Streaming in CLI/GUI).
- **Abbruch:** `abbrechen()` setzt ein Event; Aufträge, die es respektieren,
  werden als `STATUS_ABGEBROCHEN` markiert und übersprungen.
- **Fehlerisolation:** Eine Exception in einem Auftrag stoppt weder den Worker
  noch andere Aufträge — der Fehler wird im `AuftragErgebnis` gespeichert und
  beim `abholen()` als `RuntimeError` geworfen.

## Integration in die App

Die Warteschlange ist in CLI und GUI integriert:

- **`cli.py`** — Chat-Aufrufe (`llm.chat_with_tools`) und Ziel-Modus-Durchläufe
  (`ziel_modus.arbeite_bis_ziel`) werden über die Warteschlange serialisiert.
  Der Tools-Only-Modus (ohne AI-Abhängigkeiten) läuft unverändert daneben.
  Die Queue wird beim Beenden gestoppt.
- **`gui.py`** — Der finale LLM-Aufruf sowie die Schwarm- (`schwarm.beantworte`)
  und Ziel-Modus-Durchläufe (`ziel_modus.arbeite_bis_ziel`) werden als ganze
  Aufträge durch die Warteschlange geroutet, sodass aufeinanderfolgende
  Chat-Anfragen geordnet verarbeitet werden. Schwarm und Ziel behalten intern
  ihre eigene Sperre (`_gesperrt`); die Queue serialisiert nur die
  Top-Level-Aufträge — kein Konflikt. Die Queue wird beim Schließen geordnet
  beendet.

## Beispiel: parallele Einreihung

```python
from warteschlange import AuftragsWarteschlange
import time

queue = AuftragsWarteschlange()
queue.starten()

reihenfolge = []

def aufgabe(name, dauer):
    def fn():
        time.sleep(dauer)
        reihenfolge.append(name)
        return name
    return fn

# C zuerst eingereiht (dauert 0.3s), dann A (0.1s), dann B (0.2s)
r1 = queue.einreihen("tool", aufgabe("C", 0.3))
r2 = queue.einreihen("tool", aufgabe("A", 0.1))
r3 = queue.einreihen("tool", aufgabe("B", 0.2))

print(r1.abholen(), r2.abholen(), r3.abholen())
# -> C A B   (FIFO, nicht nach Dauer sortiert)

queue.stoppen(warten=True)
```

## Abhängigkeiten

Keine externen Pakete. Das Modul nutzt ausschließlich die Python-Standardbibliothek
(`threading`, `queue`, `dataclasses`, `typing`). Es funktioniert daher auch im
AI-freien Modus der App.
