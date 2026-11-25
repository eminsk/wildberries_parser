"""
Native Model Context Protocol (MCP) Server for WB SDK Pro (`wb-mcp`).
Exposes 9 JSON-RPC 2.0 stdio tools for Wildberries CDN card inspection, catalog search,
seller extraction, sharded feedback lookups, SQLite price-drop monitoring, live WB Wallet
pricing, search rank checking, smart review analysis (Free `g4f`/Ollama & Paid APIs),
and AI provider discovery/testing.
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
    {
        "name": "wb_wallet_price",
        "description": "Fetch active WB Wallet discount rules and calculate exact floored wallet price in RUB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Product price in RUB"},
                "use_club": {"type": "boolean", "default": False, "description": "Use WB Club discount tier"},
            },
            "required": ["price"],
        },
    },
    {
        "name": "wb_check_rank",
        "description": "Check a Wildberries product's organic search position (rank) for a keyword query and log history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Product URL or numeric nm_id"},
                "query": {"type": "string", "description": "Search keyword"},
                "max_pages": {"type": "integer", "default": 3},
                "sort": {
                    "type": "string",
                    "default": "popular",
                    "description": "Sort order (popular, pricedown, priceup, rate, newly)",
                },
            },
            "required": ["target", "query"],
        },
    },
    {
        "name": "wb_smart_reviews",
        "description": "Extract real product pros/cons, size fit stats, and rating breakdown via CDN + feedbacks1/2 with offline NLP, free (`g4f`/Ollama), or paid LLM summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Product URL or numeric nm_id"},
                "only_this_color": {"type": "boolean", "default": True},
                "limit": {"type": "integer", "default": 100},
                "ai_mode": {"type": "string", "default": "auto", "description": "AI mode: auto, free, paid, local, or offline"},
                "ai_provider": {"type": "string", "description": "Provider slug/name (e.g. Pollinations, Cerebras, g4f, ollama, openai, deepseek, openrouter, proxyapi, groq)"},
                "ai_model": {"type": "string", "description": "Optional AI model name"},
                "ai_base_url": {"type": "string", "description": "Optional OpenAI-compatible base URL"},
                "ai_key": {"type": "string", "description": "Optional OpenAI-compatible API key for paid LLM summarization"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "wb_ai_providers",
        "description": "List, inspect, health-check, or prompt Free (`g4f`/Ollama) and Paid (`OpenAI`/`DeepSeek`/`OpenRouter`/`ProxyAPI`/`Groq`) AI providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "default": "list", "description": "Action: list, models, test, quick_scan, or chat"},
                "tier": {"type": "string", "default": "all", "description": "Filter tier for list: all, free, paid, local, g4f"},
                "only_working": {"type": "boolean", "default": False},
                "only_free": {"type": "boolean", "default": False},
                "search": {"type": "string", "default": ""},
                "provider": {"type": "string", "description": "Provider name/slug/index"},
                "model": {"type": "string", "description": "Model name"},
                "mode": {"type": "string", "default": "auto", "description": "auto, free, paid, or local"},
                "prompt": {"type": "string", "default": "Ответь одним словом: Работает"},
                "timeout": {"type": "number", "default": 12.0},
            },
        },
    },
]


class WBMCPServer:
    """Native Model Context Protocol (MCP) JSON-RPC 2.0 stdio server (`wb-parser-mcp`)."""

    def __init__(
        self,
        *,
        proxy: Optional[str] = None,
        proxy_change_url: Optional[str] = None,
        cookies: Optional[str] = None,
        wbaas_token: Optional[str] = None,
        tracker_db: Optional[str] = None,
        client: Optional[WBClient] = None,
    ) -> None:
        self.proxy = proxy or os.environ.get("WB_PROXY")
        self.proxy_change_url = proxy_change_url or os.environ.get("WB_PROXY_CHANGE_URL")
        self.cookies = cookies or os.environ.get("WB_COOKIES")
        self.wbaas_token = wbaas_token or os.environ.get("WB_WBAAS_TOKEN")
        self.tracker_db = tracker_db or os.environ.get("WB_TRACKER_DB") or "wb_prices.db"
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

        if name == "wb_wallet_price":
            res = self.client.wallet_price(float(args["price"]), use_club=bool(args.get("use_club", False)))
            return {
                "base_price": res.base_price,
                "wallet_price": res.wallet_price,
                "savings": res.savings,
                "discount_pct": res.discount_pct,
                "applied": res.applied,
                "reason": res.reason,
            }

        if name == "wb_check_rank":
            res = self.client.check_rank(
                args["target"],
                str(args["query"]),
                max_pages=int(args.get("max_pages", 3)),
                sort=str(args.get("sort", "popular")),
            )
            return res.model_dump()

        if name == "wb_smart_reviews":
            summary = self.client.analyze_reviews(
                args["target"],
                only_this_color=bool(args.get("only_this_color", True)),
                limit=int(args.get("limit", 100)),
                ai_key=args.get("ai_key"),
                ai_mode=args.get("ai_mode"),
                ai_provider=args.get("ai_provider"),
                ai_model=args.get("ai_model"),
                ai_base_url=args.get("ai_base_url"),
            )
            data = summary.model_dump()
            # Keep compact payload for LLM contexts
            data["reviews"] = data["reviews"][:15]
            return data

        if name == "wb_ai_providers":
            from wb_parser.ai import (
                fetch_g4f_provider_models,
                find_ai_provider,
                generate_completion,
                is_g4f_available,
                list_ai_providers,
                quick_scan_ai_providers,
                test_ai_provider,
            )

            action = str(args.get("action") or "list").strip().lower()
            if action == "list":
                items = list_ai_providers(
                    tier=str(args.get("tier") or "all"),
                    only_working=bool(args.get("only_working", False)),
                    only_free=bool(args.get("only_free", False)),
                    search_query=str(args.get("search") or ""),
                )
                return {
                    "g4f_installed": is_g4f_available(),
                    "count": len(items),
                    "providers": [p.model_dump() for p in items],
                }
            if action == "models":
                info = find_ai_provider(str(args.get("provider") or ""))
                if info is None:
                    raise ValueError(f"Unknown AI provider: {args.get('provider')!r}")
                models = (
                    fetch_g4f_provider_models(info.id, timeout=float(args.get("timeout", 3.0)))
                    if info.backend == "g4f"
                    else list(info.models)
                )
                return {"provider": info.id, "backend": info.backend, "tier": info.tier, "models": models}
            if action == "test":
                res = test_ai_provider(
                    args.get("provider"),
                    mode=str(args.get("mode") or "auto"),
                    model=args.get("model"),
                    prompt=str(args.get("prompt") or "Ответь одним словом: Работает"),
                    timeout=float(args.get("timeout", 12.0)),
                )
                return res.model_dump()
            if action == "quick_scan":
                scanned = quick_scan_ai_providers(timeout=float(args.get("timeout", 6.0)))
                return {"count": len(scanned), "results": [r.model_dump() for r in scanned]}
            if action == "chat":
                out = generate_completion(
                    str(args.get("prompt") or ""),
                    mode=args.get("mode"),
                    provider=args.get("provider"),
                    model=args.get("model"),
                    timeout=float(args.get("timeout", 25.0)),
                )
                return out.model_dump()
            raise ValueError(f"Unknown wb_ai_providers action: {action!r}")

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
    parser.add_argument("--db", default=None)
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
