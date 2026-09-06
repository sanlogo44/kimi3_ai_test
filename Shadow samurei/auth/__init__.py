"""Authentifizierungspaket: Benutzerverwaltung der Desktop-Oberfläche.

Enthält:
* ``auth.auth_manager`` – Benutzerverwaltung inklusive CustomTkinter-Oberfläche

Die Anmeldung der Weboberfläche liegt vollständig in Rust (``rust/web``).
Beide Wege nutzen dieselben Konten aus ``data/users.json``.
"""
from auth.auth_manager import (
    AnmeldeFenster,
    AuthManager,
    AuthManagerUI,
    PasswortAendernFenster,
    ROLLEN_ANZEIGE,
)

__all__ = [
    "AuthManager",
    "AuthManagerUI",
    "AnmeldeFenster",
    "PasswortAendernFenster",
    "ROLLEN_ANZEIGE",
]
