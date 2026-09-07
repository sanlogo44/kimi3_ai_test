"""Kern der Anwendung: Logik und Datenhaltung in Python.

Dieses Paket enthält alles, was weder PyTorch noch eine Oberfläche
braucht: Konfiguration, Protokollierung, Einstellungen, Schalter,
Metriken, Bewertungen, Konten samt Passwortprüfung, die Verwaltung der
Checkpoint-Dateien und den sicheren Rechner.

Alle Dateien liegen wie bisher im Ordner data/ des Projekts und
behalten ihr Format, damit alte Daten weiter gelesen werden.
"""

# Zeit
from .zeit import (
    jetzt,
    jetzt_iso,
    jetzt_lesbar,
    lese,
    kurzzeit,
    aus_sekunden,
    vor_tagen,
)

# Pfade
from .pfade import (
    projektordner,
    datenordner,
    datendatei,
    stelle_ordner_bereit,
    schreibe_atomar,
    UMGEBUNGSVARIABLE,
)

# Protokollierung
from .protokoll import (
    Stufe,
    Protokoll,
    richte_protokoll_ein,
    setze_protokollstufe,
    protokolliere,
    hole_protokoll,
    setze_protokoll,
    stufe_name,
    stufe_farbe,
    stufe_aus_text,
)

# Konfiguration
from .konfiguration import (
    standardwerte,
    tiefe_zusammenfuehrung,
    lade_konfiguration,
    Konfiguration,
)

# Einstellungen
from .einstellungen import Einstellungen

# Schalter
from .schalter import Schalter

# Metriken
from .metriken import (
    Metrik,
    MetrikSpeicher,
    Zusammenfassung,
    ModellVergleich,
)

# Bewertungen
from .bewertungen import (
    BewertungsEintrag,
    BewertungsSpeicher,
    bewertungstext,
    BewertungsZusammenfassung,
)

# Passwort
from .passwort import (
    hash_passwort,
    pruefe_passwort,
    hash_benutzer_passwort,
    pruefe_benutzer_passwort,
    erzeuge_hash,
    pruefe,
    SCRYPT_N,
    SCRYPT_R,
    SCRYPT_P,
)

# Konten
from .konten import (
    Konto,
    Kontenverwaltung,
    MINDESTLAENGE_PASSWORT,
    rollenname,
)

# Checkpoints
from .checkpoints import (
    Checkpoint,
    CheckpointVerwaltung,
)

# Rechner
from .rechner import (
    berechne,
    ergebnis_text,
    RechenFehler,
)

#: Version des Pakets.
VERSION = "1.0.0"

__all__ = [
    # Zeit
    "jetzt",
    "jetzt_iso",
    "jetzt_lesbar",
    "lese",
    "kurzzeit",
    "aus_sekunden",
    "vor_tagen",
    # Pfade
    "projektordner",
    "datenordner",
    "datendatei",
    "stelle_ordner_bereit",
    "schreibe_atomar",
    "UMGEBUNGSVARIABLE",
    # Protokollierung
    "Stufe",
    "Protokoll",
    "richte_protokoll_ein",
    "setze_protokollstufe",
    "protokolliere",
    "hole_protokoll",
    "setze_protokoll",
    "stufe_name",
    "stufe_farbe",
    "stufe_aus_text",
    # Konfiguration
    "standardwerte",
    "tiefe_zusammenfuehrung",
    "lade_konfiguration",
    "Konfiguration",
    # Einstellungen
    "Einstellungen",
    # Schalter
    "Schalter",
    # Metriken
    "Metrik",
    "MetrikSpeicher",
    "Zusammenfassung",
    "ModellVergleich",
    # Bewertungen
    "BewertungsEintrag",
    "BewertungsSpeicher",
    "bewertungstext",
    "BewertungsZusammenfassung",
    # Passwort
    "hash_passwort",
    "pruefe_passwort",
    "hash_benutzer_passwort",
    "pruefe_benutzer_passwort",
    "erzeuge_hash",
    "pruefe",
    "SCRYPT_N",
    "SCRYPT_R",
    "SCRYPT_P",
    # Konten
    "Konto",
    "Kontenverwaltung",
    "MINDESTLAENGE_PASSWORT",
    "rollenname",
    # Checkpoints
    "Checkpoint",
    "CheckpointVerwaltung",
    # Rechner
    "berechne",
    "ergebnis_text",
    "RechenFehler",
    # Version
    "VERSION",
]
