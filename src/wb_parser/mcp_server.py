"""
Native Model Context Protocol (MCP) Server for Wildberries Parser SDK (`wb-mcp`).
Exposes Wildberries card inspection, catalog search, seller extraction, sharded feedback lookups,
and SQLite price drop monitoring over JSON-RPC 2.0 stdio.
"""

from __future__ import annotations

import io
import json
import os
import sys
from typing import Any, Dict, List, Optional

from wb_parser.client import WBClient, filter_products
from wb_parser.export import to_excel
from wb_parser.shards import calculate_feedback_shard, extract_nm_id
from wb_parser.tracker import WBPriceTracker

SUPPORTED_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2024-11-05",
)
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

MCP_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "wb_get_card",
        "description": (
            "Fetch complete Wildberries product metadata directly from wbbasket.ru CDN "
            "(name, brand, supplier_id, imt_id/root_id, options/specs, description, "
            ".webp image links) plus sharded review counts (feedbacks1/2)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Wildberries product URL or numeric nm_id"},
                "with_feedbacks": {"type": "boolean", "default": True, "description": "Fetch feedbacks1/2 review count & rating"},
                "with_price_history": {"type": "boolean", "default": False, "description": "Fetch CDN price-history.json"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "wb_get_feedbacks",
        "description": (
            "Fetch product review count and average rating using Wildberries shard routing "
            "(root_id % 100 >= 50 -> feedbacks2, else feedbacks1)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "root_id": {"type": "integer", "description": "Wildberries root_id (imt_id)"},
            },
            "required": ["root_id"],
        },
    },
    {
        "name": "wb_search",
        "description": (
            "Search Wildberries catalog with price, discount, rating filters and optional Excel export."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'беговые кроссовки')"},
                "min_price": {"type": "integer", "default": 0},
                "max_price": {"type": "integer", "default": 999999999},
                "min_discount": {"type": "integer", "default": 0},
                "min_rating": {"type": "number", "default": 0.0},
                "limit": {"type": "integer", "default": 20},
                "max_pages": {"type": "integer", "default": 1},
                "excel_path": {"type": "string", "description": "Optional .xlsx output path"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wb_get_seller_catalog",
        "description": "Scrape all items for a Wildberries seller by seller URL, supplier_id, or sample product URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Seller URL, supplier_id, or product URL"},
                "max_pages": {"type": "integer", "default": 3},
                "limit": {"type": "integer", "default": 100},
                "excel_path": {"type": "string", "description": "Optional .xlsx output path"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "wb_price_drops",
        "description": "Query SQLite price tracker for tracked price drops or history of a specific nm_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nm_id": {"type": "integer", "description": "Optional product nm_id for full history"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
]


class WBMCPServer:
    """Zero-dependency Model Context Protocol (MCP) JSON-RPC 2.0 server."""

    def __init__(
        self,
        *,
        proxy: Optional[str] = None,
        proxy_change_url: Optional[str] = None,
        cookies: Optional[str] = None,
        wbaas_token: Optional[str] = None,
        tracker_db: str = "wb_prices.db",
        client: Optional[WBClient] = None,
    ) -> None:
        self.proxy = proxy or os.environ.get("WB_PROXY")
        self.proxy_change_url = proxy_change_url or os.environ.get("WB_PROXY_CHANGE_URL")
        self.cookies = cookies or os.environ.get("WB_COOKIES")
        self.wbaas_token = wbaas_token or os.environ.get("WB_WBAAS_TOKEN")
        self.tracker_db = tracker_db or os.environ.get("WB_TRACKER_DB", "wb_prices.db")
        self._client = client

    @property
    def client(self) -> WBClient:
        if self._client is None:
            self._client = WBClient(
                proxy=self.proxy,
                proxy_change_url=self.proxy_change_url,
                cookies=self.cookies,
                wbaas_token=self.wbaas_token,
                tracker_db=self.tracker_db,
            )
        return self._client

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC 2.0 request or notification."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params") or {}

        if req_id is None and method.startswith("notifications/"):
            return None

        try:
            if method == "initialize":
                from wb_parser import __version__
                client_version = params.get("protocolVersion")
                negotiated = (
                    client_version
                    if client_version in SUPPORTED_PROTOCOL_VERSIONS
                    else LATEST_PROTOCOL_VERSION
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": negotiated,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "wb-parser-mcp", "version": __version__},
                    },
                }

            if method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            if method == "tools/list":
                return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS_SCHEMA}}

            if method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments") or {}
                output = self._call_tool(tool_name, args)
                call_result: Dict[str, Any] = {
                    "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False, indent=2)}],
                    "isError": False,
                }
                if isinstance(output, dict):
                    call_result["structuredContent"] = output
                return {"jsonrpc": "2.0", "id": req_id, "result": call_result}

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            }

    def _call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if name == "wb_get_card":
            prod = self.client.get_product(
                args["target"],
                enrich_cdn=True,
                with_feedbacks=bool(args.get("with_feedbacks", True)),
                with_price_history=bool(args.get("with_price_history", False)),
            )
            return prod.to_dict()

        if name == "wb_get_feedbacks":
            root_id = extract_nm_id(args["root_id"])
            shard = calculate_feedback_shard(root_id)
            fb = self.client.get_feedbacks(root_id)
            if fb is None:
                return {"root_id": root_id, "expected_shard": f"feedbacks{shard}", "found": False}
            return {
                "root_id": root_id,
                "expected_shard": f"feedbacks{shard}",
                "used_shard": f"feedbacks{fb.shard}",
                "valuation": fb.valuation,
                "feedback_count_with_text": fb.feedback_count,
                "total_feedback_count": fb.total_feedback_count,
                "distribution_pct": fb.valuation_distribution,
            }

        if name == "wb_search":
            raw = self.client.search(
                str(args["query"]),
                max_pages=int(args.get("max_pages", 1)),
                limit=int(args.get("limit", 20)),
            )
            items = filter_products(
                raw,
                min_price=int(args.get("min_price", 0)),
                max_price=int(args.get("max_price", 999_999_999)),
                min_discount=int(args.get("min_discount", 0)),
                min_rating=float(args.get("min_rating", 0.0)),
            )
            if args.get("excel_path"):
                to_excel(items, args["excel_path"])
            return {"count": len(items), "items": [p.to_dict() for p in items]}

        if name == "wb_get_seller_catalog":
            items = self.client.get_seller_catalog(
                args["target"],
                max_pages=int(args.get("max_pages", 3)),
                limit=int(args.get("limit", 100)),
            )
            if args.get("excel_path"):
                to_excel(items, args["excel_path"])
            return {"count": len(items), "items": [p.to_dict() for p in items]}

        if name == "wb_price_drops":
            tracker = self.client.tracker or WBPriceTracker(self.tracker_db)
            if args.get("nm_id") is not None:
                nm_id = int(args["nm_id"])
                history = tracker.get_history(nm_id)
                return {"nm_id": nm_id, "history": [h.model_dump() for h in history]}
            drops = tracker.get_price_drops(limit=int(args.get("limit", 50)))
            return {"count": len(drops), "drops": [d.model_dump() for d in drops]}

        raise ValueError(f"Unknown MCP tool: {name}")

    def run_stdio(self) -> None:
        """Serve JSON-RPC 2.0 messages line by line over UTF-8 stdio."""
        stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8") if hasattr(sys.stdin, "buffer") else sys.stdin
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass

        for raw_line in stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp = self.handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()


def main_mcp(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for `wb-mcp`."""
    import argparse

    parser = argparse.ArgumentParser(description="Start Wildberries SDK Model Context Protocol (MCP) Server")
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--proxy-change-url", default=None)
    parser.add_argument("--cookies", default=None)
    parser.add_argument("--wbaas-token", default=None)
    parser.add_argument("--db", default="wb_prices.db")
    args = parser.parse_args(argv)

    srv = WBMCPServer(
        proxy=args.proxy,
        proxy_change_url=args.proxy_change_url,
        cookies=args.cookies,
        wbaas_token=args.wbaas_token,
        tracker_db=args.db,
    )
    srv.run_stdio()
    return 0


if __name__ == "__main__":
    sys.exit(main_mcp())
