"""
Backward-compatible model exports matching original `models.py`.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wb_parser.models import (  # noqa: E402, F401
    Feedback,
    FeedbackInfo,
    Item,
    Items,
    PriceRecord,
    WBProduct,
    WBSearchPage,
)
