"""
Backward-compatible root entrypoint for `Duff89/wildberries_parser`.
Allows running `python parser.py` or `from parser import ParseWB`.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wb_parser import AsyncWBClient, ParseWB, WBClient  # noqa: E402, F401

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.wildberries.ru/catalog/141217830/detail.aspx"
    out = sys.argv[2] if len(sys.argv) > 2 else "wb_data.xlsx"
    print(f"Fetching WB target via WB SDK Pro: {target} -> {out}")
    ParseWB(target, output_path=out).parse()
