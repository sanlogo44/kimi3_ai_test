"""Passwort-Hashes im Format von Werkzeug.

Damit Weboberfläche (Rust) und Desktop-Oberfläche (Python) dieselbe
Datei data/users.json nutzen können, wird genau das Format von
werkzeug.security erzeugt und geprüft:

* scrypt:n:r:p$salz$hex – Standard neuerer Werkzeug-Fassungen,
* pbkdf2:sha256:runden$salz$hex – Format älterer Fassungen.

Der Vergleich der Hashes läuft zeitunabhängig (hmac.compare_digest).
"""

import hashlib
import hmac
import secrets
import string

#: Länge des abgeleiteten Schlüssels bei scrypt (wie bei Werkzeug).
SCRYPT_LAENGE = 64
#: Standardparameter von Werkzeug für scrypt.
SCRYPT_N = 32768
SCRYPT_R = 8
SCRYPT_P = 1
#: Länge des Salzes in Zeichen (wie bei Werkzeug).
SALZ_LAENGE = 16
#: Zeichenvorrat des Salzes (wie bei Werkzeug: Buchstaben und Ziffern).
SALZ_ZEICHEN = string.ascii_letters + string.digits


def _salz():
    """Erzeugt ein zufälliges Salz."""
    return "".join(secrets.choice(SALZ_ZEICHEN) for _ in range(SALZ_LAENGE))


def _scrypt_hash(passwort, salz, n, r, p):
    """Berechnet den scrypt-Hash eines Passworts."""
    try:
        dk = hashlib.scrypt(
            passwort.encode("utf-8"),
            salt=salz.encode("utf-8"),
            n=n, r=r, p=p,
            dklen=SCRYPT_LAENGE,
            maxmem=132 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return None
    return dk.hex()


def _pbkdf2_hash(passwort, salz, runden):
    """Berechnet den pbkdf2-Hash eines Passworts (SHA-256)."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        passwort.encode("utf-8"),
        salz.encode("utf-8"),
        runden,
        dklen=32,
    )
    return dk.hex()


def erzeuge_hash(passwort):
    """Erzeugt einen Passwort-Hash im Werkzeug-Format (scrypt)."""
    salz = _salz()
    hash_wert = _scrypt_hash(passwort, salz, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    if hash_wert is not None:
        return f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${salz}${hash_wert}"
    # Sollte nicht vorkommen; dann gilt das ältere, ebenfalls
    # unterstützte Verfahren.
    runden = 1_000_000
    return f"pbkdf2:sha256:{runden}${salz}${_pbkdf2_hash(passwort, salz, runden)}"


def pruefe(hash_wert, passwort):
    """Prüft ein Passwort gegen einen gespeicherten Hash.

    Unbekannte Verfahren und defekte Hashes ergeben False.
    """
    teile = hash_wert.split("$", 2)
    if len(teile) < 3:
        return False
    verfahren, salz, erwartet = teile
    angaben = verfahren.split(":")
    berechnet = None
    if len(angaben) == 4 and angaben[0] == "scrypt":
        try:
            n = int(angaben[1])
            r = int(angaben[2])
            p = int(angaben[3])
        except ValueError:
            return False
        berechnet = _scrypt_hash(passwort, salz, n, r, p)
        if berechnet is None:
            return False
    elif len(angaben) == 3 and angaben[0] == "pbkdf2" and angaben[1] == "sha256":
        try:
            runden = int(angaben[2])
        except ValueError:
            return False
        berechnet = _pbkdf2_hash(passwort, salz, runden)
    elif len(angaben) == 2 and angaben[0] == "pbkdf2" and angaben[1] == "sha256":
        berechnet = _pbkdf2_hash(passwort, salz, 260_000)
    else:
        return False
    return hmac.compare_digest(berechnet, erwartet)


# --- Werkzeug-kompatible API-Namen ---

def hash_passwort(passwort):
    """Erzeugt einen Passwort-Hash im Werkzeug-Format."""
    return erzeuge_hash(passwort)


def pruefe_passwort(passwort, gehasht):
    """Prüft ein Passwort gegen einen gespeicherten Hash."""
    return pruefe(gehasht, passwort)


def hash_benutzer_passwort(passwort, algo="auto"):
    """Erzeugt einen Passwort-Hash im Werkzeug-Format.

    algo kann 'auto', 'scrypt' oder 'pbkdf2' sein.
    """
    if algo in ("auto", "scrypt"):
        return erzeuge_hash(passwort)
    elif algo == "pbkdf2":
        salz = _salz()
        runden = 1_000_000
        return f"pbkdf2:sha256:{runden}${salz}${_pbkdf2_hash(passwort, salz, runden)}"
    return erzeuge_hash(passwort)


def pruefe_benutzer_passwort(passwort, gehasht):
    """Prüft ein Passwort gegen einen gespeicherten Hash."""
    return pruefe(gehasht, passwort)
