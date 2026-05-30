#!/usr/bin/env python3
"""Standalone launcher for the TFIAC CLI.

The integration's ``custom_components/tfiac_local/__init__.py`` imports Home
Assistant, so the package cannot be imported with ``-m`` outside an HA install.
This launcher loads only the Home-Assistant-free modules (``const``,
``tfiac_client``, ``cli``) into a synthetic package and runs the CLI, so device
discovery/status/set works with nothing but Python installed.

Usage:
    python tfiac_cli.py discover
    python tfiac_cli.py status --host 192.168.1.50
    python tfiac_cli.py set --host 192.168.1.50 --power on --hvac cool ...
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_COMPONENT_DIR = (
    Path(__file__).resolve().parent / "custom_components" / "tfiac_local"
)
_PKG = "tfiac_standalone"


def _load_cli():
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(_COMPONENT_DIR)]
        sys.modules[_PKG] = pkg

    for name in ("const", "tfiac_client", "cli"):
        full = f"{_PKG}.{name}"
        if full in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(
            full, _COMPONENT_DIR / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{_PKG}.cli"]


if __name__ == "__main__":
    raise SystemExit(_load_cli().main())
