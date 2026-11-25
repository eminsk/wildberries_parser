"""
Wildberries Parser SDK & Desktop GUI (`wb_parser`).

Modular Python SDK + CLI + Native MCP Server + CustomTkinter Desktop GUI
for Wildberries card inspection, dynamic basket-01..65+ routing, sharded
feedback collection (`feedbacks1` / `feedbacks2`), price tracking, and Excel export.
"""

from __future__ import annotations

__version__ = "2.0.0"

from wb_parser.client import AsyncWBClient, ParseWB, WBClient, filter_products
from wb_parser.config import DEST_CODES, DEFAULT_DEST, WBConfig
from wb_parser.exceptions import (
    WBAntiBotError,
    WBError,
    WBNetworkError,
    WBNotFoundError,
    WBRateLimitError,
    WBValidationError,
)
from wb_parser.export import to_csv, to_dataframe, to_excel, to_json, to_jsonl
from wb_parser.models import (
    Feedback,
    FeedbackInfo,
    Item,
    Items,
    PriceRecord,
    WBProduct,
    WBSearchPage,
)
from wb_parser.shards import (
    DEFAULT_BASKET_RANGES,
    BasketRoute,
    BasketRouter,
    calculate_feedback_shard,
    classify_target,
    extract_nm_id,
    extract_seller_id,
    feedback_url,
)
from wb_parser.telegram import TelegramNotifier
from wb_parser.tracker import WBPriceTracker

__all__ = [
    "__version__",
    "AsyncWBClient",
    "BasketRoute",
    "BasketRouter",
    "DEFAULT_BASKET_RANGES",
    "DEFAULT_DEST",
    "DEST_CODES",
    "Feedback",
    "FeedbackInfo",
    "Item",
    "Items",
    "ParseWB",
    "PriceRecord",
    "TelegramNotifier",
    "WBAntiBotError",
    "WBClient",
    "WBConfig",
    "WBError",
    "WBNetworkError",
    "WBNotFoundError",
    "WBPriceTracker",
    "WBProduct",
    "WBRateLimitError",
    "WBSearchPage",
    "WBValidationError",
    "calculate_feedback_shard",
    "classify_target",
    "extract_nm_id",
    "extract_seller_id",
    "feedback_url",
    "filter_products",
    "to_csv",
    "to_dataframe",
    "to_excel",
    "to_json",
    "to_jsonl",
]
