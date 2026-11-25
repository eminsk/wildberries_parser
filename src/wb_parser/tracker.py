"""
SQLite Price Tracker for Wildberries products.

Stores price snapshots across runs, automatically populates `old_price`
on WBProduct instances when prices change, and exposes price drop queries.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from wb_parser.models import PriceRecord, WBProduct


class WBPriceTracker:
    """Thread-safe SQLite price history and drop detector."""

    def __init__(self, db_path: Union[str, Path] = "wb_prices.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wb_latest_prices (
                    nm_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    basic_price REAL NOT NULL DEFAULT 0,
                    old_price REAL,
                    discount INTEGER NOT NULL DEFAULT 0,
                    supplier_id INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wb_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nm_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    basic_price REAL NOT NULL DEFAULT 0,
                    discount INTEGER NOT NULL DEFAULT 0,
                    recorded_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_wb_hist_nm ON wb_price_history(nm_id)"
            )

    def track_products(self, products: List[WBProduct]) -> List[WBProduct]:
        """
        Update stored prices for a batch of products.
        Mutates `product.old_price` if a previous distinct price existed in the DB.
        Returns the list of products.
        """
        if not products:
            return products

        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for p in products:
                if p.price <= 0:
                    continue
                row = conn.execute(
                    "SELECT price, old_price FROM wb_latest_prices WHERE nm_id = ?",
                    (p.id,),
                ).fetchone()

                prev_price: Optional[float] = row["price"] if row else None
                recorded_old: Optional[float] = row["old_price"] if row else None

                if prev_price is not None and prev_price != p.price:
                    p.old_price = prev_price
                elif recorded_old is not None and recorded_old != p.price:
                    p.old_price = recorded_old

                conn.execute(
                    """
                    INSERT INTO wb_latest_prices (nm_id, name, price, basic_price, old_price, discount, supplier_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(nm_id) DO UPDATE SET
                        name = excluded.name,
                        old_price = CASE
                            WHEN wb_latest_prices.price != excluded.price THEN wb_latest_prices.price
                            ELSE wb_latest_prices.old_price
                        END,
                        price = excluded.price,
                        basic_price = excluded.basic_price,
                        discount = excluded.discount,
                        supplier_id = CASE
                            WHEN excluded.supplier_id > 0 THEN excluded.supplier_id
                            ELSE wb_latest_prices.supplier_id
                        END,
                        updated_at = excluded.updated_at
                    """,
                    (
                        p.id,
                        p.name,
                        p.price,
                        p.basic_price,
                        p.old_price,
                        p.discount,
                        p.supplier_id,
                        now,
                    ),
                )

                if prev_price is None or prev_price != p.price:
                    conn.execute(
                        """
                        INSERT INTO wb_price_history (nm_id, price, basic_price, discount, recorded_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (p.id, p.price, p.basic_price, p.discount, now),
                    )
        return products

    def get_price_drops(self, limit: int = 100) -> List[PriceRecord]:
        """Return tracked products whose current price is strictly below their previous `old_price`."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT nm_id, name, price, basic_price, old_price, discount, supplier_id, updated_at
                FROM wb_latest_prices
                WHERE old_price IS NOT NULL AND old_price > price AND price > 0
                ORDER BY (old_price - price) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            PriceRecord(
                nm_id=r["nm_id"],
                name=r["name"],
                price=r["price"],
                basic_price=r["basic_price"],
                old_price=r["old_price"],
                discount=r["discount"],
                supplier_id=r["supplier_id"],
                recorded_at=r["updated_at"],
            )
            for r in rows
        ]

    def get_history(self, nm_id: int) -> List[PriceRecord]:
        """Return chronological price snapshots for a given product article `nm_id`."""
        with self._connect() as conn:
            meta = conn.execute(
                "SELECT name, supplier_id FROM wb_latest_prices WHERE nm_id = ?",
                (nm_id,),
            ).fetchone()
            name = meta["name"] if meta else str(nm_id)
            supplier_id = meta["supplier_id"] if meta else 0

            rows = conn.execute(
                """
                SELECT price, basic_price, discount, recorded_at
                FROM wb_price_history
                WHERE nm_id = ?
                ORDER BY id ASC
                """,
                (nm_id,),
            ).fetchall()

        return [
            PriceRecord(
                nm_id=nm_id,
                name=name,
                price=r["price"],
                basic_price=r["basic_price"],
                discount=r["discount"],
                supplier_id=supplier_id,
                recorded_at=r["recorded_at"],
            )
            for r in rows
        ]
