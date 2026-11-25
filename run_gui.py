"""
One-click launcher for WB SDK Pro Desktop GUI.
Usage: uv run python run_gui.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wb_parser.gui import main_gui  # noqa: E402

if __name__ == "__main__":
    sys.exit(main_gui())
