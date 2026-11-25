"""
Wildberries Parser SDK & Desktop GUI (`wb_parser`).

Modular Python SDK + CLI + Native MCP Server + CustomTkinter Desktop GUI
for Wildberries card inspection, dynamic basket-01..65+ routing, sharded
feedback collection (`feedbacks1` / `feedbacks2`), price tracking, and Excel export.
"""

from __future__ import annotations

__version__ = "2.1.0"

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
from wb_parser.export import rank_results_to_excel, to_csv, to_dataframe, to_excel, to_json, to_jsonl
from wb_parser.models import (
    Feedback,
    FeedbackInfo,
    Item,
    Items,
    PriceRecord,
    WBProduct,
    WBSearchPage,
)
from wb_parser.rank import RankResult, WBRankTracker
from wb_parser.reviews import ReviewItem, ReviewSummary, SmartReviewAnalyzer
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
from wb_parser.wallet import WBWalletCalculator, WalletPriceResult, WalletSettings

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
    "RankResult",
    "ReviewItem",
    "ReviewSummary",
    "SmartReviewAnalyzer",
    "TelegramNotifier",
    "WBAntiBotError",
    "WBClient",
    "WBConfig",
    "WBError",
    "WBNetworkError",
    "WBNotFoundError",
    "WBPriceTracker",
    "WBProduct",
    "WBRankTracker",
    "WBRateLimitError",
    "WBSearchPage",
    "WBValidationError",
    "WBWalletCalculator",
    "WalletPriceResult",
    "WalletSettings",
    "calculate_feedback_shard",
    "classify_target",
    "extract_nm_id",
    "extract_seller_id",
    "feedback_url",
    "filter_products",
    "rank_results_to_excel",
    "to_csv",
    "to_dataframe",
    "to_excel",
    "to_json",
    "to_jsonl",
]
