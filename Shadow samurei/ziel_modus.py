"""Ziel-Modus: arbeitet und testet, bis ein Ziel erreicht ist.

Der Ziel-Modus ist eine autonome Schleife über dem bestehenden Schwarm:

  1. Der **Schwarm** (Planer, Bearbeiter, Kritiker, Zusammenfasser) bearbeitet
     das Ziel und liefert ein Ergebnis.
  2. Der **Tester** prüft objektiv, ob das Ziel wirklich erreicht ist. Er ist
     pro Versuch *zustandslos* (frische Agent-Instanz), damit frühere
     Antworten ihn nicht weichspülen. Er antwortet strikt mit
     ``ERREICHT`` oder ``NICHT_ERREICHT: <Grund>``.
  3. Optional laufen **echte Prüfungen** (z. B. ``py_compile``), bevor der
     Tester fragt. Schlägt eine echte Prüfung fehl, gilt das Ziel als nicht
     erreicht – ungeachtet der Meinung des Testers.
  4. Ist das Ziel nicht erreicht, wird das Feedback in den nächsten Versuch
     eingespeist. Nach ``max_versuche`` wird ein Teilergebnis geliefert.

Wichtig: „getestet" heißt hier *nur dann* echte Prüfung, wenn eine echte
Prüfung konfiguriert wurde. Ohne solche ist es eine *Prüfung durch den
Tester-Agenten*, was schwächer ist. Das wird im Ergebnis ausgewiesen.
"""
from __future__ import annotations

import os
import py_compile
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from logger import get_logger
from mcp_protocol import MCPServer
from schwarm import Agent, SchwarmOrchester


#: Signatur einer echten Prüfung. Sie erhält das Ziel und das letzte Ergebnis
#: und liefert (erfuellt, rueckmeldung).
Pruefung = Callable[[str, Dict[str, Any]], Tuple[bool, str]]


class ZielModus:
    """Autonomer Modus, der iteriert, bis das Ziel erreicht ist.

    Für jeden Aufruf von :meth:`arbeite_bis_ziel` wird ein *frischer* Schwarm
    erzeugt, damit alte Versuche spätere Ziele nicht beeinflussen. Der Tester
    ist pro Versuch zustandslos.
    """

    def __init__(
        self,
        llm: Any,
        server: MCPServer,
        max_versuche: int = 5,
        pruefungen: Optional[List[Pruefung]] = None,
    ) -> None:
        self.llm = llm
        self.server = server
        self.log = get_logger()
        self.max_versuche = max(1, min(10, max_versuche))
        self.pruefungen: List[Pruefung] = list(pruefungen or [])

    # ------------------------------------------------------------- Tester
    def _neuer_tester(self) -> Agent:
        """Erzeugt einen frischen, zustandslosen Tester-Agenten."""
        return Agent(
            "Tester",
            "Tester",
            "Du prüfst objektiv, ob ein Ziel erreicht wurde. Du bist "
            "anspruchsvoll und lässt dich nicht durch Höflichkeit oder "
            "Teilerfolge überzeugen. Prüfe nur das tatsächliche Ergebnis "
            "gegen das Ziel. Antworte ausschließlich mit 'ERREICHT' oder "
            "mit 'NICHT_ERREICHT: <konkreter Grund>'.",
            self.server,
        )

    def _teste(
        self,
        ziel: str,
        ergebnis: Dict[str, Any],
        abbruch: Optional[threading.Event],
        status: Optional[Callable[[str], None]],
    ) -> Tuple[bool, str]:
        """Prüft, ob das Ziel erreicht ist, und gibt (erfuellt, feedback)."""
        antwort = (ergebnis.get("response") or "").strip()
        kontext = f"Ziel:\n{ziel}\n\nErgebnis:\n{antwort}"

        # 1) Echte Prüfungen zuerst – sie haben Vorrang vor dem Tester.
        for pruefung in self.pruefungen:
            try:
                erfuellt, meldung = pruefung(ziel, ergebnis)
            except Exception as fehler:  # Prüfungsfehler gilt als nicht erfüllt.
                erfuellt, meldung = False, f"Prüfung fehlerhaft: {fehler}"
            if not erfuellt:
                return False, meldung

        # 2) Tester-Agent entscheidet.
        tester = self._neuer_tester()
        pruef_ergebnis = tester.frage(
            self.llm,
            f"Prüfe, ob das folgende Ziel erreicht wurde.\n\n{kontext}\n\n"
            "Antworte mit 'ERREICHT' oder 'NICHT_ERREICHT: <Grund>'.",
            abbruch=abbruch,
            status=status,
        )
        urteil = (pruef_ergebnis.get("response") or "").strip()
        return self._auswerten(urteil)

    @staticmethod
    def _auswerten(urteil: str) -> Tuple[bool, str]:
        """Wertet die Tester-Antwort streng aus."""
        text = urteil.strip()
        if not text:
            return False, "Der Tester hat kein Urteil abgegeben."
        erste_zeile = text.splitlines()[0].strip()
        oben = erste_zeile.upper()
        if oben == "ERREICHT":
            return True, ""
        if oben.startswith("NICHT_ERREICHT"):
            _, _, grund = erste_zeile.partition(":")
            grund = grund.strip()
            return False, grund or "Kein Grund angegeben."
        if oben.startswith("NICHT ERREICHT"):
            _, _, grund = erste_zeile.partition(":")
            grund = grund.strip()
            return False, grund or "Kein Grund angegeben."
        # Kein klares Urteil → sicherheitshalber als nicht erreicht werten.
        return False, erste_zeile or text

    # --------------------------------------------------------------- Ablauf
    def arbeite_bis_ziel(
        self,
        ziel: str,
        verlauf: Optional[List[Dict[str, str]]] = None,
        teilstueck_rueckmeldung: Optional[Callable[[str], None]] = None,
        abbruch: Optional[threading.Event] = None,
        status_rueckmeldung: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Arbeitet so lange am Ziel, bis es erreicht ist oder das Limit greift.

        Die Rückgabe ist kompatibel zu ``ToolAugmentedLLM.chat_with_tools`` und
        enthält zusätzlich ``ziel_erreicht``, ``versuche`` und ``protokoll``.
        """
        if status_rueckmeldung:
            status_rueckmeldung("Ziel-Modus gestartet – arbeite bis zum Ziel.")

        protokoll: List[Dict[str, Any]] = []
        gesammelte_werkzeuge: List[Any] = []
        gesammelte_ergebnisse: List[Any] = []
        letztes_ergebnis: Dict[str, Any] = {
            "response": "",
            "tool_calls": [],
            "tool_results": [],
            "conversation": list(verlauf or []),
            "abgebrochen": False,
        }
        feedback = ""

        for versuch in range(1, self.max_versuche + 1):
            if abbruch is not None and abbruch.is_set():
                return self._abbruch(ziel, verlauf, gesammelte_werkzeuge,
                                    protokoll, versuch - 1)

            if status_rueckmeldung:
                status_rueckmeldung(
                    f"Versuch {versuch}/{self.max_versuche}: "
                    "Schwarm bearbeitet das Ziel."
                )

            # Frischer Schwarm pro Versuch.
            schwarm = SchwarmOrchester(llm=self.llm, server=self.server)

            aufgabe = ziel
            if feedback:
                aufgabe = (
                    f"{ziel}\n\n"
                    "Hinweis aus der vorherigen Prüfung (bitte beheben):\n"
                    f"{feedback}"
                )

            ergebnis = schwarm.beantworte(
                aufgabe,
                verlauf=verlauf,
                teilstueck_rueckmeldung=teilstueck_rueckmeldung,
                abbruch=abbruch,
                status_rueckmeldung=status_rueckmeldung,
            )
            gesammelte_werkzeuge.extend(ergebnis.get("tool_calls", []) or [])
            gesammelte_ergebnisse.extend(ergebnis.get("tool_results", []) or [])
            letztes_ergebnis = ergebnis

            # Abbruch nach der Schwarm-Bearbeitung prüfen.
            if ergebnis.get("abgebrochen") or (
                abbruch is not None and abbruch.is_set()
            ):
                return self._abbruch(ziel, verlauf, gesammelte_werkzeuge,
                                    protokoll, versuch - 1)

            # Testen.
            if status_rueckmeldung:
                status_rueckmeldung(f"Versuch {versuch}: Tester prüft das Ergebnis.")
            erfuellt, urteil = self._teste(
                ziel, ergebnis, abbruch, status_rueckmeldung
            )

            # Abbruch nach der Prüfung noch einmal prüfen.
            if abbruch is not None and abbruch.is_set():
                return self._abbruch(ziel, verlauf, gesammelte_werkzeuge,
                                    protokoll, versuch - 1)

            protokoll.append(
                {
                    "versuch": versuch,
                    "ergebnis": (ergebnis.get("response") or "").strip(),
                    "erfuellt": erfuellt,
                    "urteil": urteil,
                }
            )

            if erfuellt:
                if status_rueckmeldung:
                    status_rueckmeldung("Ziel erreicht – fertig.")
                return self._erfolg(ziel, verlauf, gesammelte_werkzeuge,
                                    protokoll, ergebnis)

            feedback = urteil

        # Limit erreicht.
        if status_rueckmeldung:
            status_rueckmeldung(
                "Ziel nach allen Versuchen nicht sicher erreicht."
            )
        return self._teilerfolg(ziel, verlauf, gesammelte_werkzeuge,
                               gesammelte_ergebnisse, protokoll,
                               letztes_ergebnis, feedback)

    # ----------------------------------------------------------- Ergebnisform
    def _erfolg(
        self,
        ziel: str,
        verlauf: Optional[List[Dict[str, str]]],
        werkzeuge: List[Any],
        protokoll: List[Dict[str, Any]],
        ergebnis: Dict[str, Any],
    ) -> Dict[str, Any]:
        antwort = (ergebnis.get("response") or "").strip()
        neu_verlauf = list(verlauf or [])
        neu_verlauf.append({"role": "user", "content": ziel})
        neu_verlauf.append({"role": "assistant", "content": antwort})
        if len(neu_verlauf) > 20:
            neu_verlauf = neu_verlauf[-20:]
        return {
            "response": antwort,
            "tool_calls": werkzeuge,
            "tool_results": [],
            "conversation": neu_verlauf,
            "abgebrochen": False,
            "ziel_erreicht": True,
            "versuche": len(protokoll),
            "protokoll": protokoll,
            "schwarm": True,
        }

    def _teilerfolg(
        self,
        ziel: str,
        verlauf: Optional[List[Dict[str, str]]],
        werkzeuge: List[Any],
        gesammelte_ergebnisse: List[Any],
        protokoll: List[Dict[str, Any]],
        ergebnis: Dict[str, Any],
        feedback: str,
    ) -> Dict[str, Any]:
        antwort = (ergebnis.get("response") or "").strip()
        hinweis = (
            "Ziel nach "
            f"{self.max_versuche} Versuchen nicht sicher erreicht."
        )
        if feedback:
            hinweis += f" Letzter Hinweis: {feedback}"
        vollstaendig = f"{hinweis}\n\nBisheriges Ergebnis:\n{antwort}" if antwort else hinweis
        neu_verlauf = list(verlauf or [])
        neu_verlauf.append({"role": "user", "content": ziel})
        neu_verlauf.append({"role": "assistant", "content": vollstaendig})
        if len(neu_verlauf) > 20:
            neu_verlauf = neu_verlauf[-20:]
        return {
            "response": vollstaendig,
            "tool_calls": werkzeuge,
            "tool_results": gesammelte_ergebnisse,
            "conversation": neu_verlauf,
            "abgebrochen": False,
            "ziel_erreicht": False,
            "versuche": len(protokoll),
            "protokoll": protokoll,
            "schwarm": True,
        }

    def _abbruch(
        self,
        ziel: str,
        verlauf: Optional[List[Dict[str, str]]],
        werkzeuge: List[Any],
        protokoll: List[Dict[str, Any]],
        versuche: int,
    ) -> Dict[str, Any]:
        antwort = "Der Ziel-Modus wurde abgebrochen."
        neu_verlauf = list(verlauf or [])
        neu_verlauf.append({"role": "user", "content": ziel})
        neu_verlauf.append({"role": "assistant", "content": antwort})
        return {
            "response": antwort,
            "tool_calls": werkzeuge,
            "tool_results": [],
            "conversation": neu_verlauf,
            "abgebrochen": True,
            "ziel_erreicht": False,
            "versuche": versuche,
            "protokoll": protokoll,
            "schwarm": True,
        }


# ----------------------------------------------------------- Echte Prüfungen
def python_datei_pruefung(
    dateien: Optional[List[str]] = None,
    basis: str = ".",
) -> Pruefung:
    """Erzeugt eine echte Prüfung, die Python-Dateien kompiliert.

    ``dateien`` kann absolut oder relativ zu ``basis`` sein. Ohne Angabe
    werden alle ``.py``-Dateien unter ``basis`` (nicht rekursiv) geprüft.
    """

    def pruefe(_ziel: str, _ergebnis: Dict[str, Any]) -> Tuple[bool, str]:
        pfade: List[str] = []
        if dateien:
            pfade = [d if os.path.isabs(d) else os.path.join(basis, d)
                     for d in dateien]
        else:
            for name in os.listdir(basis):
                if name.endswith(".py"):
                    pfade.append(os.path.join(basis, name))
        if not pfade:
            return True, "Keine Python-Dateien zur Prüfung vorhanden."
        fehler = []
        for pfad in pfade:
            try:
                py_compile.compile(pfad, doraise=True)
            except py_compile.PyCompileError as e:
                fehler.append(str(e))
            except (FileNotFoundError, OSError) as e:
                fehler.append(f"Datei nicht lesbar: {pfad} ({e})")
        if fehler:
            return False, "Python-Kompilierung fehlgeschlagen:\n" + "\n".join(fehler)
        return True, "Alle Python-Dateien sind syntaktisch korrekt."

    return pruefe


#: Rückwärtskompatibler deutscher Name
Ziel = ZielModus
