#!/usr/bin/env python3
"""Haupteinstiegspunkt für kimi3_ai_test.

Beispiele:
    python main.py                  Desktop-Oberfläche
    python main.py --modus web      Weboberfläche auf Port 5000
    python main.py --modus cli      Dialog im Terminal

Die Weboberfläche ist ein eigenständiges Rust-Programm (``kimi3-web``);
``--modus web`` startet es und gibt dessen Ausgabe unverändert weiter.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from argumente import _DeutscheHilfe, deutscher_zerleger

#: Name des Rust-Programms der Weboberfläche
WEB_PROGRAMM = "kimi3-web"
#: Umgebungsvariable, mit der sich ein eigener Pfad vorgeben lässt
WEB_BINAER_VARIABLE = "KIMI3_WEB_BINAER"
#: Hinweis, wie das Programm gebaut wird
WEB_BAUHINWEIS = (
    f"Das Programm der Weboberfläche „{WEB_PROGRAMM}“ wurde nicht gefunden.\n"
    "Bitte einmal bauen:\n"
    "    bash rust/bauen.sh\n"
    f"Alternativ den Pfad in der Umgebungsvariablen „{WEB_BINAER_VARIABLE}“ angeben."
)


def finde_web_binaer() -> str | None:
    """Sucht das Rust-Programm der Weboberfläche.

    Gesucht wird in dieser Reihenfolge: Umgebungsvariable
    ``KIMI3_WEB_BINAER``, ``rust/target/release``, ``rust/target/debug``
    und zuletzt der Suchpfad des Systems (``PATH``).
    """
    aus_umgebung = os.environ.get(WEB_BINAER_VARIABLE, "").strip()
    if aus_umgebung:
        return aus_umgebung if os.path.isfile(aus_umgebung) else None

    projektordner = os.path.dirname(os.path.abspath(__file__))
    for bauart in ("release", "debug"):
        pfad = os.path.join(projektordner, "rust", "target", bauart, WEB_PROGRAMM)
        if os.path.isfile(pfad):
            return pfad
    return shutil.which(WEB_PROGRAMM)


def starte_weboberflaeche(host: str, port: int) -> int:
    """Startet das Rust-Programm der Weboberfläche und gibt dessen Rückgabewert zurück."""
    binaer = finde_web_binaer()
    if not binaer:
        print(WEB_BAUHINWEIS, file=sys.stderr)
        return 1

    befehl = [binaer, "--host", str(host), "--port", str(port)]
    try:
        # Ausgabe und Rückgabewert werden unverändert durchgeleitet.
        return subprocess.run(befehl).returncode
    except KeyboardInterrupt:  # Strg+C beendet den Server geordnet
        print("\nWeboberfläche beendet.")
        return 0
    except OSError as fehler:
        print(
            f"Das Programm „{binaer}“ konnte nicht gestartet werden: {fehler}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    """Liest die Argumente und startet den gewählten Modus."""
    zerleger = deutscher_zerleger(
        description="kimi3_ai_test – Assistent mit Werkzeugzugriff",
        formatter_class=_DeutscheHilfe,
    )
    zerleger.add_argument(
        "--modus", "--mode",
        dest="modus",
        choices=["gui", "web", "cli", "ziel", "train"],
        default="gui",
        help="Startmodus: gui (Desktop), web (Browser), cli (Terminal), "
             "ziel (autonomer Ziel-Modus), train (paralleles Training)",
    )
    zerleger.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port für den Modus „web“ (Standard: 5000)",
    )
    zerleger.add_argument(
        "--host",
        default="0.0.0.0",
        help="Adresse für den Modus „web“ (Standard: 0.0.0.0)",
    )
    zerleger.add_argument(
        "--parallel",
        type=int,
        default=0,
        help="Anzahl gleichzeitiger Trainingsaufträge im Modus „train“ "
             "(0 = automatisch nach Gerätezahl)",
    )
    zerleger.add_argument(
        "--geraet",
        dest="geraet",
        default=None,
        help="Trainingsgerät im Modus „train“: cuda, mps, xpu, npu, tpu, cpu "
             "oder auto (Standard)",
    )
    zerleger.add_argument(
        "--epochs",
        type=int,
        default=5,
        help="Epochen je Trainingsauftrag im Modus „train“ (Standard: 5)",
    )
    argumente = zerleger.parse_args()

    if argumente.modus == "gui":
        # Die Oberfläche wird erst hier geladen, damit die Modi „web“ und
        # „cli“ ohne Tkinter starten können.
        from gui import run_gui

        run_gui()
        return 0

    if argumente.modus == "web":
        return starte_weboberflaeche(host=argumente.host, port=argumente.port)

    if argumente.modus == "ziel":
        from cli import run_ziel
        return run_ziel()

    if argumente.modus == "train":
        from train_cli import run_train
        return run_train(
            parallel=argumente.parallel,
            geraet=argumente.geraet,
            epochs=argumente.epochs,
        )

    from cli import run_cli

    return run_cli()


if __name__ == "__main__":
    sys.exit(main())
