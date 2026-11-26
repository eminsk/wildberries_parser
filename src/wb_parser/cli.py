"""
Command-Line Interface (CLI) for Wildberries Parser SDK (`wb-parser` / `wb-sdk`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from wb_parser import __version__
from wb_parser.client import WBClient, filter_products
from wb_parser.config import DEFAULT_DEST, DEST_CODES, DOCS_URL, ISSUES_URL, TELEGRAM_CHANNEL_URL
from wb_parser.export import rank_results_to_excel, reviews_to_excel, to_csv, to_excel, to_json, to_jsonl
from wb_parser.models import WBProduct
from wb_parser.shards import calculate_feedback_shard, extract_nm_id
from wb_parser.telegram import TelegramNotifier, WBTelegramBot
from wb_parser.tracker import WBPriceTracker


def _export_results(products: List[WBProduct], output_path: Optional[str]) -> Optional[Path]:
    if not output_path:
        return None
    path = Path(output_path)
    ext = path.suffix.lower()
    if ext == ".xlsx":
        to_excel(products, path)
    elif ext == ".csv":
        to_csv(products, path)
    elif ext == ".jsonl":
        to_jsonl(products, path)
    else:
        to_json(products, path)
    print(f"[+] Exported {len(products)} item(s) -> {path}")
    return path


def _add_tg_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--tg-token", default=None, help="Optional Telegram Bot Token to send results/Excel")
    subparser.add_argument("--tg-chat-id", default=None, help="Optional Telegram Chat or Channel ID")
    subparser.add_argument("--tg-proxy", default=None, help="Optional separate SOCKS5/HTTP proxy for Telegram API")


def _notify_cli_export(args: argparse.Namespace, products: List[WBProduct], exported: Optional[Path], title: str) -> None:
    token = getattr(args, "tg_token", None)
    chat_id = getattr(args, "tg_chat_id", None)
    if not (token and chat_id):
        return
    notifier = TelegramNotifier(token, chat_id, proxy=getattr(args, "tg_proxy", None))
    if exported and exported.exists():
        notifier.send_excel(exported, caption=f"📊 {title} ({len(products)} шт.)")
    elif products:
        notifier.notify_many(products[:5])


def _print_products_table(products: List[WBProduct]) -> None:
    if not products:
        print("No products found.")
        return
    for idx, p in enumerate(products, start=1):
        price_str = f"{p.price:,.0f} RUB" if p.price > 0 else "CDN (no live price)"
        disc_str = f" (-{p.discount}%)" if p.discount > 0 else ""
        fb_str = f" | ★ {p.valuation or p.rating} ({p.feedback_count} reviews)" if (p.feedback_count or p.rating) else ""
        print(f"{idx:2d}. [{p.id}] {p.name[:60]} | {p.brand or '-'} | {price_str}{disc_str}{fb_str}")


def _build_client(args: argparse.Namespace) -> WBClient:
    dest_val = getattr(args, "dest", DEFAULT_DEST)
    if isinstance(dest_val, str) and dest_val in DEST_CODES:
        dest_val = DEST_CODES[dest_val]
    return WBClient(
        dest=int(dest_val),
        proxy=getattr(args, "proxy", None),
        proxy_change_url=getattr(args, "proxy_change_url", None),
        mobileproxy_key=getattr(args, "mobileproxy_key", None),
        cookies=getattr(args, "cookies", None),
        wbaas_token=getattr(args, "wbaas_token", None),
        tracker_db=getattr(args, "db", None),
    )


def _add_network_args(subparser: argparse.ArgumentParser, *, db_default: Optional[str] = "wb_prices.db") -> None:
    subparser.add_argument("--dest", default=str(DEFAULT_DEST), help="WB region destination ID or city name")
    subparser.add_argument("--proxy", default=None, help="Proxy URL (http://user:pass@ip:port or socks5://...)")
    subparser.add_argument("--proxy-change-url", default=None, help="Mobile proxy rotation URL")
    subparser.add_argument("--mobileproxy-key", default=None, help="MobileProxy.rent/space API rotation key")
    subparser.add_argument("--cookies", default=None, help="Optional browser Cookie header string")
    subparser.add_argument("--wbaas-token", default=None, help="Optional x-wbaas-token header")
    subparser.add_argument("--db", default=db_default, help="SQLite price history path")


def _handle_ai_command(args: argparse.Namespace) -> int:
    """Handle `wb-parser ai` (Free g4f/Ollama + Paid OpenAI/DeepSeek/OpenRouter/ProxyAPI/Groq)."""
    from wb_parser.ai import (
        fetch_g4f_provider_models,
        find_ai_provider,
        generate_completion,
        is_g4f_available,
        list_ai_providers,
        quick_scan_ai_providers,
        test_ai_provider,
    )

    if args.quick_scan:
        results = quick_scan_ai_providers(timeout=min(args.timeout, 8.0))
        if args.json:
            print(json.dumps([r.model_dump() for r in results], ensure_ascii=False, indent=2))
            return 0
        if not results:
            print('No live g4f or configured paid providers detected. Install free AI: uv add "wb-sdk-pro[ai]"')
            return 0
        for r in results:
            tag = "LIVE" if r.success else "DEAD"
            detail = r.response_text[:60] if r.success else f"{r.error_type}: {r.error_message}"[:70]
            print(f"[{tag:4s}] {r.provider:<18} ({r.tier}/{r.model or 'default'}) {r.latency_seconds:>5.2f}s | {detail}")
        return 0

    if args.ask:
        res = generate_completion(
            args.ask,
            mode=args.mode,
            provider=args.provider,
            model=args.model,
            api_key=args.key,
            base_url=args.url,
            timeout=args.timeout,
        )
        if args.json:
            print(res.model_dump_json(indent=2))
        elif res.ok:
            print(f"[{res.tier}:{res.provider}/{res.model} in {res.latency_seconds}s]\n{res.content}")
        else:
            print(f"[FAILED] {res.error}", file=sys.stderr)
        return 0 if res.ok else 1

    tier_filter = args.tier
    if args.local:
        tier_filter = "local"
    elif args.paid and tier_filter == "all":
        tier_filter = "paid"

    if args.list or (not args.provider):
        items = list_ai_providers(
            tier=tier_filter,
            only_working=args.working,
            only_free=args.free,
            search_query=args.search,
        )
        if args.json:
            print(json.dumps({
                "g4f_installed": is_g4f_available(),
                "count": len(items),
                "providers": [p.model_dump() for p in items],
            }, ensure_ascii=False, indent=2))
            return 0
        print(f"AI Providers ({len(items)}) | g4f installed: {is_g4f_available()}")
        for p in items:
            auth_flag = "KEY" if p.needs_auth else "FREE"
            cfg_flag = "ready" if p.configured else "needs-key"
            print(
                f"{p.index:3d}. [{p.tier:<6s}|{auth_flag:<4s}|{cfg_flag:<9s}] "
                f"{p.id:<18s} model={p.default_model or '-'}"
            )
        if not is_g4f_available():
            print('Tip: install free key-less AI providers via: uv add "wb-sdk-pro[ai]"')
        return 0

    info = find_ai_provider(args.provider)
    if not info:
        print(f"Error: AI provider {args.provider!r} not found.", file=sys.stderr)
        return 1

    if args.test:
        res = test_ai_provider(
            info.id,
            mode=args.mode,
            model=args.model,
            api_key=args.key,
            base_url=args.url,
            prompt=args.prompt,
            timeout=args.timeout,
        )
        if args.json:
            print(res.model_dump_json(indent=2))
        elif res.success:
            print(f"[OK] {res.provider} ({res.model}) in {res.latency_seconds}s -> {res.response_text}")
        else:
            print(f"[FAIL] {res.provider}: {res.error_type}: {res.error_message}")
            if res.hint:
                print(f"Hint: {res.hint}")
        return 0 if res.success else 1

    models = (
        fetch_g4f_provider_models(info.id, timeout=min(args.timeout, 5.0))
        if info.backend == "g4f"
        else info.models
    )
    if args.json:
        print(json.dumps({**info.model_dump(), "models": models}, ensure_ascii=False, indent=2))
    else:
        print(f"Provider: {info.id} ({info.name}) | backend={info.backend} | tier={info.tier}")
        print(f"Default model: {info.default_model or '-'} | auth_required={info.needs_auth} | configured={info.configured}")
        if info.base_url or info.url:
            print(f"URL: {info.base_url or info.url}")
        print(f"Models ({len(models)}): {', '.join(models[:30]) or '(dynamic / pass --model)'}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="wb-parser",
        description=(
            f"WB SDK Pro v{__version__} — CDN Card Inspector, Feedbacks1/2 Sharder, "
            "WB Wallet Calculator, Rank Tracker, Smart Reviews, Free/Paid AI, Search, MCP & GUI"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Telegram Support: {TELEGRAM_CHANNEL_URL}\n"
            f"Docs: {DOCS_URL}\n"
            f"Issues: {ISSUES_URL}"
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 1. card
    card_p = subparsers.add_parser("card", help="Fetch single product card (CDN card.json + feedbacks1/2)")
    card_p.add_argument("target", help="Wildberries product URL or numeric article (nm_id)")
    card_p.add_argument("--no-feedbacks", action="store_true", help="Skip feedbacks1/2 request")
    card_p.add_argument("--history", action="store_true", help="Include CDN price-history.json")
    card_p.add_argument("-o", "--output", help="Save output (.json, .jsonl, .csv, .xlsx)")
    _add_network_args(card_p)

    # 2. feedbacks
    fb_p = subparsers.add_parser("feedbacks", help="Fetch sharded reviews from feedbacks1/2 using root_id or nm_id")
    fb_p.add_argument("target", help="Root ID (imt_id) OR product URL / nm_id (use --is-nm)")
    fb_p.add_argument("--is-nm", action="store_true", help="Resolve nm_id -> root_id via CDN card.json first")
    _add_network_args(fb_p)

    # 3. seller
    seller_p = subparsers.add_parser("seller", help="Scrape all products for a seller URL, supplier ID, or sample item URL")
    seller_p.add_argument("target", help="Seller URL (/seller/123), supplier ID, or product URL")
    seller_p.add_argument("-p", "--pages", type=int, default=5, help="Max catalog pages")
    seller_p.add_argument("-n", "--limit", type=int, default=200, help="Max items")
    seller_p.add_argument("--enrich", action="store_true", help="Enrich each item with full CDN card.json specs")
    seller_p.add_argument("--no-feedbacks", action="store_true", help="Skip feedback fetching")
    seller_p.add_argument("-o", "--output", help="Save output (.xlsx, .csv, .json, .jsonl)")
    _add_network_args(seller_p)
    _add_tg_args(seller_p)

    # 4. search
    search_p = subparsers.add_parser("search", help="Search Wildberries catalog")
    search_p.add_argument("query", help="Search keyword")
    search_p.add_argument("-p", "--pages", type=int, default=2, help="Max pages")
    search_p.add_argument("-n", "--limit", type=int, default=50, help="Max items")
    search_p.add_argument("--min-price", type=int, default=0, help="Minimum price filter (RUB)")
    search_p.add_argument("--max-price", type=int, default=999_999_999, help="Maximum price filter (RUB)")
    search_p.add_argument("--min-discount", type=int, default=0, help="Minimum discount percentage")
    search_p.add_argument("--min-rating", type=float, default=0.0, help="Minimum rating filter")
    search_p.add_argument("--enrich", action="store_true", help="Enrich with CDN card.json specs")
    search_p.add_argument("--with-feedbacks", action="store_true", help="Fetch sharded reviews")
    search_p.add_argument("-o", "--output", help="Save output (.xlsx, .csv, .json, .jsonl)")
    _add_network_args(search_p)
    _add_tg_args(search_p)

    # 5. drops
    drops_p = subparsers.add_parser("drops", help="Show tracked price drops from SQLite")
    drops_p.add_argument("--db", default="wb_prices.db", help="Path to SQLite tracker DB")
    drops_p.add_argument("-n", "--limit", type=int, default=50, help="Max records")

    # 6. upstreams
    up_p = subparsers.add_parser("upstreams", help="Fetch live CDN basket shard ranges (cdn.wbbasket.ru)")
    _add_network_args(up_p)

    # 7. wallet
    wal_p = subparsers.add_parser("wallet", help="Calculate WB Wallet discounted price for a RUB price")
    wal_p.add_argument("price", type=float, help="Base price in RUB")
    wal_p.add_argument("--club", action="store_true", help="Use WB Club discount tier")
    _add_network_args(wal_p)

    # 8. rank
    rank_p = subparsers.add_parser("rank", help="Check product search position (rank) for a keyword query")
    rank_p.add_argument("target", help="Product URL or numeric nm_id")
    rank_p.add_argument("query", help="Search keyword query")
    rank_p.add_argument("-p", "--pages", type=int, default=3, help="Max search pages to scan (100 items/page)")
    rank_p.add_argument("--sort", default="popular", help="Sort order (popular, pricedown, priceup, rate, newly)")
    rank_p.add_argument("-o", "--output", help="Save rank report (.xlsx or .json)")
    _add_network_args(rank_p)

    # 9. reviews
    rev_p = subparsers.add_parser("reviews", help="Smart Review Analyzer (offline NLP, free g4f/Ollama, or paid LLM)")
    rev_p.add_argument("target", help="Product URL or numeric nm_id")
    rev_p.add_argument("--all-colors", action="store_true", help="Analyze all linked colors (root_id) instead of single nm_id")
    rev_p.add_argument("-n", "--limit", type=int, default=100, help="Max reviews to inspect")
    rev_p.add_argument("--mode", default="auto", choices=["auto", "free", "paid", "local", "offline"], help="AI mode (default: auto)")
    rev_p.add_argument("--provider", default=None, help="AI provider (e.g. Pollinations, Cerebras, g4f, ollama, openai, deepseek, openrouter, proxyapi, groq)")
    rev_p.add_argument("--ai-key", default=None, help="Optional API key for paid OpenAI-compatible providers")
    rev_p.add_argument("--ai-url", default=None, help="Optional custom OpenAI-compatible base URL")
    rev_p.add_argument("--ai-model", default=None, help="Model name (auto-selected per provider if omitted)")
    rev_p.add_argument("--ai-timeout", type=float, default=25.0, help="AI completion timeout in seconds")
    rev_p.add_argument("-o", "--output", help="Save summary JSON file")
    _add_network_args(rev_p)

    # 10. ai
    ai_p = subparsers.add_parser("ai", help="Discover, health-check, and query Free (g4f/Ollama) & Paid AI providers")
    ai_p.add_argument("--list", action="store_true", help="List available free & paid AI providers")
    ai_p.add_argument("--tier", default="all", choices=["all", "free", "paid", "local", "g4f"], help="Provider tier filter")
    ai_p.add_argument("--working", action="store_true", help="Show only working g4f/active providers")
    ai_p.add_argument("--free", action="store_true", help="Filter strictly zero-key providers")
    ai_p.add_argument("--paid", action="store_true", help="Filter paid/key-based providers")
    ai_p.add_argument("--local", action="store_true", help="Filter local key-free providers (Ollama, LM Studio)")
    ai_p.add_argument("--search", default="", help="Search providers by name or URL")
    ai_p.add_argument("-p", "--provider", default=None, help="Select provider by index, slug, or g4f name")
    ai_p.add_argument("--models", action="store_true", help="Show supported models for --provider")
    ai_p.add_argument("-t", "--test", action="store_true", help="Run latency/error health-check on provider/model")
    ai_p.add_argument("--quick-scan", action="store_true", help="Quick-scan popular free g4f + configured paid providers")
    ai_p.add_argument("--ask", default=None, help="Send a prompt using free, local, or paid models")
    ai_p.add_argument("--mode", default="auto", choices=["auto", "free", "paid", "local"], help="Execution mode (auto, free, paid, local)")
    ai_p.add_argument("-m", "--model", default=None, help="Specific AI model name")
    ai_p.add_argument("--key", default=None, help="Optional API key for paid endpoint")
    ai_p.add_argument("--url", default=None, help="Optional OpenAI-compatible base URL")
    ai_p.add_argument("--prompt", default="Ответь одним словом: Работает", help="Health-check test prompt")
    ai_p.add_argument("--timeout", type=float, default=12.0, help="Timeout in seconds")
    ai_p.add_argument("--json", action="store_true", help="Emit structured JSON output")

    # 11. mcp
    mcp_p = subparsers.add_parser("mcp", help="Start native JSON-RPC 2.0 MCP Server over stdio")
    _add_network_args(mcp_p, db_default=None)

    # 12. gui
    subparsers.add_parser("gui", help="Launch Dark-Themed 7-Tab WB SDK Pro Desktop GUI (requires [gui] extra)")

    # 13. bot
    bot_p = subparsers.add_parser(
        "bot",
        help="Start interactive WBTelegramBot with live progress bars, /drops, /wallet, /rank, /reviews & Excel export",
    )
    bot_p.add_argument("--tg-token", default=None, help="Telegram Bot Token (or set WB_TG_TOKEN env var)")
    bot_p.add_argument("--tg-proxy", default=None, help="Optional SOCKS5/HTTP proxy for Telegram API (or WB_TG_PROXY)")
    bot_p.add_argument("--channel-id", default=None, help="Optional channel/chat ID for forwarding reports")
    bot_p.add_argument("--workers", type=int, default=2, help="Parallel worker threads (1..16)")
    bot_p.add_argument("-n", "--limit", type=int, default=50, help="Default max items per search (1..5000)")
    bot_p.add_argument("-p", "--pages", type=int, default=2, help="Default search pages")
    bot_p.add_argument("--no-cdn", action="store_true", help="Disable per-item CDN card.json enrichment")
    bot_p.add_argument("--no-feedbacks", action="store_true", help="Skip sharded feedbacks enrichment")
    _add_network_args(bot_p)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "gui":
        from wb_parser.gui import main_gui
        return main_gui()

    if args.command == "bot":
        import os

        token = (args.tg_token or os.getenv("WB_TG_TOKEN", "")).strip()
        if not token:
            print("Error: --tg-token or WB_TG_TOKEN environment variable is required.", file=sys.stderr)
            return 1
        dest_val = DEST_CODES.get(args.dest, args.dest)
        bot = WBTelegramBot(
            bot_token=token,
            proxy=args.proxy,
            proxy_change_url=args.proxy_change_url,
            mobileproxy_key=args.mobileproxy_key,
            tg_proxy=args.tg_proxy or os.getenv("WB_TG_PROXY"),
            channel_id=args.channel_id or os.getenv("WB_TG_CHANNEL"),
            dest=int(dest_val),
            workers=args.workers,
            limit=args.limit,
            max_pages=args.pages,
            enrich_cdn=not args.no_cdn,
            with_feedbacks=not args.no_feedbacks,
            tracker_db=args.db or "wb_prices.db",
        )
        bot.run_polling()
        return 0

    if args.command == "mcp":
        from wb_parser.mcp_server import WBMCPServer
        srv = WBMCPServer(
            proxy=args.proxy,
            proxy_change_url=args.proxy_change_url,
            mobileproxy_key=args.mobileproxy_key,
            cookies=args.cookies,
            wbaas_token=args.wbaas_token,
            tracker_db=args.db,
        )
        srv.run_stdio()
        return 0

    if args.command == "ai":
        return _handle_ai_command(args)

    if args.command == "drops":
        tracker = WBPriceTracker(args.db)
        drops = tracker.get_price_drops(limit=args.limit)
        if not drops:
            print("No price drops recorded yet.")
            return 0
        for d in drops:
            diff = round((d.old_price or 0) - d.price, 2)
            print(f"[{d.nm_id}] {d.name}: {d.price:,.0f} RUB (was {d.old_price:,.0f}, -{diff:,.0f} RUB)")
        return 0

    with _build_client(args) as client:
        if args.command == "upstreams":
            ping = client.ping()
            count = client.sync_upstreams()
            wallet_cfg = client.wallet.fetch_settings()
            print(json.dumps({
                "ping": ping,
                "basket_routes": count,
                "wallet_discount_pct": float(wallet_cfg.wallet_discount_pct),
                "wallet_club_pct": float(wallet_cfg.club_discount_pct),
                "wallet_max_price": float(wallet_cfg.max_price),
            }, indent=2))
            return 0

        if args.command == "wallet":
            res = client.wallet_price(args.price, use_club=args.club)
            print(json.dumps({
                "base_price": res.base_price,
                "wallet_price": res.wallet_price,
                "savings": res.savings,
                "discount_pct": res.discount_pct,
                "applied": res.applied,
                "reason": res.reason,
            }, indent=2))
            return 0

        if args.command == "rank":
            res = client.check_rank(args.target, args.query, max_pages=args.pages, sort=args.sort)
            print(res.model_dump_json(indent=2))
            if args.output:
                out_p = Path(args.output)
                if out_p.suffix.lower() == ".xlsx":
                    rank_results_to_excel([res], out_p)
                else:
                    out_p.write_text(res.model_dump_json(indent=2), encoding="utf-8")
                print(f"[+] Exported rank report -> {out_p}")
            return 0

        if args.command == "reviews":
            summary = client.analyze_reviews(
                args.target,
                only_this_color=not args.all_colors,
                limit=args.limit,
                ai_key=args.ai_key,
                ai_base_url=args.ai_url,
                ai_model=args.ai_model,
                ai_mode=args.mode,
                ai_provider=args.provider,
                ai_timeout=args.ai_timeout,
            )
            print(f"[{summary.nm_id}] {summary.product_name} (root={summary.root_id}, shard=feedbacks{summary.shard})")
            print(f"Analyzed: {summary.total_analyzed} / {summary.total_available} | Avg: {summary.avg_rating} | Mode: {summary.summary_mode}")
            if summary.size_fit:
                print(f"Size fit: {summary.size_fit}")
            print("Pros (+):", summary.top_pros)
            print("Cons (-):", summary.top_cons)
            if args.output:
                Path(args.output).write_text(summary.model_dump_json(indent=2), encoding="utf-8")
                print(f"[+] Saved review summary -> {args.output}")
            return 0

        if args.command == "card":
            prod = client.get_product(
                args.target,
                enrich_cdn=True,
                with_feedbacks=not args.no_feedbacks,
                with_price_history=args.history,
            )
            print(prod.to_json(indent=2))
            _export_results([prod], args.output)
            return 0

        if args.command == "feedbacks":
            target_num = extract_nm_id(args.target)
            if args.is_nm:
                card = client.get_card_cdn(target_num)
                root_id = card.root
            else:
                root_id = target_num
            shard = calculate_feedback_shard(root_id)
            fb = client.get_feedbacks(root_id)
            if not fb:
                print(f"No feedbacks found for root_id={root_id} (shard=feedbacks{shard})")
                return 1
            print(f"root_id={root_id} | server=feedbacks{fb.shard}.wb.ru (formula shard={shard})")
            print(f"valuation={fb.valuation} | feedbackCountWithText={fb.feedback_count} | total={fb.total_feedback_count}")
            return 0

        if args.command == "seller":
            products = client.get_seller_catalog(
                args.target,
                max_pages=args.pages,
                limit=args.limit,
                enrich_cdn=args.enrich,
                with_feedbacks=not args.no_feedbacks,
            )
            _print_products_table(products)
            exported = _export_results(products, args.output)
            _notify_cli_export(args, products, exported, f"WB Продавец {args.target}")
            return 0

        if args.command == "search":
            raw = client.search(
                args.query,
                max_pages=args.pages,
                limit=args.limit,
                enrich_cdn=args.enrich,
                with_feedbacks=args.with_feedbacks,
            )
            products = filter_products(
                raw,
                min_price=args.min_price,
                max_price=args.max_price,
                min_discount=args.min_discount,
                min_rating=args.min_rating,
            )
            _print_products_table(products)
            exported = _export_results(products, args.output)
            _notify_cli_export(args, products, exported, f"WB Поиск: {args.query}")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
