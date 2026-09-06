#!/usr/bin/env python3
"""Kommandozeilen-Oberfläche für kimi3_ai_test.

Startet einen einfachen Dialog im Terminal. Die Antworten werden im Datenstrom
ausgegeben, sobald das Modell Teilstücke liefert.
"""
from __future__ import annotations

import sys
import threading

from config_loader import load_config
from logger import get_logger
from mcp_protocol import MCPClient
from tools import create_math_tools

BEFEHLE = {
    "/ende": "Beendet das Programm",
    "/leeren": "Löscht den Gesprächsverlauf",
    "/werkzeuge": "Zeigt alle verfügbaren Werkzeuge",
    "/hilfe": "Zeigt diese Übersicht",
}


def zeige_hilfe() -> None:
    """Gibt die verfügbaren Befehle aus."""
    print("\nBefehle:")
    for befehl, beschreibung in BEFEHLE.items():
        print(f"  {befehl:<12} {beschreibung}")
    print()


def run_cli() -> int:
    """Startet den interaktiven Dialog und gibt den Rückgabewert zurück."""
    konfiguration = load_config()
    protokoll = get_logger(konfiguration)
    protokoll.info("Starte Kommandozeilen-Modus ...")

    server = create_math_tools()
    client = MCPClient(server)

    try:
        from llm_engine import ToolAugmentedLLM

        llm = ToolAugmentedLLM(config=konfiguration)
        llm.load_model()
    except Exception as fehler:
        print(f"Das Sprachmodell konnte nicht geladen werden: {fehler}")
        print("Bitte „pip install -r requirements.txt“ ausführen (siehe INSTALL.md).")
        return 1

    verlauf: list[dict[str, str]] = []

    print("\nKimi3 – Assistent mit Werkzeugzugriff")
    print(f"Modell: {getattr(llm, 'model_name', 'unbekannt')}")
    zeige_hilfe()

    while True:
        try:
            eingabe = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAuf Wiedersehen.")
            break

        if not eingabe:
            continue
        if eingabe in ("/ende", "/quit", "/exit"):
            print("Auf Wiedersehen.")
            break
        if eingabe in ("/leeren", "/clear"):
            verlauf = []
            print("Gesprächsverlauf gelöscht.\n")
            continue
        if eingabe in ("/werkzeuge", "/tools"):
            for schema in server.get_tool_schemas():
                funktion = schema["function"]
                print(f"  - {funktion['name']}: {funktion['description']}")
            print()
            continue
        if eingabe in ("/hilfe", "/help"):
            zeige_hilfe()
            continue

        print("\nAssistent: ", end="", flush=True)
        try:
            ergebnis = llm.chat_with_tools(
                eingabe,
                client,
                conversation_history=verlauf,
                teilstueck_rueckmeldung=lambda stueck: print(stueck, end="", flush=True),
            )
        except Exception as fehler:
            protokoll.error(f"Fehler bei der Anfrage: {fehler}")
            print(f"\nFehler: {fehler}\n")
            continue

        antwort = ergebnis.get("response", "")
        print("" if antwort.endswith("\n") else "\n", end="")
        if not antwort:
            print("(keine Antwort erhalten)")

        aufrufe = ergebnis.get("tool_calls", [])
        if aufrufe:
            namen = [getattr(aufruf, "tool_name", str(aufruf)) for aufruf in aufrufe]
            print(f"Verwendete Werkzeuge: {', '.join(namen)}")
        print()

        verlauf = ergebnis.get("conversation", verlauf)
        if len(verlauf) > 20:
            verlauf = verlauf[-20:]

    return 0


def run_ziel() -> int:
    """Startet den autonomen Ziel-Modus im Terminal.

    Der Nutzer gibt ein Ziel ein. Anschließend arbeitet der Schwarm so lange,
    bis das Ziel erreicht ist oder das Versuchslimit greift. Statusmeldungen
    und Teilergebnisse werden live ausgegeben.
    """
    konfiguration = load_config()
    protokoll = get_logger(konfiguration)
    protokoll.info("Starte Ziel-Modus ...")

    server = create_math_tools()

    try:
        from llm_engine import ToolAugmentedLLM

        llm = ToolAugmentedLLM(config=konfiguration)
        llm.load_model()
    except Exception as fehler:
        print(f"Das Sprachmodell konnte nicht geladen werden: {fehler}")
        print("Bitte „pip install -r requirements.txt“ ausführen (siehe INSTALL.md).")
        return 1

    from ziel_modus import ZielModus

    ziel_modus = ZielModus(
        llm=llm,
        server=server,
        max_versuche=5,
        pruefungen=None,  # nur Tester-Agent; echte Prüfungen bei Bedarf ergänzen
    )

    print("\nKimi3 – Ziel-Modus (autonom bis zum Ziel)")
    print(f"Modell: {getattr(llm, 'model_name', 'unbekannt')}")
    print("Leere Eingabe oder Strg+C zum Beenden.\n")

    while True:
        try:
            ziel = input("Ziel: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAuf Wiedersehen.")
            break

        if not ziel:
            break

        abbruch = threading.Event()

        def status(meldung: str) -> None:
            print(f"  [{meldung}]", flush=True)

        def teilstueck(stueck: str) -> None:
            print(stueck, end="", flush=True)

        print("\nArbeite am Ziel ...\n", flush=True)
        try:
            ergebnis = ziel_modus.arbeite_bis_ziel(
                ziel,
                teilstueck_rueckmeldung=teilstueck,
                abbruch=abbruch,
                status_rueckmeldung=status,
            )
        except KeyboardInterrupt:
            abbruch.set()
            print("\nAbgebrochen.")
            continue
        except Exception as fehler:
            protokoll.error(f"Fehler im Ziel-Modus: {fehler}")
            print(f"\nFehler: {fehler}\n")
            continue

        print()  # Teilstück-Zeile abschließen
        versuche = ergebnis.get("versuche", 0)
        erreicht = ergebnis.get("ziel_erreicht", False)
        print(f"Versuche: {versuche}")
        print(f"Ziel erreicht: {'ja' if erreicht else 'nein (nicht sicher)'}")

        protokoll_liste = ergebnis.get("protokoll", [])
        if protokoll_liste:
            print("Protokoll:")
            for eintrag in protokoll_liste:
                urteil = eintrag.get("urteil", "")
                marker = "✓" if eintrag.get("erfuellt") else "✗"
                if not urteil and eintrag.get("erfuellt"):
                    urteil = "erreicht"
                print(f"  {marker} Versuch {eintrag.get('versuch')}: {urteil}")
        aufrufe = ergebnis.get("tool_calls", [])
        if aufrufe:
            namen = [getattr(a, "tool_name", str(a)) for a in aufrufe]
            print(f"Verwendete Werkzeuge: {', '.join(namen)}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
