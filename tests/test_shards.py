"""
Tests for BasketRouter, dynamic upstreams, feedback sharding, and URL classification.
"""

from __future__ import annotations

import pytest

from wb_parser.exceptions import WBValidationError
from wb_parser.shards import (
    BasketRouter,
    calculate_feedback_shard,
    classify_target,
    extract_nm_id,
    extract_seller_id,
    feedback_url,
)


def test_basket_router_default_boundaries():
    router = BasketRouter()
    assert router.routes_count == 65
    assert router.resolve_host(100_000) == "basket-01.wbbasket.ru"
    assert router.resolve_host(14_399_999) == "basket-01.wbbasket.ru"  # vol 143
    assert router.resolve_host(14_400_000) == "basket-02.wbbasket.ru"  # vol 144
    assert router.resolve_host(141_217_830) == "basket-10.wbbasket.ru"  # vol 1412
    assert router.resolve_host(339_182_812) == "basket-20.wbbasket.ru"  # vol 3391
    assert router.resolve_host(2_880_500_000) == "basket-65.wbbasket.ru"  # vol 28805


def test_basket_router_future_extrapolation():
    router = BasketRouter()
    # vol = 28806 -> basket-66
    host = router.resolve_host(2_880_600_000)
    assert host == "basket-66.wbbasket.ru"


def test_basket_router_upstreams_update():
    router = BasketRouter()
    payload = {
        "origin": {
            "mediabasket_route_map": [
                {
                    "method": "range",
                    "hosts": [
                        {"vol_range_from": 0, "vol_range_to": 500, "host": "basket-01.wbbasket.ru"},
                        {"vol_range_from": 501, "vol_range_to": 1500, "host": "basket-02.wbbasket.ru"},
                    ],
                }
            ]
        }
    }
    count = router.update_from_upstreams(payload)
    assert count == 2
    assert router.resolve_host(141_217_830) == "basket-02.wbbasket.ru"


def test_basket_router_urls_and_webp():
    router = BasketRouter()
    assert router.card_json_url(141_217_830) == (
        "https://basket-10.wbbasket.ru/vol1412/part141217/141217830/info/ru/card.json"
    )
    assert router.price_history_url(141_217_830) == (
        "https://basket-10.wbbasket.ru/vol1412/part141217/141217830/info/price-history.json"
    )
    imgs = router.image_urls(141_217_830, 3)
    assert len(imgs) == 3
    assert imgs[0] == "https://basket-10.wbbasket.ru/vol1412/part141217/141217830/images/big/1.webp"
    assert imgs[2].endswith("/images/big/3.webp")
    assert router.image_urls(141_217_830, 0) == []


def test_calculate_feedback_shard():
    # Shard 1: root % 100 in 0..49
    assert calculate_feedback_shard(181_851_928) == 1  # 28 < 50
    assert calculate_feedback_shard(100_000) == 1      # 0 < 50
    assert calculate_feedback_shard(100_049) == 1      # 49 < 50
    # Shard 2: root % 100 in 50..99
    assert calculate_feedback_shard(100_050) == 2      # 50 >= 50
    assert calculate_feedback_shard(100_099) == 2      # 99 >= 50
    assert feedback_url(181_851_928) == "https://feedbacks1.wb.ru/feedbacks/v1/181851928"
    assert feedback_url(181_851_975) == "https://feedbacks2.wb.ru/feedbacks/v1/181851975"


def test_extractors_and_target_classification():
    assert extract_nm_id("https://www.wildberries.ru/catalog/141217830/detail.aspx?targetUrl=XS") == 141_217_830
    assert extract_nm_id(" 339182812 ") == 339_182_812
    assert extract_nm_id(141_217_830) == 141_217_830
    with pytest.raises(WBValidationError):
        extract_nm_id("not-a-valid-product")

    assert extract_seller_id("https://www.wildberries.ru/seller/626520") == 626_520
    assert extract_seller_id("https://www.wildberries.ru/catalog/141217830/detail.aspx") is None

    assert classify_target("https://www.wildberries.ru/catalog/141217830/detail.aspx") == ("product", "141217830")
    assert classify_target("https://www.wildberries.ru/seller/626520") == ("seller", "626520")
    assert classify_target("https://www.wildberries.ru/catalog/0/search.aspx?search=%D0%BA%D0%B5%D0%B4%D1%8B") == (
        "search",
        "кеды",
    )
    assert classify_target("беговые кроссовки") == ("search", "беговые кроссовки")
