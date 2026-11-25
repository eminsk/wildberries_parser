"""
Wildberries CDN Basket & Feedback Shard Routing Engine.

Includes:
- Dynamic route map synchronization from `https://cdn.wbbasket.ru/api/v3/upstreams`.
- Built-in fallback table covering baskets `01` through `65` (volumes 0 .. 28,805; articles > 2.88 billion)
  plus mathematical extrapolation beyond `28,805`.
- Exact feedback shard calculation (`feedbacks1` vs `feedbacks2`) using `root_id % 100 >= 50`.
- Strict `.webp` / `.jpg` image & `card.json` / `price-history.json` URL generators.
- Flexible URL / ID extractors for product pages, seller stores, and search links.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from wb_parser.exceptions import WBValidationError


@dataclass(frozen=True, slots=True)
class BasketRoute:
    """Volume partition mapping `[vol_from, vol_to]` to a CDN basket host."""

    vol_from: int
    vol_to: int
    host: str


# Live snapshot verified against https://cdn.wbbasket.ru/api/v3/upstreams (`origin.mediabasket_route_map`)
DEFAULT_BASKET_RANGES: Tuple[Tuple[int, int, str], ...] = (
    (0, 143, "basket-01.wbbasket.ru"),
    (144, 287, "basket-02.wbbasket.ru"),
    (288, 431, "basket-03.wbbasket.ru"),
    (432, 719, "basket-04.wbbasket.ru"),
    (720, 1007, "basket-05.wbbasket.ru"),
    (1008, 1061, "basket-06.wbbasket.ru"),
    (1062, 1115, "basket-07.wbbasket.ru"),
    (1116, 1169, "basket-08.wbbasket.ru"),
    (1170, 1313, "basket-09.wbbasket.ru"),
    (1314, 1601, "basket-10.wbbasket.ru"),
    (1602, 1655, "basket-11.wbbasket.ru"),
    (1656, 1919, "basket-12.wbbasket.ru"),
    (1920, 2045, "basket-13.wbbasket.ru"),
    (2046, 2189, "basket-14.wbbasket.ru"),
    (2190, 2405, "basket-15.wbbasket.ru"),
    (2406, 2621, "basket-16.wbbasket.ru"),
    (2622, 2837, "basket-17.wbbasket.ru"),
    (2838, 3053, "basket-18.wbbasket.ru"),
    (3054, 3269, "basket-19.wbbasket.ru"),
    (3270, 3485, "basket-20.wbbasket.ru"),
    (3486, 3701, "basket-21.wbbasket.ru"),
    (3702, 3917, "basket-22.wbbasket.ru"),
    (3918, 4133, "basket-23.wbbasket.ru"),
    (4134, 4349, "basket-24.wbbasket.ru"),
    (4350, 4565, "basket-25.wbbasket.ru"),
    (4566, 4877, "basket-26.wbbasket.ru"),
    (4878, 5189, "basket-27.wbbasket.ru"),
    (5190, 5501, "basket-28.wbbasket.ru"),
    (5502, 5813, "basket-29.wbbasket.ru"),
    (5814, 6125, "basket-30.wbbasket.ru"),
    (6126, 6437, "basket-31.wbbasket.ru"),
    (6438, 6749, "basket-32.wbbasket.ru"),
    (6750, 7061, "basket-33.wbbasket.ru"),
    (7062, 7373, "basket-34.wbbasket.ru"),
    (7374, 7685, "basket-35.wbbasket.ru"),
    (7686, 7997, "basket-36.wbbasket.ru"),
    (7998, 8309, "basket-37.wbbasket.ru"),
    (8310, 8741, "basket-38.wbbasket.ru"),
    (8742, 9173, "basket-39.wbbasket.ru"),
    (9174, 9605, "basket-40.wbbasket.ru"),
    (9606, 10373, "basket-41.wbbasket.ru"),
    (10374, 11141, "basket-42.wbbasket.ru"),
    (11142, 11909, "basket-43.wbbasket.ru"),
    (11910, 12677, "basket-44.wbbasket.ru"),
    (12678, 13445, "basket-45.wbbasket.ru"),
    (13446, 14213, "basket-46.wbbasket.ru"),
    (14214, 14981, "basket-47.wbbasket.ru"),
    (14982, 15749, "basket-48.wbbasket.ru"),
    (15750, 16517, "basket-49.wbbasket.ru"),
    (16518, 17285, "basket-50.wbbasket.ru"),
    (17286, 18053, "basket-51.wbbasket.ru"),
    (18054, 18821, "basket-52.wbbasket.ru"),
    (18822, 19589, "basket-53.wbbasket.ru"),
    (19590, 20357, "basket-54.wbbasket.ru"),
    (20358, 21125, "basket-55.wbbasket.ru"),
    (21126, 21893, "basket-56.wbbasket.ru"),
    (21894, 22661, "basket-57.wbbasket.ru"),
    (22662, 23429, "basket-58.wbbasket.ru"),
    (23430, 24197, "basket-59.wbbasket.ru"),
    (24198, 24965, "basket-60.wbbasket.ru"),
    (24966, 25733, "basket-61.wbbasket.ru"),
    (25734, 26501, "basket-62.wbbasket.ru"),
    (26502, 27269, "basket-63.wbbasket.ru"),
    (27270, 28037, "basket-64.wbbasket.ru"),
    (28038, 28805, "basket-65.wbbasket.ru"),
)


class BasketRouter:
    """
    Fast `O(log N)` router resolving Wildberries `nm_id` -> `basket-XX.wbbasket.ru` host and URLs.

    Maintains a preloaded snapshot up to `basket-65` and can be updated at runtime
    from the official live route map (`cdn.wbbasket.ru/api/v3/upstreams`).
    """

    def __init__(self, routes: Optional[List[BasketRoute]] = None) -> None:
        if routes is None:
            routes = [BasketRoute(a, b, h) for a, b, h in DEFAULT_BASKET_RANGES]
        self._set_routes(routes)

    def _set_routes(self, routes: List[BasketRoute]) -> None:
        self._routes: List[BasketRoute] = sorted(routes, key=lambda r: r.vol_from)
        self._starts: List[int] = [r.vol_from for r in self._routes]

    @property
    def routes_count(self) -> int:
        """Number of configured shard ranges."""
        return len(self._routes)

    def update_from_upstreams(self, payload: Dict[str, Any]) -> int:
        """
        Parse `origin.mediabasket_route_map` from `cdn.wbbasket.ru/api/v3/upstreams` JSON.
        Returns the number of loaded basket routes, or 0 if structure wasn't present.
        """
        origin = payload.get("origin") if isinstance(payload, dict) else None
        if not isinstance(origin, dict):
            return 0
        route_map = origin.get("mediabasket_route_map")
        if not isinstance(route_map, list) or not route_map:
            return 0

        hosts = route_map[0].get("hosts") if isinstance(route_map[0], dict) else None
        if not isinstance(hosts, list):
            return 0

        parsed: List[BasketRoute] = []
        for entry in hosts:
            if not isinstance(entry, dict):
                continue
            v_from = entry.get("vol_range_from")
            v_to = entry.get("vol_range_to")
            host = entry.get("host")
            if v_from is not None and v_to is not None and isinstance(host, str) and host:
                parsed.append(BasketRoute(int(v_from), int(v_to), host))

        if parsed:
            self._set_routes(parsed)
        return len(parsed)

    @staticmethod
    def vol_and_part(nm_id: int) -> Tuple[int, int]:
        """Compute `(vol, part)` path components for a given `nm_id`."""
        if nm_id <= 0:
            raise WBValidationError(f"nm_id must be positive integer, got {nm_id!r}")
        return nm_id // 100_000, nm_id // 1_000

    def resolve_host(self, nm_id: int) -> str:
        """Resolve exact `basket-XX.wbbasket.ru` host for `nm_id`."""
        vol, _ = self.vol_and_part(nm_id)
        if not self._routes:
            return "basket-01.wbbasket.ru"

        idx = bisect_right(self._starts, vol) - 1
        if idx < 0:
            return self._routes[0].host

        route = self._routes[idx]
        if route.vol_from <= vol <= route.vol_to:
            return route.host

        # Future article beyond known max route: extrapolate with +768 step
        last = self._routes[-1]
        if vol > last.vol_to:
            last_num_match = re.search(r"basket-(\d+)", last.host)
            base_num = int(last_num_match.group(1)) if last_num_match else len(self._routes)
            extra = (vol - last.vol_to - 1) // 768 + 1
            return f"basket-{base_num + extra:02d}.wbbasket.ru"

        return route.host

    def card_json_url(self, nm_id: int, lang: str = "ru") -> str:
        """Build direct `wbbasket.ru` URL for static card JSON (`card.json`)."""
        vol, part = self.vol_and_part(nm_id)
        host = self.resolve_host(nm_id)
        return f"https://{host}/vol{vol}/part{part}/{nm_id}/info/{lang}/card.json"

    def price_history_url(self, nm_id: int) -> str:
        """Build direct `wbbasket.ru` URL for product price history (`price-history.json`)."""
        vol, part = self.vol_and_part(nm_id)
        host = self.resolve_host(nm_id)
        return f"https://{host}/vol{vol}/part{part}/{nm_id}/info/price-history.json"

    def image_urls(
        self,
        nm_id: int,
        count: int,
        size: str = "big",
        ext: str = "webp",
    ) -> List[str]:
        """
        Generate image URLs (`1..count`) on `wbbasket.ru`.

        Modern Wildberries CDN serves `.webp` images (`images/big/1.webp`, `images/c516x688/1.webp`).
        """
        if count <= 0:
            return []
        vol, part = self.vol_and_part(nm_id)
        host = self.resolve_host(nm_id)
        return [
            f"https://{host}/vol{vol}/part{part}/{nm_id}/images/{size}/{i}.{ext}"
            for i in range(1, count + 1)
        ]


def calculate_feedback_shard(root_id: int) -> int:
    """
    Determine Wildberries feedback shard server (`1` or `2`) from `root_id` (`imt_id`).

    Matches WB frontend logic in `productFeedbacksService`:
        `e % 100 >= 50 ? "2" : "1"`
    """
    if root_id <= 0:
        return 1
    return 2 if (root_id % 100 >= 50) else 1


def feedback_url(root_id: int, version: int = 1, shard: Optional[int] = None) -> str:
    """Build Wildberries feedback endpoint URL (`https://feedbacks{1|2}.wb.ru/feedbacks/v{1|2}/{root_id}`)."""
    target_shard = shard if shard in (1, 2) else calculate_feedback_shard(root_id)
    return f"https://feedbacks{target_shard}.wb.ru/feedbacks/v{version}/{root_id}"


_NM_PATTERNS = (
    re.compile(r"/catalog/(\d+)"),
    re.compile(r"[?&]nm=(\d+)"),
    re.compile(r"^\s*(\d+)\s*$"),
)

_SELLER_PATTERNS = (
    re.compile(r"/seller/(\d+)"),
    re.compile(r"[?&]supplier=(\d+)"),
)


def extract_nm_id(url_or_id: str | int) -> int:
    """Extract numeric product `nm_id` from a Wildberries product URL or plain integer string."""
    if isinstance(url_or_id, int):
        if url_or_id <= 0:
            raise WBValidationError(f"Invalid nm_id: {url_or_id}")
        return url_or_id

    text = str(url_or_id).strip()
    for rx in _NM_PATTERNS:
        m = rx.search(text)
        if m:
            val = int(m.group(1))
            if val > 0:
                return val
    raise WBValidationError(f"Could not extract Wildberries article (nm_id) from: {url_or_id!r}")


def extract_seller_id(url_or_id: str | int) -> Optional[int]:
    """Extract numeric `supplier_id` from a seller store URL (`/seller/12345`), if present."""
    if isinstance(url_or_id, int):
        return url_or_id if url_or_id > 0 else None

    text = str(url_or_id).strip()
    for rx in _SELLER_PATTERNS:
        m = rx.search(text)
        if m:
            return int(m.group(1))
    return None


def classify_target(target: str) -> Tuple[str, str]:
    """
    Classify a user-supplied target string into `(kind, normalized_value)`:
    - `("product", "<nm_id>")` — product URL or numeric article ID
    - `("seller", "<seller_id>")` — seller store URL (`/seller/<id>`)
    - `("search", "<query>")` — WB search URL (`?search=...`) or plain keyword query
    """
    text = target.strip()
    seller = extract_seller_id(text)
    if seller is not None:
        return ("seller", str(seller))

    if text.startswith("http"):
        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        for key in ("search", "query", "q"):
            if key in qs and qs[key]:
                return ("search", unquote(qs[key][0]).strip())

    try:
        nm_id = extract_nm_id(text)
        return ("product", str(nm_id))
    except WBValidationError:
        pass

    return ("search", text)
