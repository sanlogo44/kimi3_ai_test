"""Schlanke Markdown-Anzeige für Chat-Nachrichten.

Rendert Überschriften, Listen, Zitate, Fettschrift, Kursivschrift,
Inline-Code und Code-Blöcke in einem Tkinter-Textfeld. Die Höhe des
Feldes wird automatisch an den Inhalt angepasst, sodass sich die
Nachricht wie ein normaler Textabsatz in den Chatverlauf einfügt.
"""
from __future__ import annotations

import re
import tkinter as tk
from typing import List, Tuple

from ui.theme import SCHRIFT_MONO, SCHRIFT_TEXT, ThemeVerwaltung

# Regex für Inline-Auszeichnungen: Code, Fett, Kursiv, Links
_INLINE_MUSTER = re.compile(
    r"(`[^`\n]+`)"                     # Inline-Code
    r"|(\*\*[^*\n]+\*\*)"              # **fett**
    r"|(__[^_\n]+__)"                  # __fett__
    r"|(\*[^*\n]+\*)"                  # *kursiv*
    r"|(\[[^\]\n]+\]\([^)\n]+\))"      # [Text](Ziel)
)
_LINK_MUSTER = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")


class MarkdownAnsicht(tk.Text):
    """Nur-Lese-Textfeld mit einfacher Markdown-Formatierung."""

    def __init__(self, master, theme: ThemeVerwaltung, grundschrift: int = 13,
                 hintergrund_name: str = "blase_assistent",
                 zeichen_breite: int | None = None, **kwargs):
        self._theme = theme
        self._hintergrund_name = hintergrund_name
        self._quelltext = ""
        kwargs.setdefault("wrap", "word")
        kwargs.setdefault("borderwidth", 0)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("padx", 0)
        kwargs.setdefault("pady", 0)
        kwargs.setdefault("height", 1)
        kwargs.setdefault("width", zeichen_breite or 1)
        kwargs.setdefault("cursor", "arrow")
        kwargs.setdefault("takefocus", 0)
        super().__init__(master, **kwargs)
        self._grundschrift = grundschrift
        self._konfiguriere_tags()
        self.configure(state="disabled")
        self.bind("<Configure>", self._auf_groessenaenderung)
        # Mausrad an das übergeordnete Scrollfeld weitergeben.
        for ereignis in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(ereignis, self._weiterleiten_scroll)
        theme.registriere_beobachter(lambda _modus: self.aktualisiere_farben())

    # ------------------------------------------------------------------ Farben
    def _konfiguriere_tags(self) -> None:
        """Legt Schriftarten und Farben für alle Markdown-Elemente fest."""
        g = self._grundschrift
        text = self._theme.einzelfarbe("text")
        gedaempft = self._theme.einzelfarbe("text_gedaempft")
        code_bg = self._theme.einzelfarbe("code_hintergrund")
        akzent = self._theme.einzelfarbe("akzent")

        self.configure(
            background=self._theme.einzelfarbe(self._hintergrund_name),
            foreground=text,
            insertbackground=text,
            selectbackground=akzent,
            selectforeground="#ffffff",
            font=(SCHRIFT_TEXT, g),
        )
        self.tag_configure("normal", font=(SCHRIFT_TEXT, g), foreground=text, spacing1=2, spacing3=4)
        self.tag_configure("fett", font=(SCHRIFT_TEXT, g, "bold"), foreground=text)
        self.tag_configure("kursiv", font=(SCHRIFT_TEXT, g, "italic"), foreground=text)
        self.tag_configure("h1", font=(SCHRIFT_TEXT, g + 6, "bold"), foreground=text, spacing1=8, spacing3=6)
        self.tag_configure("h2", font=(SCHRIFT_TEXT, g + 4, "bold"), foreground=text, spacing1=7, spacing3=5)
        self.tag_configure("h3", font=(SCHRIFT_TEXT, g + 2, "bold"), foreground=text, spacing1=6, spacing3=4)
        self.tag_configure("liste", font=(SCHRIFT_TEXT, g), foreground=text, lmargin1=18, lmargin2=32, spacing3=2)
        self.tag_configure("zitat", font=(SCHRIFT_TEXT, g, "italic"), foreground=gedaempft,
                           lmargin1=16, lmargin2=16, spacing1=3, spacing3=3)
        self.tag_configure("code_inline", font=(SCHRIFT_MONO, g - 1), background=code_bg, foreground=akzent)
        self.tag_configure("code_block", font=(SCHRIFT_MONO, g - 1), background=code_bg, foreground=text,
                           lmargin1=14, lmargin2=14, rmargin=14, spacing1=3, spacing3=3, wrap="none")
        self.tag_configure("code_kopf", font=(SCHRIFT_MONO, g - 3, "bold"), background=code_bg,
                           foreground=gedaempft, lmargin1=14, spacing1=6)
        self.tag_configure("link", font=(SCHRIFT_TEXT, g, "underline"), foreground=akzent)
        self.tag_configure("trenner", font=(SCHRIFT_TEXT, 4), foreground=gedaempft)

    def aktualisiere_farben(self) -> None:
        """Zeichnet den Inhalt nach einem Theme-Wechsel neu."""
        try:
            self._konfiguriere_tags()
            if self._quelltext:
                self.setze_text(self._quelltext)
        except tk.TclError:
            pass

    # -------------------------------------------------------------- Rendering
    def setze_text(self, markdown: str) -> None:
        """Ersetzt den Inhalt durch den gerenderten Markdown-Text."""
        self._quelltext = markdown or ""
        self.configure(state="normal")
        self.delete("1.0", "end")
        for text, tags in self._zerlege(self._quelltext):
            self.insert("end", text, tags)
        self.configure(state="disabled")
        self._passe_hoehe_an()

    def haenge_text_an(self, zusatz: str) -> None:
        """Erweitert den Inhalt (für zeichenweises Streaming)."""
        self.setze_text(self._quelltext + zusatz)

    @property
    def quelltext(self) -> str:
        """Gibt den zugrunde liegenden Markdown-Quelltext zurück."""
        return self._quelltext

    def _zerlege(self, markdown: str) -> List[Tuple[str, Tuple[str, ...]]]:
        """Zerlegt Markdown in Textabschnitte mit zugehörigen Tags."""
        abschnitte: List[Tuple[str, Tuple[str, ...]]] = []
        im_codeblock = False
        zeilen = markdown.split("\n")

        for nummer, zeile in enumerate(zeilen):
            letzte = nummer == len(zeilen) - 1

            if zeile.strip().startswith("```"):
                if not im_codeblock:
                    sprache = zeile.strip()[3:].strip()
                    if sprache:
                        abschnitte.append((f"{sprache}\n", ("code_kopf",)))
                    im_codeblock = True
                else:
                    im_codeblock = False
                continue

            if im_codeblock:
                abschnitte.append((zeile + "\n", ("code_block",)))
                continue

            nackt = zeile.strip()
            if not nackt:
                abschnitte.append(("\n", ("trenner",)))
                continue

            if nackt.startswith("### "):
                abschnitte.extend(self._inline(nackt[4:], ("h3",)))
            elif nackt.startswith("## "):
                abschnitte.extend(self._inline(nackt[3:], ("h2",)))
            elif nackt.startswith("# "):
                abschnitte.extend(self._inline(nackt[2:], ("h1",)))
            elif nackt.startswith("> "):
                abschnitte.extend(self._inline(nackt[2:], ("zitat",)))
            elif re.match(r"^[-*•]\s+", nackt):
                abschnitte.append(("   ·   ", ("liste",)))
                abschnitte.extend(self._inline(re.sub(r"^[-*•]\s+", "", nackt), ("liste",)))
            elif re.match(r"^\d+[.)]\s+", nackt):
                nummerierung = re.match(r"^(\d+)[.)]\s+", nackt)
                abschnitte.append((f"  {nummerierung.group(1)}.  ", ("liste",)))
                abschnitte.extend(self._inline(re.sub(r"^\d+[.)]\s+", "", nackt), ("liste",)))
            elif set(nackt) <= {"-", "_", "="} and len(nackt) >= 3:
                abschnitte.append(("─" * 40 + "\n", ("trenner",)))
                continue
            else:
                abschnitte.extend(self._inline(zeile, ("normal",)))

            if not letzte:
                abschnitte.append(("\n", ("normal",)))

        return abschnitte

    def _inline(self, text: str, grund_tags: Tuple[str, ...]) -> List[Tuple[str, Tuple[str, ...]]]:
        """Löst Inline-Auszeichnungen innerhalb einer Zeile auf."""
        ergebnis: List[Tuple[str, Tuple[str, ...]]] = []
        position = 0
        for treffer in _INLINE_MUSTER.finditer(text):
            if treffer.start() > position:
                ergebnis.append((text[position:treffer.start()], grund_tags))
            stueck = treffer.group(0)
            if stueck.startswith("`"):
                ergebnis.append((stueck.strip("`"), grund_tags + ("code_inline",)))
            elif stueck.startswith("**") or stueck.startswith("__"):
                ergebnis.append((stueck[2:-2], grund_tags + ("fett",)))
            elif stueck.startswith("["):
                link = _LINK_MUSTER.match(stueck)
                if link:
                    ergebnis.append((link.group(1), grund_tags + ("link",)))
                else:
                    ergebnis.append((stueck, grund_tags))
            else:
                ergebnis.append((stueck[1:-1], grund_tags + ("kursiv",)))
            position = treffer.end()
        if position < len(text):
            ergebnis.append((text[position:], grund_tags))
        return ergebnis or [("", grund_tags)]

    # ----------------------------------------------------------------- Layout
    def _passe_hoehe_an(self) -> None:
        """Setzt die Zeilenhöhe des Feldes passend zum Inhalt."""
        try:
            self.update_idletasks()
            zeilen = self.count("1.0", "end", "displaylines")
            anzahl = zeilen[0] if isinstance(zeilen, tuple) else zeilen
            self.configure(height=max(1, int(anzahl or 1)))
        except tk.TclError:
            pass

    def _auf_groessenaenderung(self, _ereignis=None) -> None:
        """Passt die Höhe nach einer Breitenänderung erneut an."""
        self.after_idle(self._passe_hoehe_an)

    def _weiterleiten_scroll(self, ereignis):
        """Leitet Mausrad-Ereignisse an das übergeordnete Scrollfeld weiter."""
        eltern = self.master
        while eltern is not None:
            if hasattr(eltern, "_parent_canvas"):
                canvas = eltern._parent_canvas
                if ereignis.num == 4:
                    canvas.yview_scroll(-3, "units")
                elif ereignis.num == 5:
                    canvas.yview_scroll(3, "units")
                else:
                    canvas.yview_scroll(int(-1 * (ereignis.delta / 40)), "units")
                return "break"
            eltern = getattr(eltern, "master", None)
        return None
