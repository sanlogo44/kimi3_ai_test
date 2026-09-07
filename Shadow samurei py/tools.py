"""Werkzeug-Definitionen für den KI-Assistenten.

Registriert Rechner, Wetter, Websuche und Uhrzeit als MCP-Werkzeuge.

Wichtig: Der MCP-Server ruft die Handler mit Schlüsselwortargumenten auf
(``handler(**aufruf.arguments)``). Die Parameternamen der Handler müssen
daher genau den Namen in der Werkzeugdefinition entsprechen.
"""
from __future__ import annotations

import datetime
import random
from typing import Any

from kern_modul import kern
from mcp_protocol import MCPServer, ToolDefinition, ToolParameter

# ---------------------------------------------------------------------------
# Sicherer Rechner (Auswertung im Rust-Kern)
# ---------------------------------------------------------------------------
class RechenFehler(ValueError):
    """Fehler bei der Auswertung eines mathematischen Ausdrucks."""


def berechne(ausdruck: str) -> float | int:
    """Wertet einen mathematischen Ausdruck sicher aus.

    Die Auswertung übernimmt der Rust-Kern (``kimi3_kern.berechne``): Erlaubt
    sind Zahlen, Grundrechenarten sowie die dort hinterlegten Funktionen und
    Konstanten. Ganze Ergebnisse werden wie bisher als Ganzzahl geliefert.
    """
    if not isinstance(ausdruck, str):
        raise RechenFehler("Es wurde kein Ausdruck übergeben.")
    try:
        wert = kern.berechne(ausdruck)
    except ValueError as fehler:
        raise RechenFehler(str(fehler)) from fehler
    if wert.is_integer():
        return int(wert)
    return wert


def ergebnis_text(wert: float | int) -> str:
    """Formatiert ein Rechenergebnis wie der Kern (ganze Zahlen ohne Komma)."""
    return kern.ergebnis_text(float(wert))


# ---------------------------------------------------------------------------
# Werkzeug-Handler
# ---------------------------------------------------------------------------
def rechner(expression: str | None = None, ausdruck: str | None = None) -> dict[str, Any]:
    """Berechnet einen mathematischen Ausdruck.

    Der Parameter heißt im Protokoll ``expression``; ``ausdruck`` wird als
    deutsche Schreibweise ebenfalls angenommen.
    """
    eingabe = expression if expression is not None else ausdruck
    if not eingabe:
        raise ValueError("Es wurde kein Ausdruck übergeben.")
    return {"ausdruck": eingabe, "ergebnis": berechne(eingabe)}


def wetter(
    location: str | None = None,
    unit: str = "celsius",
    ort: str | None = None,
    einheit: str | None = None,
) -> dict[str, Any]:
    """Gibt simulierte Wetterdaten für einen Ort zurück.

    Neben den Protokollnamen ``location`` und ``unit`` werden auch ``ort``
    und ``einheit`` angenommen.
    """
    location = location or ort
    if not location:
        raise ValueError("Es wurde kein Ort übergeben.")
    unit = (einheit or unit or "celsius").lower()
    if unit in ("c", "grad", "grad celsius"):
        unit = "celsius"
    if unit in ("f", "grad fahrenheit"):
        unit = "fahrenheit"
    if unit not in ("celsius", "fahrenheit"):
        unit = "celsius"
    return {
        "ort": location,
        "temperatur": random.randint(15, 28)
        if unit == "celsius"
        else random.randint(59, 82),
        "einheit": "Celsius" if unit == "celsius" else "Fahrenheit",
        "wetterlage": random.choice(
            ["Sonnig", "Bewölkt", "Leichter Regen", "Wechselhaft"]
        ),
        "luftfeuchtigkeit": random.randint(40, 80),
        "hinweis": "Simulierte Werte – keine echte Wettervorhersage.",
    }


def websuche(
    query: str | None = None,
    num_results: int = 3,
    suchbegriff: str | None = None,
    anzahl_ergebnisse: int | None = None,
) -> dict[str, Any]:
    """Gibt simulierte Suchergebnisse zurück.

    Neben den Protokollnamen ``query`` und ``num_results`` werden auch
    ``suchbegriff`` und ``anzahl_ergebnisse`` angenommen.
    """
    query = query or suchbegriff
    if not query:
        raise ValueError("Es wurde kein Suchbegriff übergeben.")
    try:
        anzahl = int(anzahl_ergebnisse or num_results or 3)
    except (TypeError, ValueError):
        anzahl = 3
    anzahl = max(1, min(10, anzahl))
    return {
        "suchbegriff": query,
        "ergebnisse": [
            {
                "titel": f"Ergebnis {nummer + 1} zu „{query}“",
                "url": f"https://example.com/{nummer}",
                "textvorschau": f"Textvorschau für Ergebnis {nummer + 1} ...",
            }
            for nummer in range(anzahl)
        ],
        "hinweis": "Simulierte Ergebnisse – keine echte Websuche.",
    }


def uhrzeit() -> dict[str, Any]:
    """Gibt die aktuelle lokale Uhrzeit zurück."""
    jetzt = datetime.datetime.now().astimezone()
    return {
        "zeitpunkt": jetzt.isoformat(timespec="seconds"),
        "datum": jetzt.strftime("%d.%m.%Y"),
        "uhrzeit": jetzt.strftime("%H:%M:%S"),
        "zeitzone": jetzt.tzname() or "lokal",
    }


def create_math_tools() -> MCPServer:
    """Erstellt einen MCP-Server mit allen verfügbaren Werkzeugen."""
    server = MCPServer()

    server.register_tool(
        ToolDefinition(
            "calculator",
            "Führt mathematische Berechnungen durch.",
            [ToolParameter("expression", "string", "Zum Beispiel 2+2 oder sqrt(16)")],
        ),
        rechner,
    )

    server.register_tool(
        ToolDefinition(
            "get_weather",
            "Gibt Wetterdaten für einen Ort zurück (simuliert).",
            [
                ToolParameter("location", "string", "Name der Stadt"),
                ToolParameter(
                    "unit",
                    "string",
                    "Temperatureinheit",
                    False,
                    ["celsius", "fahrenheit"],
                    "celsius",
                ),
            ],
        ),
        wetter,
    )

    server.register_tool(
        ToolDefinition(
            "web_search",
            "Führt eine Websuche durch (simuliert).",
            [
                ToolParameter("query", "string", "Suchbegriff"),
                ToolParameter(
                    "num_results", "number", "Anzahl der Ergebnisse", False, default=3
                ),
            ],
        ),
        websuche,
    )

    server.register_tool(
        ToolDefinition("get_current_time", "Gibt die aktuelle Uhrzeit zurück.", []),
        uhrzeit,
    )

    return server


# Deutscher Aliasname
erstelle_werkzeuge = create_math_tools


if __name__ == "__main__":  # pragma: no cover - manueller Test
    import asyncio

    from mcp_protocol import ToolCall

    server = create_math_tools()
    for aufruf in (
        ToolCall("calculator", {"expression": "17*23+42"}, "t1"),
        ToolCall("get_weather", {"location": "Scharbeutz"}, "t2"),
        ToolCall("web_search", {"query": "MCP", "num_results": 2}, "t3"),
        ToolCall("get_current_time", {}, "t4"),
    ):
        print(asyncio.run(server.execute(aufruf)))
