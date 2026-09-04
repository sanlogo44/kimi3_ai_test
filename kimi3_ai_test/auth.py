
"""Authentifizierung für den Admin-Bereich."""
import json
import os
from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "data", "credentials.json")
DEFAULT_USER = "Admin"
DEFAULT_PASS = "1234"


def _load():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Erstinitialisierung
    creds = {
        "username": DEFAULT_USER,
        "password_hash": generate_password_hash(DEFAULT_PASS),
        "must_change": True,   # beim ersten Login Passwort ändern
    }
    _save(creds)
    return creds


def _save(creds):
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)


def verify(username, password):
    creds = _load()
    return username == creds["username"] and check_password_hash(creds["password_hash"], password)


def must_change_password():
    return _load().get("must_change", False)


def change_credentials(new_username, new_password):
    creds = _load()
    creds["username"] = new_username
    creds["password_hash"] = generate_password_hash(new_password)
    creds["must_change"] = False
    _save(creds)


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper
