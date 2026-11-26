#!/usr/bin/env python3
"""
One-click launcher for WB SDK Pro Desktop GUI (`wb-gui`).
Can be executed directly: `uv run python run_gui.py`
Or frozen into standalone `WBSDK_Pro.exe` with PyInstaller.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Prevent crashes in PyInstaller windowed mode (console=False sets stdout/stderr to None)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure bundled CA certificates work reliably inside PyInstaller frozen bundles
try:
    import certifi

    _ca = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", _ca)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca)
    os.environ.setdefault("CURL_CA_BUNDLE", _ca)
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from wb_parser import __version__ as _app_version
except Exception:
    _app_version = "2.4.0"

if sys.platform.startswith("win"):
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"eminsk.wbsdkpro.desktop.{_app_version}"
        )
    except Exception:
        pass

from wb_parser.gui import main_gui  # noqa: E402

if __name__ == "__main__":
    sys.exit(main_gui())
