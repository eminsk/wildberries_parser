"""
Core Sync & Async Wildberries Clients + Backward-Compatible `ParseWB` Drop-in.

Combines:
1. Direct `wbbasket.ru` CDN (`card.json`, `price-history.json`, `upstreams`, `.webp` images)
   which works natively without WBAAS gateway challenges.
2. Sharded feedback endpoints (`feedbacks1.wb.ru` / `feedbacks2.wb.ru`) selected via
   `root_id % 100 >= 50`.
3. `__internal/u-search`, `__internal/u-card`, and `__internal/catalog/sellers` gateway
   queries with configurable proxies, cookies, `x-wbaas-token`, and fallbacks.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from wb_parser.config import DEFAULT_DEST, UPSTREAMS_URL
from wb_parser.exceptions import (
    WBAntiBotError,
    WBNetworkError,
    WBNotFoundError,
    WBValidationError,
)
from wb_parser.export import to_csv, to_excel
from wb_parser.http import AsyncWBTransport, SyncWBTransport
from wb_parser.models import FeedbackInfo, WBProduct
from wb_parser.shards import (
    BasketRouter,
    calculate_feedback_shard,
    classify_target,
    extract_nm_id,
    extract_seller_id,
    feedback_url,
)
from wb_parser.tracker import WBPriceTracker
from wb_parser.wallet import WBWalletCalculator, WalletPriceResult

logger = logging.getLogger("wb_parser.client")

SEARCH_ENDPOINTS = (
    "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search",
    "https://www.wildberries.ru/__internal/u-search/exactmatch/sng/common/v18/search",
    "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v13/search",
    "https://search.wb.ru/exactmatch/ru/common/v4/search",
)

CARD_DETAIL_ENDPOINTS = (
    "https://www.wildberries.ru/__internal/u-card/cards/v4/detail",
    "https://www.wildberries.ru/__internal/u-card/cards/v2/detail",
    "https://card.wb.ru/cards/v2/detail",
)

SELLER_CATALOG_ENDPOINTS = (
    "https://www.wildberries.ru/__internal/catalog/sellers/v4/catalog",
    "https://catalog.wb.ru/sellers/v2/catalog",
    "https://catalog.wb.ru/sellers/catalog",
)


def _extract_products_list(payload: Any) -> List[Dict[str, Any]]:
    """Extract raw product dicts from either v18 top-level or legacy `data.products` JSON."""
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("products"), list):
        return payload["products"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("products"), list):
        return data["products"]
    return []


def _enrich_product_urls(router: BasketRouter, product: WBProduct, lang: str = "ru") -> WBProduct:
    """Populate `.webp` image links, card JSON URL, and feedback shard on a product."""
    if product.id > 0:
        if not product.url:
            product.url = f"https://www.wildberries.ru/catalog/{product.id}/detail.aspx"
        if not product.card_json_url:
            product.card_json_url = router.card_json_url(product.id, lang=lang)
        if product.pics > 0 and not product.image_links:
            product.image_links = router.image_urls(product.id, product.pics, size="big", ext="webp")
    if product.root > 0 and product.feedback_shard is None:
        product.feedback_shard = calculate_feedback_shard(product.root)
    return product


def _merge_cdn_into_product(router: BasketRouter, product: WBProduct, cdn_data: Dict[str, Any], lang: str = "ru") -> WBProduct:
    """Merge rich fields from CDN `card.json` onto an existing `WBProduct`."""
    cdn_item = WBProduct.model_validate(cdn_data)
    if not product.name and cdn_item.name:
        product.name = cdn_item.name
    if not product.brand and cdn_item.brand:
        product.brand = cdn_item.brand
    if not product.supplier_id and cdn_item.supplier_id:
        product.supplier_id = cdn_item.supplier_id
    if not product.subject and cdn_item.subject:
        product.subject = cdn_item.subject
    if not product.subject_id and cdn_item.subject_id:
        product.subject_id = cdn_item.subject_id
    if not product.vendor_code and cdn_item.vendor_code:
        product.vendor_code = cdn_item.vendor_code
    if cdn_item.description:
        product.description = cdn_item.description
    if cdn_item.specs:
        product.specs = cdn_item.specs
    if cdn_item.color_ids:
        product.color_ids = cdn_item.color_ids
    if cdn_item.root and not product.root:
        product.root = cdn_item.root
    if cdn_item.pics and cdn_item.pics > product.pics:
        product.pics = cdn_item.pics
        product.image_links = router.image_urls(product.id, product.pics, size="big", ext="webp")
    return _enrich_product_urls(router, product, lang=lang)


def _apply_feedback_to_product(product: WBProduct, fb: Optional[FeedbackInfo]) -> WBProduct:
    """Attach feedback summary onto a `WBProduct`."""
    if fb is None:
        return product
    product.feedback_count = fb.feedback_count
    product.valuation = fb.valuation
    product.feedback_shard = fb.shard
    if product.rating <= 0 and fb.valuation_float > 0:
        product.rating = fb.valuation_float
    if product.review_rating <= 0 and fb.valuation_float > 0:
        product.review_rating = fb.valuation_float
    return product


def filter_products(
    products: Iterable[WBProduct],
    *,
    min_price: int = 0,
    max_price: int = 999_999_999,
    min_discount: int = 0,
    min_rating: float = 0.0,
    white_keywords: Sequence[str] = (),
    black_keywords: Sequence[str] = (),
) -> List[WBProduct]:
    """Filter parsed products by price range, discount %, minimum rating, and keywords."""
    whites = [w.strip().lower() for w in white_keywords if w.strip()]
    blacks = [b.strip().lower() for b in black_keywords if b.strip()]

    matched: List[WBProduct] = []
    for p in products:
        if p.price > 0:
            if p.price < min_price or p.price > max_price:
                continue
        if min_discount > 0 and p.discount < min_discount:
            continue
        effective_rating = max(p.rating, p.review_rating)
        if min_rating > 0 and effective_rating < min_rating:
            continue

        haystack = f"{p.name} {p.brand} {p.subject} {p.description}".lower()
        if whites and not any(w in haystack for w in whites):
            continue
        if blacks and any(b in haystack for b in blacks):
            continue

        matched.append(p)
    return matched


class WBClient:
    """Synchronous high-level Wildberries SDK client."""

    def __init__(
        self,
        *,
        dest: int = DEFAULT_DEST,
        currency: str = "rub",
        lang: str = "ru",
        proxy: Optional[str] = None,
        proxy_change_url: Optional[str] = None,
        cookies: Optional[str] = None,
        wbaas_token: Optional[str] = None,
        timeout: float = 12.0,
        max_retries: int = 3,
        force_ipv4: bool = True,
        tracker_db: Optional[Union[str, Path]] = None,
        auto_sync_upstreams: bool = False,
        transport: Optional[SyncWBTransport] = None,
    ) -> None:
        self.dest = int(dest)
        self.currency = currency
        self.lang = lang
        self.router = BasketRouter()
        self.transport = transport or SyncWBTransport(
            proxy=proxy,
            proxy_change_url=proxy_change_url,
            cookies=cookies,
            wbaas_token=wbaas_token,
            timeout=timeout,
            max_retries=max_retries,
            force_ipv4=force_ipv4,
        )
        self.tracker = WBPriceTracker(tracker_db) if tracker_db else None
        self.wallet = WBWalletCalculator(transport=self.transport)
        self._tracker_db_path = str(tracker_db) if tracker_db else "wb_prices.db"
        self._upstreams_synced = False
        if auto_sync_upstreams:
            try:
                self.sync_upstreams()
            except Exception as exc:
                logger.warning(f"Auto upstream route sync skipped: {exc}")

    def __enter__(self) -> "WBClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close underlying HTTP client resources."""
        self.transport.close()

    def ping(self) -> Dict[str, Any]:
        """Verify live CDN reachability and measure latency."""
        return self.transport.ping(UPSTREAMS_URL)

    def sync_upstreams(self) -> int:
        """Fetch live shard routes from `cdn.wbbasket.ru/api/v3/upstreams` and update router."""
        payload = self.transport.get_json(UPSTREAMS_URL)
        count = self.router.update_from_upstreams(payload)
        self._upstreams_synced = count > 0
        logger.info(f"Synchronized {count} live WB basket routes from cdn.wbbasket.ru")
        return count

    def _ensure_upstreams(self) -> None:
        if not self._upstreams_synced:
            try:
                self.sync_upstreams()
            except Exception as exc:
                logger.debug(f"Using built-in basket routes (upstream sync unavailable: {exc})")
                self._upstreams_synced = True

    def get_card_cdn(self, nm_id: int) -> WBProduct:
        """
        Fetch full product card directly from `basket-XX.wbbasket.ru/.../card.json`.
        Works reliably without WBAAS tokens or cookies.
        """
        self._ensure_upstreams()
        url = self.router.card_json_url(nm_id, lang=self.lang)
        data = self.transport.get_json(url)
        product = WBProduct.model_validate(data)
        return _enrich_product_urls(self.router, product, lang=self.lang)

    def get_price_history(self, nm_id: int) -> List[Dict[str, Any]]:
        """Fetch historical prices from CDN `price-history.json`, returning `[]` if absent (404)."""
        url = self.router.price_history_url(nm_id)
        try:
            data = self.transport.get_json(url)
            return data if isinstance(data, list) else []
        except WBNotFoundError:
            return []

    def get_feedbacks(
        self,
        root_id: int,
        *,
        version: int = 1,
        fallback_alternate_shard: bool = True,
    ) -> Optional[FeedbackInfo]:
        """
        Fetch product reviews & rating from `feedbacks1.wb.ru` or `feedbacks2.wb.ru`
        using exact shard routing (`root_id % 100 >= 50 -> feedbacks2`).
        """
        primary_shard = calculate_feedback_shard(root_id)
        shards = [primary_shard]
        if fallback_alternate_shard:
            shards.append(2 if primary_shard == 1 else 1)

        for shard in shards:
            url = feedback_url(root_id, version=version, shard=shard)
            try:
                data = self.transport.get_json(url)
                if isinstance(data, dict):
                    return FeedbackInfo.model_validate(
                        {**data, "root_id": root_id, "shard": shard}
                    )
            except (WBNotFoundError, WBNetworkError):
                continue
        return None

    def _get_json_with_fallbacks(
        self,
        urls: Sequence[str],
        params: Dict[str, Any],
    ) -> Any:
        last_err: Optional[Exception] = None
        for url in urls:
            try:
                return self.transport.get_json(url, params=params)
            except WBAntiBotError as exc:
                last_err = exc
                if "__internal" in url:
                    raise
                logger.debug(f"Endpoint {url} returned WBAAS block: {exc}")
            except (WBNetworkError, WBNotFoundError) as exc:
                last_err = exc
                logger.debug(f"Endpoint {url} returned error: {exc}")
                continue
        if last_err is not None:
            raise last_err
        raise WBNetworkError("No endpoints available")

    def get_card_details(self, nm_ids: Union[int, Sequence[int]]) -> List[WBProduct]:
        """
        Fetch live prices, discounts, stock volume, and ratings via `u-card` detail endpoints.
        """
        ids = [nm_ids] if isinstance(nm_ids, int) else list(nm_ids)
        if not ids:
            return []

        params = {
            "appType": 1,
            "curr": self.currency,
            "dest": self.dest,
            "spp": 30,
            "nm": ";".join(str(i) for i in ids),
        }
        payload = self._get_json_with_fallbacks(CARD_DETAIL_ENDPOINTS, params=params)
        raw_items = _extract_products_list(payload)
        products = [_enrich_product_urls(self.router, WBProduct.model_validate(r), lang=self.lang) for r in raw_items]
        if self.tracker and products:
            self.tracker.track_products(products)
        return products

    def get_product(
        self,
        url_or_id: Union[str, int],
        *,
        enrich_cdn: bool = True,
        with_feedbacks: bool = True,
        with_price_history: bool = False,
    ) -> WBProduct:
        """
        Smart unified single-product fetcher.

        Combines live prices from `u-card` (if accessible without WBAAS block) with direct CDN
        `card.json` metadata (`description`, `specs`, `root`, `supplier_id`, `.webp` images)
        and sharded feedback stats (`feedbacks1/2.wb.ru`).
        """
        nm_id = extract_nm_id(url_or_id)
        product: Optional[WBProduct] = None

        # 1. Try live u-card price/stock first (may raise WBAntiBotError if without RU proxy/cookies)
        try:
            details = self.get_card_details([nm_id])
            if details:
                product = details[0]
        except (WBAntiBotError, WBNetworkError) as exc:
            logger.info(f"u-card detail unavailable ({exc}); falling back to direct wbbasket CDN for nm={nm_id}")

        # 2. Fetch rich CDN card.json (always accessible without WBAAS)
        if enrich_cdn or product is None:
            cdn_product = self.get_card_cdn(nm_id)
            if product is None:
                product = cdn_product
            else:
                product = _merge_cdn_into_product(self.router, product, cdn_product.model_dump(), lang=self.lang)

        # 3. Sharded feedbacks using root_id (imt_id)
        if with_feedbacks and product.root > 0:
            fb = self.get_feedbacks(product.root)
            _apply_feedback_to_product(product, fb)

        # 4. Price history from CDN
        if with_price_history:
            product.price_history = self.get_price_history(nm_id)

        self._attach_wallet_price(product)
        if self.tracker and product.price > 0:
            self.tracker.track_products([product])
        return product

    def _attach_wallet_price(self, product: WBProduct) -> WBProduct:
        """Compute WB Wallet discounted price when base price > 0."""
        if product.price <= 0:
            return product
        try:
            res = self.wallet.calculate(product.price)
            if res.applied:
                product.wallet_price = res.wallet_price
                product.wallet_discount_pct = res.discount_pct
        except Exception as exc:
            logger.debug(f"Wallet discount skipped for nm={product.id}: {exc}")
        return product

    def wallet_price(self, price: float, *, use_club: bool = False) -> WalletPriceResult:
        """Calculate discounted price with WB Wallet (`WB Кошелёк` / `ВБ Клуб`)."""
        return self.wallet.calculate(price, use_club=use_club)

    def check_rank(
        self,
        nm_id_or_url: Union[int, str],
        query: str,
        *,
        max_pages: int = 3,
        sort: str = "popular",
    ):
        """Find product search position across `1..max_pages` pages and store history in SQLite."""
        from wb_parser.rank import WBRankTracker
        tracker = WBRankTracker(self, db_path=self._tracker_db_path)
        return tracker.check_rank(nm_id_or_url, query, max_pages=max_pages, sort=sort)

    def analyze_reviews(
        self,
        url_or_nm_id: Union[str, int],
        *,
        only_this_color: bool = True,
        limit: int = 100,
        ai_key: Optional[str] = None,
        ai_base_url: str = "https://api.openai.com/v1",
        ai_model: str = "gpt-4o-mini",
    ):
        """Extract buyer reviews via CDN + feedbacks1/2 and generate pros/cons/size summary."""
        from wb_parser.reviews import SmartReviewAnalyzer
        analyzer = SmartReviewAnalyzer(self)
        summary = analyzer.fetch_reviews(url_or_nm_id, only_this_color=only_this_color, limit=limit)
        if ai_key:
            summary = analyzer.summarize_with_llm(
                summary, api_key=ai_key, base_url=ai_base_url, model=ai_model
            )
        return summary

    def _paginate_catalog(
        self,
        endpoints: Sequence[str],
        base_params: Dict[str, Any],
        *,
        max_pages: int,
        limit: int,
        enrich_cdn: bool,
        with_feedbacks: bool,
    ) -> List[WBProduct]:
        """Paginate through a search or seller catalog endpoint with deduplication."""
        self._ensure_upstreams()
        results: List[WBProduct] = []
        seen: set[int] = set()

        for page in range(1, max(1, max_pages) + 1):
            params = {**base_params, "page": page}
            payload = self._get_json_with_fallbacks(endpoints, params=params)
            raw_items = _extract_products_list(payload)
            if not raw_items:
                break

            added_on_page = 0
            for raw in raw_items:
                prod = _enrich_product_urls(self.router, WBProduct.model_validate(raw), lang=self.lang)
                if prod.id in seen:
                    continue
                seen.add(prod.id)
                if enrich_cdn:
                    try:
                        cdn = self.get_card_cdn(prod.id)
                        _merge_cdn_into_product(self.router, prod, cdn.model_dump(), lang=self.lang)
                    except Exception:
                        pass
                if with_feedbacks and prod.root > 0:
                    _apply_feedback_to_product(prod, self.get_feedbacks(prod.root))
                self._attach_wallet_price(prod)
                results.append(prod)
                added_on_page += 1
                if len(results) >= limit:
                    break
            if len(results) >= limit or added_on_page == 0:
                break

        if self.tracker and results:
            self.tracker.track_products(results)
        return results

    def fetch_search_page(
        self,
        query: str,
        *,
        page: int = 1,
        sort: str = "popular",
    ) -> List[WBProduct]:
        """Fetch a single search result page with enriched CDN/wallet metadata."""
        self._ensure_upstreams()
        params = {
            "appType": 1,
            "curr": self.currency,
            "dest": self.dest,
            "lang": self.lang,
            "query": query,
            "resultset": "catalog",
            "sort": sort,
            "spp": 30,
            "page": page,
        }
        payload = self._get_json_with_fallbacks(SEARCH_ENDPOINTS, params=params)
        raw_items = _extract_products_list(payload)
        items: List[WBProduct] = []
        for raw in raw_items:
            prod = _enrich_product_urls(self.router, WBProduct.model_validate(raw), lang=self.lang)
            self._attach_wallet_price(prod)
            items.append(prod)
        return items

    def search(
        self,
        query: str,
        *,
        max_pages: int = 3,
        limit: int = 100,
        sort: str = "popular",
        enrich_cdn: bool = False,
        with_feedbacks: bool = False,
    ) -> List[WBProduct]:
        """Search Wildberries catalog by keyword query."""
        params = {
            "appType": 1,
            "curr": self.currency,
            "dest": self.dest,
            "lang": self.lang,
            "query": query,
            "resultset": "catalog",
            "sort": sort,
            "spp": 30,
        }
        return self._paginate_catalog(
            SEARCH_ENDPOINTS,
            params,
            max_pages=max_pages,
            limit=limit,
            enrich_cdn=enrich_cdn,
            with_feedbacks=with_feedbacks,
        )

    def resolve_seller_id(self, url_or_id: Union[str, int]) -> int:
        """
        Resolve seller `supplier_id` from a seller URL (`/seller/123`), integer ID,
        or a Wildberries product URL (`/catalog/141217830/detail.aspx` -> CDN `selling.supplier_id`).
        """
        seller = extract_seller_id(url_or_id)
        if seller is not None:
            return seller
        nm_id = extract_nm_id(url_or_id)
        cdn = self.get_card_cdn(nm_id)
        if cdn.supplier_id > 0:
            return cdn.supplier_id
        details = self.get_card_details([nm_id])
        if details and details[0].supplier_id > 0:
            return details[0].supplier_id
        raise WBValidationError(f"Could not determine supplier_id for {url_or_id!r}")

    def get_seller_catalog(
        self,
        url_or_seller_id: Union[str, int],
        *,
        max_pages: int = 10,
        limit: int = 1000,
        sort: str = "popular",
        enrich_cdn: bool = False,
        with_feedbacks: bool = True,
    ) -> List[WBProduct]:
        """Parse all products belonging to a single Wildberries seller."""
        supplier_id = self.resolve_seller_id(url_or_seller_id)
        params = {
            "appType": 1,
            "curr": self.currency,
            "dest": self.dest,
            "supplier": supplier_id,
            "sort": sort,
            "spp": 30,
        }
        return self._paginate_catalog(
            SELLER_CATALOG_ENDPOINTS,
            params,
            max_pages=max_pages,
            limit=limit,
            enrich_cdn=enrich_cdn,
            with_feedbacks=with_feedbacks,
        )

    def scrape_targets(
        self,
        targets: Sequence[str],
        *,
        max_pages: int = 2,
        limit_per_target: int = 100,
        enrich_cdn: bool = True,
        with_feedbacks: bool = True,
    ) -> List[WBProduct]:
        """
        Dispatch mixed list of WB product URLs, article numbers (`nm_id`), seller links,
        or search queries into unified deduplicated `WBProduct` records.
        """
        seen_ids: set[int] = set()
        collected: List[WBProduct] = []

        for raw_target in targets:
            target = raw_target.strip()
            if not target:
                continue
            kind, value = classify_target(target)
            if kind == "product":
                batch = [self.get_product(int(value), enrich_cdn=enrich_cdn, with_feedbacks=with_feedbacks)]
            elif kind == "seller":
                batch = self.get_seller_catalog(
                    int(value),
                    max_pages=max_pages,
                    limit=limit_per_target,
                    enrich_cdn=enrich_cdn,
                    with_feedbacks=with_feedbacks,
                )
            else:
                batch = self.search(
                    value,
                    max_pages=max_pages,
                    limit=limit_per_target,
                    enrich_cdn=enrich_cdn,
                    with_feedbacks=with_feedbacks,
                )

            for item in batch:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    collected.append(item)
        return collected


class AsyncWBClient:
    """Asynchronous high-throughput Wildberries SDK client."""

    def __init__(
        self,
        *,
        dest: int = DEFAULT_DEST,
        currency: str = "rub",
        lang: str = "ru",
        proxy: Optional[str] = None,
        proxy_change_url: Optional[str] = None,
        cookies: Optional[str] = None,
        wbaas_token: Optional[str] = None,
        timeout: float = 12.0,
        max_retries: int = 3,
        force_ipv4: bool = True,
        concurrency: int = 16,
        tracker_db: Optional[Union[str, Path]] = None,
        transport: Optional[AsyncWBTransport] = None,
    ) -> None:
        self.dest = int(dest)
        self.currency = currency
        self.lang = lang
        self.router = BasketRouter()
        self.transport = transport or AsyncWBTransport(
            proxy=proxy,
            proxy_change_url=proxy_change_url,
            cookies=cookies,
            wbaas_token=wbaas_token,
            timeout=timeout,
            max_retries=max_retries,
            force_ipv4=force_ipv4,
        )
        self._sem = asyncio.Semaphore(max(1, int(concurrency)))
        self.tracker = WBPriceTracker(tracker_db) if tracker_db else None
        self.wallet = WBWalletCalculator(transport=self.transport)
        self._tracker_db_path = str(tracker_db) if tracker_db else "wb_prices.db"
        self._upstreams_synced = False

    async def __aenter__(self) -> "AsyncWBClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self.transport.close()

    async def sync_upstreams(self) -> int:
        payload = await self.transport.get_json(UPSTREAMS_URL)
        count = self.router.update_from_upstreams(payload)
        self._upstreams_synced = count > 0
        return count

    async def _ensure_upstreams(self) -> None:
        if not self._upstreams_synced:
            try:
                await self.sync_upstreams()
            except Exception:
                self._upstreams_synced = True

    async def get_card_cdn(self, nm_id: int) -> WBProduct:
        await self._ensure_upstreams()
        async with self._sem:
            url = self.router.card_json_url(nm_id, lang=self.lang)
            data = await self.transport.get_json(url)
            product = WBProduct.model_validate(data)
            return _enrich_product_urls(self.router, product, lang=self.lang)

    async def get_feedbacks(self, root_id: int, *, version: int = 1) -> Optional[FeedbackInfo]:
        primary = calculate_feedback_shard(root_id)
        for shard in (primary, 2 if primary == 1 else 1):
            async with self._sem:
                url = feedback_url(root_id, version=version, shard=shard)
                try:
                    data = await self.transport.get_json(url)
                    if isinstance(data, dict):
                        return FeedbackInfo.model_validate(
                            {**data, "root_id": root_id, "shard": shard}
                        )
                except (WBNotFoundError, WBNetworkError):
                    continue
        return None

    async def get_product(
        self,
        url_or_id: Union[str, int],
        *,
        with_feedbacks: bool = True,
    ) -> WBProduct:
        nm_id = extract_nm_id(url_or_id)
        product = await self.get_card_cdn(nm_id)
        if with_feedbacks and product.root > 0:
            fb = await self.get_feedbacks(product.root)
            _apply_feedback_to_product(product, fb)
        return product

    async def gather_cards(
        self,
        nm_ids: Sequence[int],
        *,
        with_feedbacks: bool = True,
    ) -> List[WBProduct]:
        """Concurrently fetch multiple product CDN cards and sharded reviews."""
        await self._ensure_upstreams()
        tasks = [self.get_product(nm_id, with_feedbacks=with_feedbacks) for nm_id in nm_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        products = [r for r in results if isinstance(r, WBProduct)]
        if self.tracker and products:
            self.tracker.track_products(products)
        return products


class ParseWB:
    """
    Backward-compatible drop-in replacement for Duff89's original `ParseWB` class.

    Fixes:
    - Correct `feedbacks1` vs `feedbacks2` routing (`root % 100 >= 50`).
    - Dynamic `basket-01..65+` shard ranges and `.webp` CDN image URLs.
    - Dual support for Excel (`.xlsx`) and CSV output.
    """

    def __init__(
        self,
        url: str,
        output_path: str = "wb_data.csv",
        *,
        proxy: Optional[str] = None,
        cookies: Optional[str] = None,
        wbaas_token: Optional[str] = None,
    ) -> None:
        self.url = url
        self.output_path = output_path
        self.client = WBClient(proxy=proxy, cookies=cookies, wbaas_token=wbaas_token)
        self.seller_id: Optional[int] = None

    def parse(self) -> List[WBProduct]:
        """Run seller catalog scrape and write CSV or Excel report to `self.output_path`."""
        with self.client as client:
            self.seller_id = client.resolve_seller_id(self.url)
            products = client.get_seller_catalog(self.seller_id, with_feedbacks=True)
            out = Path(self.output_path)
            if out.suffix.lower() == ".xlsx":
                to_excel(products, out)
            else:
                to_csv(products, out)
            return products
