"""
Wildberries Search Position (Rank) Tracker (`wb_rank` integration).

Scans search result pages (`1..max_pages`), locates target `nm_id` position
(global rank across pages + per-page slot), computes WB Wallet pricing, and stores
historical rank trajectories in SQLite to track climbs/drops (`rank_delta`).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple, Union

from wb_parser._model import BaseModel, Field

from wb_parser.shards import extract_nm_id

if TYPE_CHECKING:
    from wb_parser.client import WBClient

logger = logging.getLogger("wb_parser.rank")


class RankResult(BaseModel):
    """Single keyword rank check snapshot for a Wildberries product."""

    nm_id: int
    query: str
    position: Optional[int] = None
    page: Optional[int] = None
    page_position: Optional[int] = None
    previous_position: Optional[int] = None
    rank_delta: Optional[int] = None
    title: str = ""
    brand: str = ""
    price: float = 0.0
    wallet_price: Optional[float] = None
    total_scanned: int = 0
    checked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class WBRankTracker:
    """Multi-page Wildberries search rank checker with SQLite position history."""

    def __init__(
        self,
        client: "WBClient",
        *,
        db_path: Union[str, Path] = "wb_prices.db",
    ) -> None:
        self.client = client
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wb_rank_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nm_id INTEGER NOT NULL,
                        query TEXT NOT NULL,
                        position INTEGER,
                        page INTEGER,
                        price REAL NOT NULL DEFAULT 0,
                        checked_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_wb_rank_nm_q ON wb_rank_history(nm_id, query)"
                )

    def _get_previous_position(self, nm_id: int, query: str) -> Optional[int]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT position FROM wb_rank_history
                    WHERE nm_id = ? AND query = ? AND position IS NOT NULL
                    ORDER BY id DESC LIMIT 1
                    """,
                    (nm_id, query),
                ).fetchone()
                return int(row["position"]) if row else None

    def _record_rank(self, res: RankResult) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO wb_rank_history (nm_id, query, position, page, price, checked_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (res.nm_id, res.query, res.position, res.page, res.price, res.checked_at),
                )

    def check_rank(
        self,
        nm_id_or_url: Union[int, str],
        query: str,
        *,
        max_pages: int = 3,
        sort: str = "popular",
    ) -> RankResult:
        """
        Search up to `max_pages` (typically 100 items/page -> Top 300+) for `nm_id` under `query`.
        Computes global rank, delta vs previous check, and logs snapshot to SQLite.
        """
        nm_id = extract_nm_id(nm_id_or_url)
        clean_query = query.strip()
        prev_pos = self._get_previous_position(nm_id, clean_query)

        scanned = 0
        for page in range(1, max(1, max_pages) + 1):
            page_items = self.client.fetch_search_page(clean_query, page=page, sort=sort)
            if not page_items:
                break

            for idx, item in enumerate(page_items, start=1):
                global_pos = scanned + idx
                if item.id == nm_id:
                    # Positive delta means climbed higher in search (e.g. prev=20, now=5 -> +15)
                    delta = (prev_pos - global_pos) if prev_pos is not None else None
                    res = RankResult(
                        nm_id=nm_id,
                        query=clean_query,
                        position=global_pos,
                        page=page,
                        page_position=idx,
                        previous_position=prev_pos,
                        rank_delta=delta,
                        title=item.name,
                        brand=item.brand,
                        price=item.price,
                        wallet_price=item.wallet_price,
                        total_scanned=scanned + len(page_items),
                    )
                    self._record_rank(res)
                    return res

            scanned += len(page_items)

        res = RankResult(
            nm_id=nm_id,
            query=clean_query,
            position=None,
            previous_position=prev_pos,
            rank_delta=None,
            total_scanned=scanned,
        )
        self._record_rank(res)
        return res

    def check_batch(
        self,
        pairs: Sequence[Tuple[Union[int, str], str]],
        *,
        max_pages: int = 3,
        sort: str = "popular",
    ) -> List[RankResult]:
        """Run rank checks across a batch of `(nm_id, query)` pairs."""
        results: List[RankResult] = []
        for nm_id, query in pairs:
            if not query.strip():
                continue
            results.append(self.check_rank(nm_id, query, max_pages=max_pages, sort=sort))
        return results

    def get_history(self, nm_id: int, query: Optional[str] = None, limit: int = 50) -> List[RankResult]:
        """Retrieve historical rank checks from SQLite."""
        with self._lock:
            with self._connect() as conn:
                if query:
                    rows = conn.execute(
                        "SELECT * FROM wb_rank_history WHERE nm_id = ? AND query = ? ORDER BY id DESC LIMIT ?",
                        (nm_id, query, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM wb_rank_history WHERE nm_id = ? ORDER BY id DESC LIMIT ?",
                        (nm_id, limit),
                    ).fetchall()

        return [
            RankResult(
                nm_id=r["nm_id"],
                query=r["query"],
                position=r["position"],
                page=r["page"],
                price=r["price"],
                checked_at=r["checked_at"],
            )
            for r in rows
        ]
