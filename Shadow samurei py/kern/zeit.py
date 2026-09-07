"""Zeitstempel in genau den Formaten, die die Datendateien verwenden."""

import datetime

# ISO-Format der Metrikeinträge, zum Beispiel 2026-09-05T21:30:00
_ISO = "%Y-%m-%dT%H:%M:%S"
# Lesbares Format der Bewertungen, zum Beispiel 2026-09-05 21:30:00
_LESBAR = "%Y-%m-%d %H:%M:%S"
# Kurzform für Anzeigen, zum Beispiel 05.09. 21:30
_KURZ = "%d.%m. %H:%M"


def jetzt():
    """Gibt die aktuelle Ortszeit zurück; ohne Zeitzoneninfo gilt UTC."""
    return datetime.datetime.now()


def jetzt_iso():
    """Gibt den aktuellen Zeitpunkt als ISO-Text zurück (…T…)."""
    return jetzt().strftime(_ISO)


def jetzt_lesbar():
    """Gibt den aktuellen Zeitpunkt als lesbaren Text zurück (mit Leerzeichen)."""
    return jetzt().strftime(_LESBAR)


def lese(text):
    """Wandelt einen gespeicherten Zeitstempel in einen Zeitpunkt um.

    Erkannt werden das ISO-Format, das lesbare Format und ISO-Angaben mit
    Sekundenbruchteilen. Nicht lesbare Angaben ergeben None.
    """
    gekuerzt = text[:26]
    if "." in gekuerzt:
        ohne_bruchteil = gekuerzt.split(".")[0]
    else:
        ohne_bruchteil = gekuerzt
    for fmt in (_ISO, _LESBAR):
        try:
            return datetime.datetime.strptime(ohne_bruchteil, fmt)
        except ValueError:
            pass
    return None


def kurzzeit(text):
    """Gibt eine kurze, lesbare Zeitangabe zurück (05.09. 21:30).

    Lässt sich der Text nicht lesen, werden die ersten 16 Zeichen genutzt –
    genau wie in der bisherigen Python-Fassung.
    """
    zeitpunkt = lese(text)
    if zeitpunkt is not None:
        return zeitpunkt.strftime(_KURZ)
    return text[:16]


def aus_sekunden(sekunden):
    """Wandelt Unix-Sekunden in einen lesbaren Text der Ortszeit um.

    Wird für den Änderungszeitpunkt der Checkpoint-Dateien genutzt.
    """
    try:
        zeitpunkt = datetime.datetime.fromtimestamp(sekunden)
    except (ValueError, OSError, OverflowError):
        return ""
    return zeitpunkt.strftime(_LESBAR)


def vor_tagen(tage):
    """Gibt den Zeitpunkt vor tage Tagen zurück."""
    return jetzt() - datetime.timedelta(days=max(0, tage))
