"""
Tests for WBClient, AsyncWBClient, ParseWB, filter_products, and WBAAS fallback behavior.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from wb_parser.client import AsyncWBClient, ParseWB, WBClient, filter_products
from wb_parser.exceptions import WBAntiBotError, WBNotFoundError
from wb_parser.models import WBProduct


class MockSyncTransport:
    """In-memory mock transport simulating WB CDN, feedbacks1/2, and __internal endpoints."""

    def __init__(self, block_internal: bool = False) -> None:
        self.block_internal = block_internal
        self.calls: list[str] = []

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, headers=None) -> Any:
        self.calls.append(url)
        if "api/v3/upstreams" in url:
            return {
                "origin": {
                    "mediabasket_route_map": [
                        {
                            "hosts": [
                                {"vol_range_from": 0, "vol_range_to": 2000, "host": "basket-10.wbbasket.ru"}
                            ]
                        }
                    ]
                }
            }

        if "__internal" in url or "card.wb.ru" in url or "catalog.wb.ru" in url or "search.wb.ru" in url:
            if self.block_internal:
                raise WBAntiBotError("498 wbaas blocked", status_code=498, url=url)
            if "u-search" in url:
                page = int((params or {}).get("page", 1))
                if page > 1:
                    return {"products": []}
                return {
                    "products": [
                        {
                            "id": 141217830,
                            "root": 181851928,
                            "name": "Кроссовки Nike Dunk",
                            "brand": "Nike",
                            "supplierId": 626520,
                            "pics": 3,
                            "reviewRating": 4.9,
                            "sizes": [{"name": "42", "price": {"basic": 900000, "product": 550000}}],
                        }
                    ]
                }
            if "sellers" in url:
                page = int((params or {}).get("page", 1))
                if page > 1:
                    return {"data": {"products": []}}
                return {
                    "data": {
                        "products": [
                            {
                                "id": 141217830,
                                "root": 181851928,
                                "name": "Кроссовки Nike Dunk",
                                "brand": "Nike",
                                "supplierId": 626520,
                                "pics": 2,
                                "salePriceU": 550000,
                                "sale": 35,
                                "rating": 5,
                                "volume": 10,
                            }
                        ]
                    }
                }
            if "cards" in url:
                return {
                    "data": {
                        "products": [
                            {
                                "id": 141217830,
                                "root": 181851928,
                                "name": "Кроссовки Nike Dunk",
                                "brand": "Nike",
                                "supplierId": 626520,
                                "pics": 2,
                                "sizes": [{"name": "42", "price": {"basic": 800000, "product": 500000}}],
                            }
                        ]
                    }
                }

        if "card.json" in url:
            return {
                "nm_id": 141217830,
                "imt_id": 181851928,
                "imt_name": "Кроссовки Nike Dunk Low",
                "subj_name": "Кроссовки",
                "description": "Подробное описание из CDN",
                "selling": {"brand_name": "Nike", "supplier_id": 626520},
                "media": {"photo_count": 5},
                "options": [{"name": "Сезон", "value": "Демисезон"}],
            }

        if "price-history.json" in url:
            raise WBNotFoundError("404")

        if "feedbacks1.wb.ru/feedbacks/v1/181851928" in url:
            return {"feedbackCountWithText": 312, "feedbackCount": 420, "valuation": "4.8"}

        if "feedbacks2.wb.ru" in url:
            raise WBNotFoundError("wrong shard")

        raise WBNotFoundError(url)

    def ping(self, url: str = "") -> Dict[str, Any]:
        return {"ok": True, "status_code": 200, "latency_ms": 12.4, "tls": "mock"}

    def close(self) -> None:
        pass


class MockAsyncTransport:
    def __init__(self) -> None:
        self._sync = MockSyncTransport(block_internal=False)

    async def get_json(self, url: str, params=None, headers=None) -> Any:
        return self._sync.get_json(url, params=params, headers=headers)

    async def close(self) -> None:
        pass


def test_wb_client_fallback_when_wbaas_blocks_internal():
    transport = MockSyncTransport(block_internal=True)
    with WBClient(transport=transport) as client:
        prod = client.get_product("https://www.wildberries.ru/catalog/141217830/detail.aspx")
        assert prod.id == 141217830
        assert prod.root == 181851928
        assert prod.supplier_id == 626520
        assert prod.feedback_shard == 1
        assert prod.feedback_count == 312
        assert prod.valuation == "4.8"
        assert len(prod.image_links) == 5
        assert prod.image_links[0].endswith("/images/big/1.webp")


def test_wb_client_search_and_filter():
    transport = MockSyncTransport(block_internal=False)
    with WBClient(transport=transport) as client:
        items = client.search("nike dunk", enrich_cdn=True, with_feedbacks=True)
        assert len(items) == 1
        assert items[0].price == 5500.0
        assert items[0].description == "Подробное описание из CDN"
        assert items[0].feedback_count == 312

        kept = filter_products(items, min_price=5000, max_price=6000, white_keywords=["nike"])
        assert len(kept) == 1
        excluded = filter_products(items, black_keywords=["nike"])
        assert len(excluded) == 0


def test_parse_wb_drop_in_compatibility(tmp_path: Path):
    out = tmp_path / "seller_items.csv"
    parser = ParseWB("https://www.wildberries.ru/catalog/141217830/detail.aspx", output_path=str(out))
    parser.client = WBClient(transport=MockSyncTransport(block_internal=False))
    products = parser.parse()
    assert len(products) == 1
    assert parser.seller_id == 626520
    assert out.exists()
    content = out.read_text(encoding="utf-8-sig")
    assert "Кроссовки Nike Dunk" in content


def test_async_client_gather_cards():
    import asyncio

    async def _run():
        async with AsyncWBClient(transport=MockAsyncTransport()) as client:
            res = await client.gather_cards([141217830])
            assert len(res) == 1
            assert isinstance(res[0], WBProduct)
            assert res[0].feedback_count == 312

    asyncio.run(_run())
