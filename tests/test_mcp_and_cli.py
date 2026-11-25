"""
Tests for Native MCP JSON-RPC 2.0 Server (`wb-mcp`) and CLI subcommands (`wb-parser`).
"""

from __future__ import annotations

import json
from pathlib import Path

from wb_parser.cli import main as cli_main
from wb_parser.client import WBClient
from wb_parser.mcp_server import WBMCPServer
from wb_parser.models import WBProduct
from wb_parser.tracker import WBPriceTracker


class _FakeTransport:
    def get_json(self, url: str, params=None, headers=None):
        if "feedbacks1.wb.ru/feedbacks/v1/181851928" in url:
            return {"feedbackCountWithText": 312, "feedbackCount": 420, "valuation": "4.8"}
        return {}

    def ping(self, url: str = ""):
        return {"ok": True, "status_code": 200, "latency_ms": 10.0, "tls": "mock"}

    def close(self) -> None:
        pass


def test_mcp_server_protocol_and_tools(tmp_path: Path):
    db = tmp_path / "mcp.db"
    tracker = WBPriceTracker(db)
    tracker.track_products([WBProduct(id=555, root=555, name="Test", price=1000.0)])
    tracker.track_products([WBProduct(id=555, root=555, name="Test", price=800.0)])

    client = WBClient(transport=_FakeTransport(), tracker_db=db)
    srv = WBMCPServer(tracker_db=str(db), client=client)

    init_resp = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init_resp["result"]["serverInfo"]["name"] == "wb-parser-mcp"

    notif = srv.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert notif is None

    list_resp = srv.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in list_resp["result"]["tools"]}
    assert {"wb_get_card", "wb_get_feedbacks", "wb_search", "wb_get_seller_catalog", "wb_price_drops"}.issubset(names)

    fb_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "wb_get_feedbacks", "arguments": {"root_id": 181851928}},
    })
    structured = fb_resp["result"]["structuredContent"]
    assert structured["expected_shard"] == "feedbacks1"
    assert structured["feedback_count_with_text"] == 312

    drops_resp = srv.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "wb_price_drops", "arguments": {}},
    })
    assert drops_resp["result"]["structuredContent"]["count"] == 1

    unknown_method = srv.handle_request({"jsonrpc": "2.0", "id": 5, "method": "foo/bar"})
    assert unknown_method["error"]["code"] == -32601


def test_cli_drops_and_help(tmp_path: Path, capsys):
    db = tmp_path / "cli.db"
    tracker = WBPriceTracker(db)
    tracker.track_products([WBProduct(id=777, root=777, name="Велосипед", price=12000.0)])
    tracker.track_products([WBProduct(id=777, root=777, name="Велосипед", price=9500.0)])

    rc = cli_main(["drops", "--db", str(db)])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "9,500" in captured and "-2,500" in captured
