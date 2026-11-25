"""
Tests for WB Wallet Calculator (`wb_rank`), Search Rank Tracker (`wb_rank`),
and Smart Review Analyzer (`wb_smart_review`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from wb_parser.client import WBClient
from wb_parser.export import rank_results_to_excel
from wb_parser.mcp_server import WBMCPServer
from wb_parser.rank import WBRankTracker
from wb_parser.reviews import SmartReviewAnalyzer
from wb_parser.wallet import WBWalletCalculator


class _ExtrasMockTransport:
    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, headers=None) -> Any:
        if "default-payment.json" in url:
            return {
                "state": 0,
                "data": [
                    {"wc_type": "Незалогиненный кошелёк", "discount_value": 2, "is_active": True},
                    {"wc_type": "ВБ Клуб Аноним кошелёк", "discount_value": 5, "is_active": True},
                ],
            }
        if "settings-front.json" in url:
            return {"variables": {"wlt1DiscountDisplayMaxPrice": 15000, "pricesDeltaToShowSale": 5}}

        if "card.json" in url:
            return {
                "nm_id": 141217830,
                "imt_id": 181851928,
                "imt_name": "Кроссовки SB Dunk Low",
                "selling": {"brand_name": "Nike", "supplier_id": 626520},
                "media": {"photo_count": 3},
            }

        if "feedbacks1.wb.ru/feedbacks/v1/181851928" in url:
            return {
                "feedbackCountWithText": 3,
                "feedbackCount": 3,
                "valuation": "4.7",
                "feedbacks": [
                    {
                        "nmId": 141217830,
                        "productValuation": 5,
                        "pros": "Удобные; легкие",
                        "cons": "",
                        "text": "Идеальные кроссовки",
                        "matchingSize": "ok",
                        "bables": ["Удобство"],
                    },
                    {
                        "nmId": 141217830,
                        "productValuation": 5,
                        "pros": "Легкие",
                        "cons": "Долгая доставка",
                        "text": "Размер подошел",
                        "matchingSize": "ok",
                        "bables": ["Качество"],
                    },
                    {
                        "nmId": 999999999,
                        "productValuation": 2,
                        "pros": "",
                        "cons": "Маломерят",
                        "text": "Другой цвет не подошел",
                        "matchingSize": "small",
                    },
                ],
            }

        if "u-search" in url:
            page = int((params or {}).get("page", 1))
            if page == 1:
                return {
                    "products": [
                        {"id": 111, "name": "Other 1", "sizes": [{"price": {"basic": 300000, "product": 200000}}]},
                        {"id": 222, "name": "Other 2", "sizes": [{"price": {"basic": 300000, "product": 200000}}]},
                    ]
                }
            if page == 2:
                return {
                    "products": [
                        {"id": 141217830, "name": "Target Sneakers", "brand": "Nike", "sizes": [{"price": {"basic": 500000, "product": 400000}}]},
                    ]
                }
            return {"products": []}

        return {}

    def ping(self, url: str = "") -> Dict[str, Any]:
        return {"ok": True, "status_code": 200, "latency_ms": 5.0, "tls": "mock"}

    def close(self) -> None:
        pass


def test_wb_wallet_calculator():
    calc = WBWalletCalculator(transport=_ExtrasMockTransport())
    res = calc.calculate(1000)
    assert res.applied is True
    assert res.discount_pct == 2.0
    assert res.wallet_price == 980.0
    assert res.savings == 20.0

    club_res = calc.calculate(1000, use_club=True)
    assert club_res.discount_pct == 5.0
    assert club_res.wallet_price == 950.0

    capped = calc.calculate(20000)
    assert capped.applied is False
    assert "above_max_price" in capped.reason


def test_wb_rank_tracker_multi_page_and_delta(tmp_path: Path):
    db = tmp_path / "ranks.db"
    client = WBClient(transport=_ExtrasMockTransport(), tracker_db=db)
    tracker = WBRankTracker(client, db_path=db)

    res1 = tracker.check_rank(141217830, "кроссовки dunk", max_pages=3)
    assert res1.position == 3
    assert res1.page == 2
    assert res1.page_position == 1
    assert res1.wallet_price == 3920.0
    assert res1.rank_delta is None

    # Second run computes rank delta cleanly
    res2 = tracker.check_rank(141217830, "кроссовки dunk", max_pages=3)
    assert res2.previous_position == 3
    assert res2.rank_delta == 0

    xlsx = rank_results_to_excel([res2], tmp_path / "ranks.xlsx")
    assert xlsx.exists()


def test_smart_review_analyzer_color_filter_and_summary():
    client = WBClient(transport=_ExtrasMockTransport())
    analyzer = SmartReviewAnalyzer(client)

    summary = analyzer.fetch_reviews(141217830, only_this_color=True)
    assert summary.root_id == 181851928
    assert summary.shard == 1
    assert summary.total_analyzed == 2
    assert summary.avg_rating == 5.0
    assert summary.size_fit == {"ok": 2}
    assert any("Легкие (2x)" in p for p in summary.top_pros)
    assert any("Долгая доставка" in c for c in summary.top_cons)

    summary_all = analyzer.fetch_reviews(141217830, only_this_color=False)
    assert summary_all.total_analyzed == 3
    assert summary_all.size_fit["small"] == 1


def test_mcp_new_tools_integration(tmp_path: Path):
    client = WBClient(transport=_ExtrasMockTransport(), tracker_db=tmp_path / "mcp.db")
    srv = WBMCPServer(tracker_db=str(tmp_path / "mcp.db"), client=client)

    tools_resp = srv.handle_request({"jsonrpc": "2.0", "id": 10, "method": "tools/list"})
    tool_names = {t["name"] for t in tools_resp["result"]["tools"]}
    assert {"wb_wallet_price", "wb_check_rank", "wb_smart_reviews"}.issubset(tool_names)

    wal_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "wb_wallet_price", "arguments": {"price": 2000}},
    })
    assert wal_resp["result"]["structuredContent"]["wallet_price"] == 1960.0

    rank_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {"name": "wb_check_rank", "arguments": {"target": "141217830", "query": "кроссовки", "max_pages": 2}},
    })
    assert rank_resp["result"]["structuredContent"]["position"] == 3

    rev_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {"name": "wb_smart_reviews", "arguments": {"target": "141217830"}},
    })
    assert rev_resp["result"]["structuredContent"]["total_analyzed"] == 2
