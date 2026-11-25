"""
Desktop GUI entry point for Wildberries SDK Pro.
"""

from __future__ import annotations

import sys
from typing import Optional


def main_gui(argv: Optional[list[str]] = None) -> int:
    """Launch the CustomTkinter WB SDK Pro Desktop application."""
    from wb_parser.gui.app import WBGUIApp

    app = WBGUIApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main_gui())
