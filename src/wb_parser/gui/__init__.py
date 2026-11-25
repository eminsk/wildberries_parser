"""
Desktop GUI entry point for Wildberries SDK Pro.
"""

from __future__ import annotations

import sys
from typing import List, Optional


def main_gui(argv: Optional[List[str]] = None) -> int:
    """Launch the CustomTkinter WB SDK Pro Desktop application."""
    from wb_parser.gui.app import WBGUIApp

    try:
        app = WBGUIApp()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main_gui())
