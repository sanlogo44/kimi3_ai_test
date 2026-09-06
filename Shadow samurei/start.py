#!/usr/bin/env python3
"""Ein-Klick-Starter für kimi3_ai_test.

Diese Datei übernimmt das vollständige Einrichten und Starten des Projekts:

  1. Python-Version prüfen (3.10 oder neuer).
  2. Virtuelle Umgebung ``venv`` anlegen, falls sie fehlt.
  3. Abhängigkeiten aus ``requirements.txt`` installieren (``pip``).
  4. Rust-Kern bauen, wenn ``cargo`` vorhanden ist (optional, aber empfohlen).
  5. Das Projekt über ``main.py`` im gewählten Modus starten.

Sie funktioniert auf Windows, macOS und Linux ohne zusätzliche manuelle
Schritte. Wenn der Rust-Kern nicht gebaut wird, läuft die Oberfläche trotzdem –
Chat und Training bleiben dann gesperrt und ein Hinweis nennt den Grund.

Aufruf:

    python start.py                 # Desktop-Oberfläche
    python start.py --modus web     # Weboberfläche auf Port 5000
    python start.py --modus cli     # Dialog im Terminal
    python start.py --modus kimi3   # lokale Kimi-K3-Inferenz (transformers)
    python start.py --kein-venv     # im aktuellen Python starten (ohne venv)
    python start.py --mit-torch     # AI-Abhängigkeiten + PyTorch installieren

Standardmäßig läuft die App OHNE AI-Abhängigkeiten: GUI, Web, CLI und
Werkzeuge starten; der Chat ist deaktiviert, bis ``--mit-torch`` gesetzt ist.
Mit der Umgebungsvariablen ``KIMI3_START_KEIN_RUST=1`` lässt sich der
Rust-Bau überspringen. Mit ``--mit-torch`` werden PyTorch/transformers
backend-spezifisch installiert (inkl. Treiberprüfung). Mit
``SKIP_DRIVER_CHECK=1`` wird die Treiberkompatibilitätsprüfung übersprungen
(z. B. in Containern mit weitergereichtem Treiber).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

#: Minimal geforderte Python-Version (Haupt, Neben)
MIN_PYTHON = (3, 10)

#: Name der virtuellen Umgebung
VENV_NAME = "venv"

#: Erwartete Python-Datei für den Einstieg
HAUPT_DATEI = "main.py"

#: Rust-Manifest, relativ zum Projektordner
RUST_MANIFEST = "rust/Cargo.toml"

#: Bash-Bauskript als Fallback
RUST_BAU_SKRIPT = "rust/bauen.sh"


# --------------------------------------------------------------------------- Hilfen
def _info(text: str) -> None:
    """Schreibt eine Informationszeile in grün auf stdout."""
    print(f"\033[1;32m[•]\033[0m {text}")


def _warnung(text: str) -> None:
    """Schreibt eine Warnung in gelb auf stderr."""
    print(f"\033[1;33m[!]\033[0m {text}", file=sys.stderr)


def _fehler(text: str) -> None:
    """Schreibt einen Fehler in rot auf stderr."""
    print(f"\033[1;31m[×]\033[0m {text}", file=sys.stderr)


def _titel(text: str) -> None:
    """Schreibt eine Überschrift."""
    print(f"\n\033[1;36m=== {text} ===\033[0m")


def projektordner() -> Path:
    """Gibt den Ordner zurück, in dem diese Datei liegt."""
    return Path(__file__).resolve().parent


# ----------------------------------------------------------------------- Schritte
def pruefe_python() -> None:
    """Bricht ab, wenn die Python-Version zu alt ist."""
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(t) for t in MIN_PYTHON)
        _fehler(f"Python {version} oder neuer ist erforderlich.")
        _fehler(f"Gefunden wurde: Python {sys.version.split()[0]}")
        _fehler("Bitte eine neuere Python-Version installieren und erneut aufrufen.")
        sys.exit(1)
    _info(f"Python {sys.version.split()[0]} erkannt.")


def venv_pfad() -> Path:
    """Gibt den Pfad zur virtuellen Umgebung zurück."""
    return projektordner() / VENV_NAME


def venv_python() -> Path:
    """Gibt den Pfad zum Python-Interpreter innerhalb der venv zurück."""
    base = venv_pfad()
    if os.name == "nt":  # Windows
        return base / "Scripts" / "python.exe"
    return base / "bin" / "python"


def venv_ist_bereit() -> bool:
    """Prüft, ob die virtuelle Umgebung bereits angelegt ist."""
    return venv_python().is_file()


def erzeuge_venv() -> Path:
    """Legt eine virtuelle Umgebung an, falls sie fehlt, und gibt den Pfad zurück."""
    pfad = venv_pfad()
    python = venv_python()

    if venv_ist_bereit():
        _info(f"Virtuelle Umgebung vorhanden: {pfad}")
        return python

    _titel("Virtuelle Umgebung anlegen")
    _info(f"Erzeuge venv in: {pfad}")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(pfad)],
            check=True,
        )
    except subprocess.CalledProcessError as fehler:
        _fehler(f"Das Anlegen der virtuellen Umgebung ist fehlgeschlagen: {fehler}")
        _fehler("Falls nötig, installiere das Paket 'venv' für deine Python-Version.")
        sys.exit(1)
    except OSError as fehler:
        _fehler(f"Python konnte die Umgebung nicht anlegen: {fehler}")
        sys.exit(1)

    if not venv_ist_bereit():
        _fehler("Die virtuelle Umgebung wurde angelegt, ist aber nicht nutzbar.")
        sys.exit(1)

    _info("Virtuelle Umgebung bereit.")
    return python


def fuehre_venv_aus(python: Path, befehl: list[str]) -> int:
    """Führt einen Befehl mit dem venv-Python aus und gibt den Rückgabewert zurück."""
    try:
        return subprocess.run([str(python), *befehl]).returncode
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        return 130
    except OSError as fehler:
        _fehler(f"Befehl konnte nicht ausgeführt werden: {fehler}")
        return 1


def aktualisiere_pip(python: Path) -> None:
    """Aktualisiert pip, damit neuere Paketversionen korrekt installiert werden."""
    _info("Aktualisiere pip ...")
    fuehre_venv_aus(python, ["-m", "pip", "install", "--upgrade", "pip"])


def installiere_requirements(python: Path) -> bool:
    """Installiert alle Pakete aus requirements.txt. Gibt True bei Erfolg zurück."""
    _titel("Abhängigkeiten installieren")
    requirements = projektordner() / "requirements.txt"
    if not requirements.is_file():
        _warnung("Keine requirements.txt gefunden – überspringe Installation.")
        return True

    _info(f"Installiere aus: {requirements}")
    code = fuehre_venv_aus(python, ["-m", "pip", "install", "-r", str(requirements)])
    if code != 0:
        _fehler("Die Installation der Abhängigkeiten ist fehlgeschlagen.")
        _fehler("Bitte die Ausgabe oben prüfen und erneut aufrufen.")
        return False
    _info("Abhängigkeiten installiert.")
    return True


def installiere_pytorch(python: Path) -> bool:
    """Installiert das backend-richtige PyTorch inkl. Treiberprüfung.

    Verwendet das integrierte ``kimi_k3``-Modul, um das passende Wheel zu
    wählen (CPU/MPS/CUDA/ROCm) und die Treiberkompatibilität VOR der
    Installation zu prüfen. Gibt True bei Erfolg zurück.
    """
    _titel("PyTorch installieren (backend-spezifisch)")
    try:
        from kimi_k3 import backend as k3backend
    except Exception as fehler:
        _fehler(f"kimi_k3-Modul konnte nicht geladen werden: {fehler}")
        _fehler("PyTorch wird über requirements.txt installiert (evtl. CUDA-Bundle).")
        return True

    backend = k3backend.detect_backend()
    cuda_version = os.environ.get("CUDA_VERSION", "cu124")
    rocm_version = os.environ.get("ROCM_VERSION", "rocm6.2")
    skip_driver = os.environ.get("SKIP_DRIVER_CHECK", "") == "1"
    try:
        k3backend.install_pytorch(
            python, backend, cuda_version=cuda_version,
            rocm_version=rocm_version, skip_driver_check=skip_driver)
    except RuntimeError as fehler:
        _fehler(str(fehler))
        return False
    return True


# ----------------------------------------------------------------------- Rust-Bau
def rust_verfuegbar() -> bool:
    """Prüft, ob der Rust-Befehl 'cargo' im Pfad liegt."""
    return shutil.which("cargo") is not None


def _ext_suffix() -> str:
    """Gibt die Dateiendung für Python-Erweiterungsmodule zurück."""
    suffix = sysconfig.get_config_var("EXT_SUFFIX") or ""
    if suffix:
        return suffix
    # Fallback für ältere Python-Versionen
    return ".pyd" if os.name == "nt" else ".so"


def _rust_kandidaten() -> list[Path]:
    """Liefert mögliche Namen der gebauten Rust-Bibliothek je Plattform."""
    projekt = projektordner()
    basis = projekt / "rust" / "target" / "release"
    namen: list[str] = []
    if sys.platform == "darwin":
        namen.append("libkimi3_kern.dylib")
    if os.name == "nt":
        namen += ["kimi3_kern.dll", "kimi3_kern.pyd", "libkimi3_kern.so"]
    # Auf allen Plattformen auch die .so-Variante berücksichtigen.
    namen.append("libkimi3_kern.so")
    gesehen: set[str] = set()
    ergebnis: list[Path] = []
    for name in namen:
        if name in gesehen:
            continue
        gesehen.add(name)
        pfad = basis / name
        if pfad not in ergebnis:
            ergebnis.append(pfad)
    return ergebnis


def rust_bibliothek_quelle() -> Path | None:
    """Gibt den Pfad der gebauten Rust-Bibliothek zurück oder None."""
    for kandidat in _rust_kandidaten():
        if kandidat.is_file():
            return kandidat
    return None


def rust_bibliothek_ziele() -> list[Path]:
    """Gibt die Pfade zurück, unter denen Python das Modul erwartet.

    Auf POSIX bleibt ``kimi3_kern.so`` erhalten (kompatibel zum bisherigen
    Bauskript). Zusätzlich wird ``kimi3_kern`` + Plattform-Suffix geschrieben,
    damit ``import kimi3_kern`` auch unter Windows (.pyd) zuverlässig greift.
    """
    projekt = projektordner()
    ziele = [projekt / ("kimi3_kern" + _ext_suffix())]
    # Auf POSIX das klassische .so zusätzlich anbieten.
    if os.name != "nt":
        klassisch = projekt / "kimi3_kern.so"
        if klassisch not in ziele:
            ziele.append(klassisch)
    return ziele


def rust_modul_da() -> bool:
    """Prüft, ob das Rust-Modul bereits im Projektordner liegt."""
    return any(ziel.is_file() for ziel in rust_bibliothek_ziele())


def baue_rust(python: Path) -> None:
    """Baut den Rust-Kern, wenn cargo vorhanden ist; sonst wird übersprungen."""
    if os.environ.get("KIMI3_START_KEIN_RUST", "").strip():
        _info("Rust-Bau durch Umgebungsvariable übersprungen.")
        return

    if rust_modul_da():
        _info("Rust-Kern bereits gebaut.")
        return

    if not rust_verfuegbar():
        _warnung("Rust (cargo) wurde nicht gefunden – überspringe Rust-Bau.")
        _warnung("Die Oberfläche startet, aber Chat und Training bleiben gesperrt.")
        _warnung("Rust bei Bedarf einrichten: https://rustup.rs")
        return

    _titel("Rust-Kern bauen")
    manifest = projektordner() / RUST_MANIFEST
    if not manifest.is_file():
        _warnung(f"Kein Rust-Manifest unter {manifest} – überspringe Rust-Bau.")
        return

    _info("cargo build --release kann einen Moment dauern ...")
    try:
        subprocess.run(
            ["cargo", "build", "--release", "--manifest-path", str(manifest)],
            cwd=str(projektordner()),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as fehler:
        _warnung(f"Der Rust-Bau ist fehlgeschlagen: {fehler}")
        _warnung("Das Projekt startet trotzdem ohne gebauten Kern.")
        return

    quelle = rust_bibliothek_quelle()
    if quelle is not None:
        for ziel in rust_bibliothek_ziele():
            try:
                shutil.copy2(quelle, ziel)
            except OSError as fehler:
                _warnung(f"Modul konnte nicht nach {ziel} kopiert werden: {fehler}")
        _info(f"Python-Modul abgelegt unter: {rust_bibliothek_ziele()[0]}")
    else:
        _warnung("Die Rust-Bibliothek wurde nicht gefunden – bitte cargo-Ausgabe prüfen.")
        _warnung("Alternativ das Bauskript direkt aufrufen: bash rust/bauen.sh")


# ----------------------------------------------------------------------- Start
def starte_projekt(python: Path, modus: str, port: int, host: str) -> int:
    """Startet main.py im gewählten Modus und gibt den Rückgabewert zurück."""
    _titel("Projekt starten")
    main_datei = projektordner() / HAUPT_DATEI
    if not main_datei.is_file():
        _fehler(f"Die Datei {HAUPT_DATEI} fehlt im Projektordner.")
        return 1

    befehl = [str(main_datei), "--modus", modus]
    if modus == "web":
        befehl += ["--host", host, "--port", str(port)]
    elif modus == "kimi3":
        # Lokale Kimi-K3-Inferenz läuft über das integrierte kimi_k3-Modul.
        _info("Starte lokale Kimi-K3-Inferenz (transformers).")
        _info("Strg+C beendet die Anwendung geordnet.\n")
        try:
            return subprocess.run(
                [str(python), "-m", "kimi_k3.inference"],
                cwd=str(projektordner()),
            ).returncode
        except KeyboardInterrupt:
            print("\nAnwendung beendet.")
            return 0
        except OSError as fehler:
            _fehler(f"Inferenz konnte nicht gestartet werden: {fehler}")
            return 1

    _info(f"Starte: python {HAUPT_DATEI} --modus {modus}" + (
        f" --host {host} --port {port}" if modus == "web" else ""
    ))
    _info("Hinweis: Strg+C beendet die Anwendung geordnet.\n")

    try:
        return subprocess.run([str(python), *befehl], cwd=str(projektordner())).returncode
    except KeyboardInterrupt:
        print("\nAnwendung beendet.")
        return 0
    except OSError as fehler:
        _fehler(f"Die Anwendung konnte nicht gestartet werden: {fehler}")
        return 1


# ------------------------------------------------------------------- Argumente
def _hilfe() -> None:
    """Gibt eine kurze Hilfe aus."""
    print("Ein-Klick-Starter für kimi3_ai_test")
    print()
    print("Aufruf:")
    print("    python start.py [Optionen]")
    print()
    print("Optionen:")
    print("    --modus <gui|web|cli|ziel|kimi3>  Startmodus (Standard: gui)")
    print("    --port <Zahl>          Port für den Modus 'web' (Standard: 5000)")
    print("    --host <Adresse>       Adresse für den Modus 'web' (Standard: 0.0.0.0)")
    print("    --kein-venv            Ohne virtuelle Umgebung starten")
    print("    --kein-rust            Rust-Bau überspringen")
    print("    --mit-torch           AI-Abhängigkeiten + PyTorch installieren (Chat aktivieren)")
    print("    --hilfe, --help        Diese Hilfe anzeigen")
    print()
    print("Umgebungsvariablen:")
    print("    KIMI3_START_KEIN_RUST=1  Rust-Bau überspringen")


def parse_argumente() -> dict:
    """Liest einfache Kommandozeilen-Argumente ohne externe Bibliotheken."""
    argumente = sys.argv[1:]
    werte = {"modus": "gui", "port": 5000, "host": "0.0.0.0",
             "kein_venv": False, "kein_rust": False, "mit_torch": False,
             "hilfe": False}

    i = 0
    while i < len(argumente):
        arg = argumente[i]
        if arg in ("--hilfe", "--help", "-h"):
            werte["hilfe"] = True
        elif arg == "--modus" and i + 1 < len(argumente):
            werte["modus"] = argumente[i + 1]
            i += 1
        elif arg == "--port" and i + 1 < len(argumente):
            try:
                werte["port"] = int(argumente[i + 1])
            except ValueError:
                _fehler(f"Ungültiger Port: {argumente[i + 1]}")
                sys.exit(1)
            i += 1
        elif arg == "--host" and i + 1 < len(argumente):
            werte["host"] = argumente[i + 1]
            i += 1
        elif arg == "--kein-venv":
            werte["kein_venv"] = True
        elif arg == "--kein-rust":
            werte["kein_rust"] = True
            os.environ["KIMI3_START_KEIN_RUST"] = "1"
        elif arg == "--mit-torch":
            werte["mit_torch"] = True
        else:
            _warnung(f"Unbekanntes Argument ignoriert: {arg}")
        i += 1

    if werte["hilfe"]:
        _hilfe()
        sys.exit(0)

    if werte["modus"] not in ("gui", "web", "cli", "ziel", "kimi3"):
        _fehler(
            f"Unbekannter Modus: {werte['modus']} "
            f"(erlaubt: gui, web, cli, ziel, kimi3)"
        )
        sys.exit(1)

    return werte


# ----------------------------------------------------------------------- Haupt
def main() -> int:
    """Führt alle Einrichtungsschritte aus und startet das Projekt."""
    argumente = parse_argumente()
    _titel("kimi3_ai_test – Ein-Klick-Starter")

    pruefe_python()

    if argumente["kein_venv"]:
        _info("Start ohne virtuelle Umgebung (Benutzer-Modus).")
        python = Path(sys.executable)
    else:
        python = erzeuge_venv()
        aktualisiere_pip(python)
        if argumente["mit_torch"]:
            if not installiere_pytorch(python):
                return 1
            _info("AI-Abhängigkeiten installieren (requirements-ai.txt) ...")
            fuehre_venv_aus(python, ["-m", "pip", "install", "-r",
                                  str(projektordner() / "requirements-ai.txt")])
        if not installiere_requirements(python):
            return 1
        baue_rust(python)

    _info("Einrichtung abgeschlossen.\n")
    return starte_projekt(
        python,
        argumente["modus"],
        argumente["port"],
        argumente["host"],
    )


if __name__ == "__main__":
    sys.exit(main())
