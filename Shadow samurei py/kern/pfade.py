"""Ermittelt die Pfade des Projekts.

Der Projektordner wird in dieser Reihenfolge bestimmt:

1. Umgebungsvariable SHADOW_ORDNER,
2. der erste Ordner ab dem Arbeitsverzeichnis nach oben, der eine
   config.yaml enthält,
3. das Arbeitsverzeichnis selbst.
"""

import os

#: Name der Umgebungsvariable, mit der sich der Projektordner setzen lässt.
UMGEBUNGSVARIABLE = "SHADOW_ORDNER"


def projektordner():
    """Gibt den Projektordner zurück."""
    wert = os.environ.get(UMGEBUNGSVARIABLE, "")
    if wert:
        return wert
    start = os.getcwd()
    kandidat = start
    while True:
        if os.path.isfile(os.path.join(kandidat, "config.yaml")):
            return kandidat
        parent = os.path.dirname(kandidat)
        if parent == kandidat:
            break
        kandidat = parent
    return start


def datenordner():
    """Gibt den Ordner data/ des Projekts zurück."""
    return os.path.join(projektordner(), "data")


def datendatei(name):
    """Gibt den Pfad einer Datei im Ordner data/ zurück."""
    return os.path.join(datenordner(), name)


def stelle_ordner_bereit(datei):
    """Legt den übergeordneten Ordner einer Datei an, falls er fehlt."""
    ordner = os.path.dirname(datei)
    if ordner:
        os.makedirs(ordner, exist_ok=True)


def schreibe_atomar(datei, inhalt):
    """Schreibt Text so, dass die Zieldatei nie halb beschrieben zurückbleibt.

    Der Inhalt landet zuerst in einer Datei mit der Endung .tmp und wird
    anschließend über die Zieldatei geschoben.
    """
    stelle_ordner_bereit(datei)
    dirname, basename = os.path.split(datei)
    if "." in basename:
        name, ext = basename.rsplit(".", 1)
        zwischenziel = os.path.join(dirname, f"{name}.{ext}.tmp")
    else:
        zwischenziel = os.path.join(dirname, f"{basename}.tmp")
    with open(zwischenziel, "w", encoding="utf-8") as f:
        f.write(inhalt)
    os.replace(zwischenziel, datei)
