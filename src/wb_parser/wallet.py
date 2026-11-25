"""
Wildberries Wallet Discount Pricing Engine (`WB Кошелёк` & `ВБ Клуб`).

Fetches live global payment discounts (`default-payment.json`) and display
thresholds (`settings-front.json`) from `static-basket-01.wbbasket.ru` with
automatic fallback to `mow-static-cdn.geobasket.ru`, and calculates exact
floored prices matching the Wildberries frontend.
"""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Optional

from wb_parser.http import SyncWBTransport

logger = logging.getLogger("wb_parser.wallet")

_DATACLASS_KW = {"frozen": True, "slots": True} if sys.version_info >= (3, 10) else {"frozen": True}

DEFAULT_PAYMENT_URLS = (
    "https://static-basket-01.wbbasket.ru/vol1/global-payment/default-payment.json",
    "https://mow-static-cdn.geobasket.ru/vol1/global-payment/default-payment.json",
)
SETTINGS_URLS = (
    "https://static-basket-01.wbbasket.ru/vol0/data/settings-front.json",
    "https://mow-static-cdn.geobasket.ru/vol0/data/settings-front.json",
)


@dataclass(**_DATACLASS_KW)
class WalletSettings:
    """Active WB Wallet discount percentages and display caps."""

    wallet_discount_pct: Decimal = Decimal("0")
    club_discount_pct: Decimal = Decimal("0")
    max_price: Decimal = Decimal("0")
    min_delta: Decimal = Decimal("0")
    is_active: bool = False


@dataclass(**_DATACLASS_KW)
class WalletPriceResult:
    """Calculated WB Wallet price breakdown for a single item price."""

    base_price: float
    wallet_price: float
    savings: float
    discount_pct: float
    applied: bool
    reason: str = ""


class WBWalletCalculator:
    """Calculates WB Wallet (`Незалогиненный кошелёк` / `ВБ Клуб`) discounted prices."""

    def __init__(self, transport: Optional[SyncWBTransport] = None) -> None:
        self._owns_transport = transport is None
        self.transport = transport or SyncWBTransport(timeout=8.0, max_retries=2)
        self._cache_lock = threading.RLock()
        self._cached_settings: Optional[WalletSettings] = None

    def close(self) -> None:
        if self._owns_transport:
            self.transport.close()

    def _fetch_first_ok(self, urls: tuple[str, ...]) -> Optional[dict[str, Any]]:
        for url in urls:
            try:
                data = self.transport.get_json(url)
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                logger.debug(f"Wallet config {url} failed: {exc}")
        return None

    def fetch_settings(self, *, force_refresh: bool = False) -> WalletSettings:
        """Fetch live discount rates and max price limits from WB CDN."""
        with self._cache_lock:
            if self._cached_settings is not None and not force_refresh:
                return self._cached_settings

        wallet_pct = Decimal("0")
        club_pct = Decimal("0")
        is_active = False

        payment_payload = self._fetch_first_ok(DEFAULT_PAYMENT_URLS)
        if payment_payload and payment_payload.get("state") == 0:
            for item in payment_payload.get("data", []):
                if not isinstance(item, dict) or item.get("is_active") is not True:
                    continue
                wc_type = str(item.get("wc_type") or "")
                try:
                    val = Decimal(str(item.get("discount_value", 0)))
                except Exception:
                    continue
                if wc_type == "Незалогиненный кошелёк":
                    wallet_pct = val
                    is_active = val > 0
                elif "Клуб" in wc_type:
                    club_pct = val

        max_price = Decimal("0")
        min_delta = Decimal("0")
        settings_payload = self._fetch_first_ok(SETTINGS_URLS)
        variables = (settings_payload or {}).get("variables")
        if isinstance(variables, dict):
            try:
                max_price = Decimal(str(variables.get("wlt1DiscountDisplayMaxPrice", 0)))
                min_delta = Decimal(str(variables.get("pricesDeltaToShowSale", 0)))
            except Exception:
                pass

        settings = WalletSettings(
            wallet_discount_pct=wallet_pct,
            club_discount_pct=club_pct,
            max_price=max_price,
            min_delta=min_delta,
            is_active=is_active,
        )
        with self._cache_lock:
            self._cached_settings = settings
        return settings

    def calculate(
        self,
        price: float | int | Decimal,
        *,
        use_club: bool = False,
        settings: Optional[WalletSettings] = None,
    ) -> WalletPriceResult:
        """Compute floored WB Wallet price respecting active percentage and max price cap."""
        dec_price = Decimal(str(price))
        if dec_price <= 0:
            return WalletPriceResult(0.0, 0.0, 0.0, 0.0, False, "zero_price")

        cfg = settings or self.fetch_settings()
        pct = cfg.club_discount_pct if (use_club and cfg.club_discount_pct > 0) else cfg.wallet_discount_pct
        if pct <= 0:
            return WalletPriceResult(float(dec_price), float(dec_price), 0.0, 0.0, False, "inactive")

        if cfg.max_price > 0 and dec_price > cfg.max_price:
            return WalletPriceResult(
                float(dec_price),
                float(dec_price),
                0.0,
                float(pct),
                False,
                f"above_max_price_{cfg.max_price}",
            )

        discounted = (dec_price * (Decimal("100") - pct) / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_FLOOR
        )
        savings = dec_price - discounted
        if cfg.min_delta > 0 and savings < cfg.min_delta:
            return WalletPriceResult(
                float(dec_price),
                float(dec_price),
                0.0,
                float(pct),
                False,
                f"below_min_delta_{cfg.min_delta}",
            )

        return WalletPriceResult(
            base_price=float(dec_price),
            wallet_price=float(discounted),
            savings=float(savings),
            discount_pct=float(pct),
            applied=True,
            reason="ok",
        )
