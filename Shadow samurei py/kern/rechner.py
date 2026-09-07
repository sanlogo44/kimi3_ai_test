"""Sicherer Rechner für mathematische Ausdrücke.

Entspricht tools.berechne aus der Python-Fassung: erlaubt sind Zahlen,
die Grundrechenarten, Vorzeichen, ein festgelegter Satz Funktionen und
die Konstanten pi, e und tau. Ausgewertet wird über einen eigenen
Parser – es gibt weder eval noch sonst einen Umweg über fremden Code.
"""

import math

#: Höchstlänge eines Ausdrucks.
HOECHSTLAENGE = 300
#: Obergrenze für Potenzen, damit kein Ausdruck den Rechner blockiert.
HOECHSTER_EXPONENT = 64.0


class RechenFehler(Exception):
    """Fehler bei der Auswertung eines Ausdrucks."""

    def __init__(self, meldung):
        super().__init__(meldung)
        self.meldung = meldung

    def __str__(self):
        return self.meldung


# --- Token-Typen ---
_ZAHL = "zahl"
_NAME = "name"
_KLAMMER = "klammer"
_KOMMA = "komma"
_OPERATOR = "operator"


def _zerlege(ausdruck):
    """Zerlegt den Ausdruck in Bausteine."""
    zeichen = list(ausdruck)
    bausteine = []
    stelle = 0
    while stelle < len(zeichen):
        z = zeichen[stelle]
        if z.isspace():
            stelle += 1
        elif z.isdigit() or z == ".":
            beginn = stelle
            while stelle < len(zeichen) and (
                zeichen[stelle].isdigit()
                or zeichen[stelle] == "."
                or zeichen[stelle] == "_"
            ):
                stelle += 1
            # Exponentialschreibweise, etwa 1e-3
            if stelle < len(zeichen) and (
                zeichen[stelle] == "e" or zeichen[stelle] == "E"
            ):
                merker = stelle
                vorschau = stelle + 1
                if vorschau < len(zeichen) and (
                    zeichen[vorschau] == "+" or zeichen[vorschau] == "-"
                ):
                    vorschau += 1
                if vorschau < len(zeichen) and zeichen[vorschau].isdigit():
                    stelle = vorschau
                    while stelle < len(zeichen) and zeichen[stelle].isdigit():
                        stelle += 1
                else:
                    stelle = merker
            text = "".join(zeichen[beginn:stelle])
            try:
                zahl = float(text.replace("_", ""))
            except ValueError:
                raise RechenFehler(
                    f"Ungültiger Ausdruck: „{text}“ ist keine Zahl."
                )
            bausteine.append((_ZAHL, zahl))
        elif z.isalpha() or z == "_":
            beginn = stelle
            while stelle < len(zeichen) and (
                zeichen[stelle].isalnum() or zeichen[stelle] == "_"
            ):
                stelle += 1
            bausteine.append((_NAME, "".join(zeichen[beginn:stelle])))
        elif z == "(" or z == ")":
            bausteine.append((_KLAMMER, z))
            stelle += 1
        elif z == ";":
            bausteine.append((_KOMMA, None))
            stelle += 1
        elif z in "+-*/%":
            doppelt = (
                stelle + 1 < len(zeichen) and zeichen[stelle + 1] == z
            )
            if doppelt and (z == "*" or z == "/"):
                bausteine.append((_OPERATOR, f"{z}{z}"))
                stelle += 2
            else:
                bausteine.append((_OPERATOR, z))
                stelle += 1
        else:
            raise RechenFehler(
                f"Ungültiger Ausdruck: „{z}“ ist nicht erlaubt."
            )
    return bausteine


class _Auswertung:
    """Wertet die Bausteine von links nach rechts aus."""

    def __init__(self, bausteine):
        self.bausteine = bausteine
        self.stelle = 0

    def _schau(self):
        """Gibt den nächsten Baustein zurück, ohne weiterzugehen."""
        if self.stelle < len(self.bausteine):
            return self.bausteine[self.stelle]
        return None

    def _ist_operator(self, zeichen):
        """Prüft, ob an dieser Stelle der angegebene Operator steht."""
        token = self._schau()
        return token is not None and token[0] == _OPERATOR and token[1] == zeichen

    def summe(self):
        """Summe und Differenz."""
        wert = self.produkt()
        while True:
            if self._ist_operator("+"):
                self.stelle += 1
                wert += self.produkt()
            elif self._ist_operator("-"):
                self.stelle += 1
                wert -= self.produkt()
            else:
                return wert

    def produkt(self):
        """Produkt, Quotient, Ganzzahldivision und Restwert."""
        wert = self.vorzeichen()
        while True:
            token = self._schau()
            if (
                token is not None
                and token[0] == _OPERATOR
                and token[1] in ("*", "/", "//", "%")
            ):
                operator = token[1]
                self.stelle += 1
                rechts = self.vorzeichen()
                if rechts == 0.0 and operator != "*":
                    raise RechenFehler("Division durch Null.")
                if operator == "*":
                    wert = wert * rechts
                elif operator == "/":
                    wert = wert / rechts
                elif operator == "//":
                    wert = float(math.floor(wert / rechts))
                else:  # % – Restwert mit dem Vorzeichen des Teilers, wie in Python
                    wert = wert % rechts
            else:
                return wert

    def vorzeichen(self):
        """Vorzeichen vor einem Wert."""
        if self._ist_operator("-"):
            self.stelle += 1
            return -self.vorzeichen()
        if self._ist_operator("+"):
            self.stelle += 1
            return self.vorzeichen()
        return self.potenz()

    def potenz(self):
        """Potenz; rechts vor links, wie in Python."""
        basis = self.wert()
        if self._ist_operator("**"):
            self.stelle += 1
            exponent = self.vorzeichen()
            if abs(exponent) > HOECHSTER_EXPONENT:
                raise RechenFehler(
                    f"Der Exponent darf höchstens {int(HOECHSTER_EXPONENT)} sein."
                )
            if basis == 0.0 and exponent < 0.0:
                raise RechenFehler("Division durch Null.")
            return basis ** exponent
        return basis

    def wert(self):
        """Zahl, Konstante, Klammerausdruck oder Funktionsaufruf."""
        token = self._schau()
        if token is None:
            raise RechenFehler("Ungültiger Ausdruck: Er endet zu früh.")
        typ, val = token
        if typ == _ZAHL:
            self.stelle += 1
            return val
        elif typ == _KLAMMER and val == "(":
            self.stelle += 1
            wert = self.summe()
            token = self._schau()
            if token is None or token[0] != _KLAMMER or token[1] != ")":
                raise RechenFehler(
                    "Ungültiger Ausdruck: Es fehlt eine schließende Klammer."
                )
            self.stelle += 1
            return wert
        elif typ == _NAME:
            self.stelle += 1
            name = val
            token = self._schau()
            if token is not None and token[0] == _KLAMMER and token[1] == "(":
                argumente = self.argumente()
                return _funktion(name, argumente)
            if name == "pi":
                return math.pi
            elif name == "e":
                return math.e
            elif name == "tau":
                return math.tau
            else:
                raise RechenFehler(f"Unbekannter Name: {name}")
        elif typ == _OPERATOR:
            raise RechenFehler(
                f"Ungültiger Ausdruck: „{val}“ steht an falscher Stelle."
            )
        else:
            raise RechenFehler("Ungültiger Ausdruck: unerwartetes Zeichen.")

    def argumente(self):
        """Liest die Argumentliste eines Funktionsaufrufs."""
        # Die öffnende Klammer ist geprüft, aber noch nicht übersprungen.
        self.stelle += 1
        werte = []
        token = self._schau()
        if token is not None and token[0] == _KLAMMER and token[1] == ")":
            self.stelle += 1
            return werte
        while True:
            werte.append(self.summe())
            token = self._schau()
            if token is None:
                raise RechenFehler(
                    "Ungültiger Ausdruck: Es fehlt eine schließende Klammer."
                )
            if token[0] == _KOMMA:
                self.stelle += 1
            elif token[0] == _KLAMMER and token[1] == ")":
                self.stelle += 1
                return werte
            else:
                raise RechenFehler(
                    "Ungültiger Ausdruck: Es fehlt eine schließende Klammer."
                )


def _funktion(name, argumente):
    """Ruft eine der erlaubten Funktionen auf."""
    def eines(zweck):
        if len(argumente) == 1:
            return argumente[0]
        raise RechenFehler(f"Die Funktion {zweck} erwartet genau einen Wert.")

    if name == "abs":
        return abs(eines("abs"))
    elif name == "round":
        if len(argumente) == 1:
            return _runde(argumente[0], 0)
        elif len(argumente) == 2:
            return _runde(argumente[0], int(argumente[1]))
        else:
            raise RechenFehler(
                "Die Funktion round erwartet einen oder zwei Werte."
            )
    elif name in ("min", "max", "sum"):
        if not argumente:
            raise RechenFehler(
                f"Die Funktion {name} erwartet mindestens einen Wert."
            )
        if name == "min":
            return min(argumente)
        elif name == "max":
            return max(argumente)
        else:
            return sum(argumente)
    elif name == "sqrt":
        wert = eines("sqrt")
        if wert < 0.0:
            raise RechenFehler(
                "Die Wurzel aus einer negativen Zahl ist nicht definiert."
            )
        return math.sqrt(wert)
    elif name == "pow":
        if len(argumente) == 2:
            basis, exponent = argumente
            if abs(exponent) > HOECHSTER_EXPONENT:
                raise RechenFehler(
                    f"Der Exponent darf höchstens {int(HOECHSTER_EXPONENT)} sein."
                )
            if basis == 0.0 and exponent < 0.0:
                raise RechenFehler("Division durch Null.")
            return basis ** exponent
        else:
            raise RechenFehler("Die Funktion pow erwartet genau zwei Werte.")
    elif name == "log":
        if len(argumente) == 1:
            return _logarithmus(argumente[0], math.e)
        elif len(argumente) == 2:
            return _logarithmus(argumente[0], argumente[1])
        else:
            raise RechenFehler(
                "Die Funktion log erwartet einen oder zwei Werte."
            )
    elif name == "log10":
        return _logarithmus(eines("log10"), 10.0)
    elif name == "exp":
        return math.exp(eines("exp"))
    elif name == "sin":
        return math.sin(eines("sin"))
    elif name == "cos":
        return math.cos(eines("cos"))
    elif name == "tan":
        return math.tan(eines("tan"))
    else:
        raise RechenFehler(f"Unbekannte Funktion: {name}")


def _logarithmus(wert, grundzahl):
    """Berechnet den Logarithmus mit Prüfung des Wertebereichs."""
    if wert <= 0.0:
        raise RechenFehler(
            "Der Logarithmus ist nur für positive Zahlen definiert."
        )
    if grundzahl <= 0.0 or grundzahl == 1.0:
        raise RechenFehler("Diese Grundzahl ist nicht erlaubt.")
    if grundzahl == 10.0:
        return math.log10(wert)
    if grundzahl == math.e:
        return math.log(wert)
    if grundzahl == 2.0:
        return math.log2(wert)
    return math.log(wert) / math.log(grundzahl)


def _runde(wert, stellen):
    """Rundet wie Python: zur nächsten geraden Zahl bei genau 0,5."""
    return float(round(wert, stellen))


def berechne(ausdruck):
    """Wertet einen mathematischen Ausdruck aus.

    ^ gilt als Potenz und , als Dezimaltrennzeichen – genau wie in der
    bisherigen Python-Fassung.
    """
    if not ausdruck.strip():
        raise RechenFehler("Es wurde kein Ausdruck übergeben.")
    if len(ausdruck) > HOECHSTLAENGE:
        raise RechenFehler("Der Ausdruck ist zu lang.")
    vorbereitet = ausdruck.replace("^", "**").replace(",", ".")
    bausteine = _zerlege(vorbereitet)
    if not bausteine:
        raise RechenFehler("Es wurde kein Ausdruck übergeben.")
    auswertung = _Auswertung(bausteine)
    wert = auswertung.summe()
    if auswertung.stelle != len(auswertung.bausteine):
        raise RechenFehler(
            "Ungültiger Ausdruck: Er enthält überzählige Zeichen."
        )
    if not math.isfinite(wert):
        raise RechenFehler("Das Ergebnis ist keine gültige Zahl.")
    return wert


def ergebnis_text(wert):
    """Gibt ein Ergebnis so aus, wie es die Oberfläche anzeigt.

    Ganze Zahlen erscheinen ohne Nachkommastellen.
    """
    try:
        if wert == int(wert) and abs(wert) < 1e15:
            return str(int(wert))
    except (OverflowError, ValueError):
        pass
    return str(wert)
