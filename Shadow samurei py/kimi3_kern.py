"""Re-Export-Modul für den Python-Kern.

Dieses Modul stellt die Abwärtskompatibilität sicher: früher wurde hier das
Rust-Erweiterungsmodul ``kimi3_kern`` (PyO3) importiert. Da der Kern nun in
Python geschrieben ist, leitet dieses Modul alle Zugriffe an das Paket ``kern``
weiter.

Bestehender Code wie ``from kern_modul import kern`` funktioniert weiterhin.
"""
from __future__ import annotations

from kern import *  # noqa: F401, F403
