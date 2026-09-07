"""shadow.backend – Weiterleitung an kimi_k3.backend.

Erlaubt ``from shadow.backend import detect_backend, Backend``.
"""
from __future__ import annotations

from kimi_k3.backend import *  # noqa: F401, F403
from kimi_k3.backend import (  # noqa: F401  (explizit für IDE/Hilfe)
    Backend,
    check_driver_compat,
    detect_backend,
    detect_nvidia,
    detect_platform,
    detect_rocm,
    detect_vendor_backends,
    install_pytorch,
    torch_install_args,
)
