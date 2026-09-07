"""
webscraper.py – Selbstständig navigierender Webscraper für Shadow

Bewegt sich automatisch durch eine Website: startet auf einer URL,
folgt Links innerhalb derselben Domain, sammelt Text und speichert
das Ergebnis als JSONL-Trainingsdaten (anweisung/antwort) ab.

Als MCP-Werkzeug registrierbar:

    from mcp_protocol import MCPServer, ToolDefinition, ToolParameter
    from webscraper import crawl

    server.register_tool(
        ToolDefinition(
            name="webscraper",
            description="Crawlt eine Website automatisch und sammelt Text.",
            parameters=[
                ToolParameter("start_url", "string", "Einstiegs-URL"),
                ToolParameter("max_seiten", "integer", "Höchstzahl Seiten"),
            ],
        ),
        lambda start_url, max_seiten=25: crawl(start_url, max_seiten),
    )

Terminal:
    python webscraper.py https://de.wikipedia.org/wiki/K%C3%BCnstliche_Intelligenz
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

try:
    from playwright.sync_api import sync_playwright

    HAT_PLAYWRIGHT = True
except ImportError:
    HAT_PLAYWRIGHT = False

from logger import log


@dataclass
class CrawlErgebnis:
    besucht: list[str] = field(default_factory=list)
    datensaetze: list[dict] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)


def _sichtbarer_text(inhalt: str) -> str:
    """Entfernt Skripte, Styles und Navigation aus dem HTML."""
    inhalt = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", inhalt)
    text = re.sub(r"(?s)<[^>]+>", " ", inhalt)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def crawl(
    start_url: str,
    max_seiten: int = 25,
    wartezeit_ms: int = 500,
    ausgabe_pfad: str = "data/gescraped.jsonl",
) -> dict:
    """Crawlt ab start_url automatisch weiter und speichert JSONL."""
    if not HAT_PLAYWRIGHT:
        log("playwright fehlt: pip install playwright && playwright install chromium",
            stufe="FEHLER")
        return {}

    ergebnis = CrawlErgebnis()
    basis_domain = urlparse(start_url).netloc
    warteschlange = [start_url]
    gesehen = {start_url}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        seite = browser.new_page()

        while warteschlange and len(ergebnis.besucht) < max_seiten:
            url = warteschlange.pop(0)
            try:
                seite.goto(url, wait_until="domcontentloaded",
                           timeout=15000)
                seite.wait_for_timeout(wartezeit_ms)

                html = seite.content()
                titel = seite.title()
                text = _sichtbarer_text(html)
                ergebnis.besucht.append(url)

                # Trainingsbeispiel erzeugen: Seitentitel -> Inhalt
                if len(text) > 200:
                    ergebnis.datensaetze.append(
                        {"anweisung": f"Fasse die Seite '{titel}' zusammen.",
                         "antwort": text[:3000]}
                    )

                # Neue Links derselben Domain in die Warteschlange
                for href in seite.eval_on_selector_all(
                    "a[href]", "elemente => elemente.map(e => e.href)"
                ):
                    ziel = urljoin(url, href)
                    ziel = ziel.split("#")[0]  # Anker entfernen
                    if (urlparse(ziel).netloc == basis_domain
                            and ziel not in gesehen
                            and not ziel.lower().endswith(
                                (".pdf", ".jpg", ".png", ".zip"))):
                        gesehen.add(ziel)
                        warteschlange.append(ziel)

                log(f"[{len(ergebnis.besucht)}/{max_seiten}] {url}")
            except Exception as exc:  # Netzfehler einzeln auffangen
                ergebnis.fehler.append(f"{url}: {exc}")

        browser.close()

    # Ergebnis als Trainingsdaten sichern
    if ergebnis.datensaetze:
        with open(ausgabe_pfad, "a", encoding="utf-8") as f:
            for satz in ergebnis.datensaetze:
                f.write(json.dumps(satz, ensure_ascii=False) + "\n")
        log(f"{len(ergebnis.datensaetze)} Datensätze -> {ausgabe_pfad}")

    return {
        "seiten": len(ergebnis.besucht),
        "datensaetze": len(ergebnis.datensaetze),
        "fehler": len(ergebnis.fehler),
        "ausgabe": ausgabe_pfad,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Aufruf: python webscraper.py <start_url> [max_seiten]")
        raise SystemExit(1)
    max_seiten = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    bericht = crawl(sys.argv[1], max_seiten=max_seiten)
    print(json.dumps(bericht, indent=2, ensure_ascii=False))
