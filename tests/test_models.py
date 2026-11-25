"""
Tests for typed WB SDK data models covering modern WB v4, legacy v1,
CDN `card.json`, TOML/JSON config loading, and No-GIL thread safety.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from wb_parser.config import WBConfig
from wb_parser.models import Feedback, Item, Items, WBProduct, WBSearchPage
from wb_parser.shards import BasketRouter
from wb_parser.tracker import WBPriceTracker


def test_modern_sizes_price_extraction():
    payload = {
        "id": 22556677,
        "root": 998877,
        "name": "Кроссовки Ultra Boost",
        "brand": "Adidas",
        "supplierId": 12345,
        "pics": 4,
        "reviewRating": 4.8,
        "totalQuantity": 50,
        "volume": 50,
        "sizes": [
            {
                "name": "42",
                "price": {"basic": 1000000, "product": 450000, "total": 450000},
            }
        ],
    }
    p = WBProduct.model_validate(payload)
    assert p.id == 22556677
    assert p.root == 998877
    assert p.price == 4500.0
    assert p.basic_price == 10000.0
    assert p.discount == 55
    assert p.sale == 55
    assert p.salePriceU == 4500.0
    assert p.supplierId == 12345
    assert p.sizes == ["42"]


def test_cdn_card_json_normalization():
    cdn_payload = {
        "nm_id": 141217830,
        "imt_id": 181851928,
        "imt_name": "Кроссовки SB Dunk Low",
        "subj_name": "Кроссовки",
        "vendor_code": "SB-01",
        "description": "Отличные кеды для города",
        "selling": {"brand_name": "Nike", "supplier_id": 626520},
        "media": {"photo_count": 10},
        "options": [
            {"name": "Цвет", "value": "серый"},
            {"name": "Пол", "value": "Мужской"},
        ],
        "colors": [141217830, 183855588],
    }
    p = WBProduct.model_validate(cdn_payload)
    assert p.id == 141217830
    assert p.root == 181851928
    assert p.name == "Кроссовки SB Dunk Low"
    assert p.brand == "Nike"
    assert p.supplier_id == 626520
    assert p.pics == 10
    assert p.specs == {"Цвет": "серый", "Пол": "Мужской"}
    assert p.color_ids == [141217830, 183855588]
    assert p.url == "https://www.wildberries.ru/catalog/141217830/detail.aspx"


def test_legacy_item_and_price_drop():
    legacy = {
        "id": 1001,
        "name": "Велосипед",
        "salePriceU": 1599000,
        "priceU": 2000000,
        "brand": "Stels",
        "sale": 20,
        "rating": 5,
        "volume": 12,
        "supplierId": 55,
        "pics": 2,
        "root": 777,
    }
    p = Item.model_validate(legacy)
    assert isinstance(p, WBProduct)
    assert p.price == 15990.0
    p.old_price = 18000.0
    assert p.price_drop == 2010.0

    page = Items(products=[p])
    assert isinstance(page, WBSearchPage)
    fb = Feedback.model_validate({"feedbackCountWithText": 42, "valuation": "4.9"})
    assert fb.feedback_count == 42
    assert fb.valuation_float == 4.9


def test_toml_config_and_free_threaded_safety(tmp_path: Path):
    toml_file = tmp_path / "wb.toml"
    toml_file.write_text('[wildberries]\ndest = -1198055\nlimit = 50\n', encoding="utf-8")
    cfg = WBConfig.from_file(toml_file)
    assert cfg.dest == -1198055
    assert cfg.limit == 50

    router = BasketRouter()
    tracker = WBPriceTracker(tmp_path / "threaded.db")

    def _worker(idx: int) -> int:
        host = router.resolve_host(141_217_830 + idx)
        assert host.startswith("basket-")
        prod = WBProduct.model_validate({
            "nm_id": 100_000 + idx,
            "imt_id": 200_000 + idx,
            "imt_name": f"Товар {idx}",
            "price": 1000.0 + idx,
        })
        tracker.track_products([prod])
        dumped = prod.model_dump()
        assert dumped["id"] == 100_000 + idx
        return prod.id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_worker, range(24)))
    assert len(ids) == 24
