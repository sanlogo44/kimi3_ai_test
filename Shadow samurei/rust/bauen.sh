#!/usr/bin/env bash
# Baut den Rust-Kern und die Weboberfläche und legt das Python-Modul
# „kimi3_kern.so“ in den Projektordner.
#
# Aufruf (aus dem Projektordner):
#     bash rust/bauen.sh
set -euo pipefail

# Ordner dieses Skripts und der darüberliegende Projektordner.
RUST_ORDNER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJEKT_ORDNER="$(cd "$RUST_ORDNER/.." && pwd)"

# Ohne Rust geht es nicht weiter.
if ! command -v cargo >/dev/null 2>&1; then
    echo "Fehler: „cargo“ wurde nicht gefunden – Rust ist offenbar nicht installiert." >&2
    echo "Rust einrichten: https://rustup.rs" >&2
    echo "Danach eine neue Sitzung öffnen und erneut „bash rust/bauen.sh“ aufrufen." >&2
    exit 1
fi

echo "Baue den Rust-Kern im Ordner: $RUST_ORDNER"
cargo build --release --manifest-path "$RUST_ORDNER/Cargo.toml"

# Die gebaute Bibliothek heißt je nach Betriebssystem anders.
case "$(uname -s)" in
    Darwin) BIBLIOTHEK="libkimi3_kern.dylib" ;;
    *)      BIBLIOTHEK="libkimi3_kern.so" ;;
esac

QUELLE="$RUST_ORDNER/target/release/$BIBLIOTHEK"
ZIEL="$PROJEKT_ORDNER/kimi3_kern.so"

if [ ! -f "$QUELLE" ]; then
    echo "Fehler: Die gebaute Bibliothek „$QUELLE“ fehlt." >&2
    echo "Bitte die Ausgabe von „cargo build“ oben prüfen." >&2
    exit 1
fi

cp "$QUELLE" "$ZIEL"
echo "Python-Modul abgelegt unter: $ZIEL"
echo "Weboberfläche liegt unter:   $RUST_ORDNER/target/release/kimi3-web"
echo "Fertig."
