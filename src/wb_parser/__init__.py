"""
Wildberries SDK Pro (`wb_parser` / `wb-sdk-pro`).

Modular Python SDK, Async Client, CLI (`wb-parser` / `wb-sdk`), Native MCP Server (`wb-mcp`),
and optional 7-Tab CustomTkinter Desktop GUI (`wb-gui`) for:
- Direct `wbbasket.ru` CDN card extraction (`card.json`, `.webp` images, `basket-01..65+` upstreams)
- Sharded review extraction & analytics (`feedbacks1`/`feedbacks2` via `root_id % 100 >= 50`)
- Live WB Wallet & WB Club discount calculation (`WB Кошелёк` / `ВБ Клуб`)
- Multi-page Search Rank Tracking with SQLite history deltas
- Smart Review Analyzer (offline pros/cons/size-fit + optional OpenAI-compatible LLM)
- SQLite price-drop tracking, Telegram notifications, and Excel/CSV/JSON/JSONL/DataFrame exports

Supports CPython 3.8-3.16, PyPy 3.8-3.12, and Free-Threaded No-GIL (3.13t-3.16t).
"""

from __future__ import annotations

__version__ = "2.2.0"

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
