<h1 align="center">WB SDK Pro (`wb-sdk-pro`)</h1>
<p align="center">
  <b>All-in-One Wildberries Suite: Sync/Async SDK + CDN Engine + WB Wallet + Rank Tracker + Smart Reviews + Free/Paid AI (g4f / Ollama / OpenAI / DeepSeek / OpenRouter) + 12 CLI + 9 MCP Tools + 7-Tab GUI</b>
</p>

<p align="center">
  <b>🇬🇧 English</b> •
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README_RU.md">🇷🇺 Документация на русском</a>
</p>

[![PyPI Version](https://img.shields.io/pypi/v/wb-sdk-pro.svg?style=flat&logo=pypi&color=blue)](https://pypi.org/project/wb-sdk-pro/)
[![Release](https://img.shields.io/badge/release-v2.3.0-7c3aed.svg?style=flat&logo=github)](https://github.com/eminsk/wildberries_parser/releases/tag/v2.3.0)
[![Python Versions](https://img.shields.io/badge/python-3.8%20--%203.16+%20%7C%20PyPy%20%7C%20No--GIL-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![uv Powered](https://img.shields.io/badge/uv-package%20manager-DE5FE9.svg?style=flat)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/pytest-33%20passed%20%C3%97%2018%20runtimes-2ea44f.svg?style=flat&logo=pytest&logoColor=white)](https://github.com/eminsk/wildberries_parser/tree/master/tests)
[![Desktop GUI](https://img.shields.io/badge/Desktop%20GUI-7%20Tabs%20%7C%20CustomTkinter-blueviolet.svg?style=flat)](https://github.com/eminsk/wildberries_parser#desktop-gui)
[![MCP Server](https://img.shields.io/badge/MCP-9%20Tools%20JSON--RPC%202.0-00C853.svg?style=flat)](https://github.com/eminsk/wildberries_parser#mcp-server-for-ai-agents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)

> **Unified 4-in-1 Wildberries Architecture** combining `wildberries_parser` (with drop-in `ParseWB`, `Item`, `Items`, `Feedback` compatibility) + `wb_rank` + `wb_smart_review` + **`testg4f` Hybrid Free/Paid AI Engine** into one pure-Python Sync/Async SDK, 12-command CLI (`wb-parser` / `wb-sdk`), 9-tool MCP Server (`wb-mcp`), and optional 7-tab Desktop GUI (`wb-gui`).

---

## 🐍 Python Compatibility

| Runtime | Versions | Status |
|---|---|---|
| **CPython** | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16 | ✅ All 33 tests pass (Win / Linux / macOS) |
| **Free-Threaded (No-GIL)** | 3.13t, 3.14t, 3.15t, 3.16t | ✅ Thread-safe (`RLock` + `wb_parser._model`) |
| **PyPy** | 3.8 (Linux CI), 3.9, 3.10, 3.11, 3.12 | ✅ Pure-Python core passes without C/Rust deps |

Core SDK, CLI, and MCP Server install cleanly across **18 Python runtimes** using pure-Python `wb_parser._model` and automatic HTTP transport selection (`curl_cffi` Chrome 124 TLS if installed → `httpx[http2]` → `requests`).

---

## 🚀 Unified Modules & Features

| Module | What It Solves | Highlights |
|---|---|---|
| **Catalog & CDN Engine** (`wb_parser.shards`, `client`) | Broken `basket-15` caps, 404 `.jpg` links & Issue #2 (`feedbacks1/2`) | Live sync (`basket-01..65+` & math extrapolation beyond vol `28,805`), real `.webp` URLs, `root_id % 100 >= 50` feedback routing with alternate-shard fallback, direct `card.json` & `price-history.json` without WBAAS blocks |
| **Sync & Async Clients** (`WBClient`, `AsyncWBClient`, `ParseWB`) | Concurrent batch scraping, search & legacy code compatibility | `WBClient` (mixed targets via `scrape_targets`), `AsyncWBClient` (`gather_cards` with semaphore concurrency), and Duff89-compatible `ParseWB` / `Item` / `Items` / `Feedback` aliases |
| **Resilient Transport** (`wb_parser.http`) | IPv6 CDN stalls, rate limits & mobile proxy failover | `curl_cffi` Chrome TLS (`[tls]`) → `httpx[http2]` → `requests` fallback, forced IPv4, exponential backoff with jitter, HTTP/SOCKS5 proxy, MobileProxy IP rotation (`proxy_change_url`) |
| **WB Wallet Pricing** (`wb_parser.wallet`) | Calculating real buyer checkout price with `WB Кошелёк` / `ВБ Клуб` | Fetches live `default-payment.json` + `settings-front.json` thresholds (`wlt1DiscountDisplayMaxPrice`, `pricesDeltaToShowSale`) with `geobasket` mirror, floors prices via `ROUND_FLOOR` |
| **Search Rank Tracker** (`wb_parser.rank`) | Monitoring keyword positions across WB search (`wb_rank`) | Scans pages `1..N` (`popular`, `pricedown`, `priceup`, `rate`, `newly`), computes global rank + page slot + SQLite `rank_delta` (`▲`/`▼`), batch checks (`check_batch`), styled Excel export |
| **Smart Review & Free/Paid AI Engine** (`wb_parser.reviews`, `wb_parser.ai`) | Extracting buyer pros, cons & size fit with zero-key Free OR Paid LLMs (`wb_smart_review` + `testg4f`) | Filters by `nm_id` (fallback `root_id`), offline clustering + **Free** (`g4f` auto-fallback, `Ollama`, `LM Studio`), **Hybrid** (`OpenRouter` `:free`/paid, `Groq`, `Gemini`), **Paid** (`OpenAI`, `DeepSeek`, `ProxyAPI`) + provider health checks (`test_ai_provider`, `quick_scan`) |
| **Price Tracker, Config & Alerts** (`tracker`, `config`, `export`, `telegram`) | Price drops, multi-format reports & Telegram monitoring | Thread-safe SQLite `wb_latest_prices` / `wb_price_history`, `.xlsx` (hyperlinks & drop highlight), UTF-8 BOM `.csv`, `.json`, `.jsonl`, `pandas.DataFrame` (`[dataframe]`), `.json`/`.toml` `WBConfig`, isolated Telegram proxy |
| **Desktop GUI (`wb-gui`)** | Visual control center (`[gui]` extra) | Dark `CustomTkinter` UI with 7 tabs (Parser, Catalog Feed, Rank Tracker, Smart Reviews with Free/Paid AI selector & live ⚡ check, Proxy & Session, Telegram, Logs) and `storage/gui_config.json` persistence |
| **Native MCP Server (`wb-mcp`)** | Giving AI agents live Wildberries market intelligence | 9 JSON-RPC 2.0 tools (`2025-11-25` / `2025-06-18` / `2024-11-05`) including `wb_ai_providers`, `structuredContent`, and env vars (`WB_PROXY`, `WB_TRACKER_DB`, `WB_AI_MODE`, `WB_AI_PROVIDER`) |

> **Note on WB anti-bot (WBAAS 498/403):** Direct CDN endpoints (`wbbasket.ru` `card.json`, `upstreams`, `.webp`, `price-history.json`, `feedbacks1/2.wb.ru`, and Wallet configs) work directly without proxies or cookies. Gateway search, seller catalogs, and live `__internal/u-card` checkout prices may require an RU residential/mobile proxy, `cookies`, or `x-wbaas-token`.

---

## 📦 Installation

### PyPI (`uv` / `pip`)

```bash
# Core SDK, 12-command CLI (wb-parser / wb-sdk), and 9-tool MCP server (wb-mcp)
uv add wb-sdk-pro

# Run Desktop GUI directly without installing into your project (requires [gui] extra)
uvx --from "wb-sdk-pro[gui]" wb-gui

# Or via pip
pip install wb-sdk-pro
```

### Optional Extras

```bash
# Free zero-key AI providers via g4f (Pollinations, Airforce, Cerebras, DeepInfra, etc.)
uv add "wb-sdk-pro[ai]"        # alias: "wb-sdk-pro[free-ai]"

# 7-Tab Desktop GUI (adds customtkinter, Pillow, curl_cffi)
uv add "wb-sdk-pro[gui]"

# Chrome TLS fingerprinting for HTTP/async requests (adds curl_cffi)
uv add "wb-sdk-pro[tls]"

# pandas DataFrame export via to_dataframe() (adds pandas)
uv add "wb-sdk-pro[dataframe]"   # or "wb-sdk-pro[pandas]"

# Everything (GUI + Free AI [g4f] + Chrome TLS + pandas)
uv add "wb-sdk-pro[all]"
```

### Debian / Ubuntu (APT PPA)

Installs the core pure-Python SDK, CLI (`wb-parser` / `wb-sdk`), and MCP server (`wb-mcp`):

```bash
# 1-line setup (adds eminsk PPA + GPG key)
curl -sS https://eminsk.github.io/ppa/setup.sh | sudo bash

# Install
sudo apt install python3-wb-sdk-pro
```

### From Source

```bash
git clone https://github.com/eminsk/wildberries_parser.git
cd wildberries_parser
uv sync              # core SDK + CLI + MCP
uv sync --extra gui  # include Desktop GUI + Chrome TLS
```

---

## ⚡ Quick Start — Python Library

### 1. Card Inspection, Sharded Feedbacks & Multi-Format Export

```python
from wb_parser import DEST_CODES, WBClient, to_csv, to_excel, to_json

with WBClient(dest=DEST_CODES["Москва"], tracker_db="wb_prices.db") as wb:
    wb.sync_upstreams()
    item = wb.get_product(
        "https://www.wildberries.ru/catalog/141217830/detail.aspx",
        with_price_history=True,
    )
    print(item.name, item.brand, f"Reviews: {item.feedback_count} (★ {item.valuation})")
    to_excel([item], "result/wb_catalog.xlsx")
    to_csv([item], "result/wb_catalog.csv")
    to_json([item], "result/wb_catalog.json")
```

### 2. Async Batch Fetching (`AsyncWBClient`)

```python
import asyncio
from wb_parser import AsyncWBClient

async def main():
    async with AsyncWBClient(concurrency=16, tracker_db="wb_prices.db") as wb:
        products = await wb.gather_cards([141217830, 181851928])
        for p in products:
            print(p.id, p.name, p.feedback_count)

asyncio.run(main())
```

### 3. WB Wallet Discount Price (`wb_parser.wallet`)

```python
from wb_parser import WBClient

with WBClient() as wb:
    res = wb.wallet_price(4990)
    club = wb.wallet_price(4990, use_club=True)
    print(f"Base: {res.base_price} ₽ -> WB Wallet (-{res.discount_pct}%): {res.wallet_price} ₽")
    print(f"WB Club (-{club.discount_pct}%): {club.wallet_price} ₽")
```

### 4. Search Rank Tracking (`wb_parser.rank`)

```python
from wb_parser import WBClient, rank_results_to_excel

with WBClient(cookies="x_wbaas_token=...", proxy="http://user:pass@ip:port") as wb:
    rank = wb.check_rank(141217830, "кроссовки sb dunk", max_pages=3, sort="popular")
    print(f"Position: #{rank.position} (Page {rank.page}, Slot #{rank.page_position}, Delta: {rank.rank_delta})")
    rank_results_to_excel([rank], "result/ranks.xlsx")
```

### 5. Smart Review Summary & Hybrid Free / Paid AI (`wb_parser.reviews` & `wb_parser.ai`)

```python
from wb_parser import AIClient, WBClient, list_ai_providers, test_ai_provider

with WBClient() as wb:
    # A) Instant Zero-API offline analysis
    summary = wb.analyze_reviews(141217830, only_this_color=True, limit=100)
    print(summary.summary_mode, summary.top_pros, summary.top_cons)

    # B) 100% Free zero-key AI via g4f auto-fallback (`uv add "wb-sdk-pro[ai]"`)
    free_summary = wb.analyze_reviews(141217830, ai_mode="free", ai_provider="g4f")

    # C) Local Free Ollama (`http://localhost:11434/v1`, no API key required)
    local_summary = wb.analyze_reviews(141217830, ai_mode="local", ai_provider="ollama", ai_model="llama3.2")

    # D) Paid / Hybrid APIs (OpenAI, DeepSeek, OpenRouter `:free`/paid, ProxyAPI, Groq, Gemini)
    paid_summary = wb.analyze_reviews(
        141217830,
        ai_mode="paid",
        ai_provider="deepseek",      # auto-resolves https://api.deepseek.com/v1 + DEEPSEEK_API_KEY
        ai_key="sk-...",
    )

# Provider Discovery & Health-Check (from testg4f):
providers = list_ai_providers(tier="all")
health = test_ai_provider("Pollinations", mode="free", timeout=10.0)
print(health.success, health.latency_seconds, health.hint)

ai = AIClient(mode="auto")  # uses paid env key if set, otherwise free g4f pool
reply = ai.chat("Назови 3 совета для карточки на Wildberries")
print(reply.provider, reply.tier, reply.content)
```

Supported built-in AI presets & environment variables:

| Preset Slug | Tier | Default Model | Env Variable | Base URL |
|---|---|---|---|---|
| `g4f` / `Pollinations`, `Cerebras`, ... | **Free** (No Key) | provider default | — *(requires `[ai]`)* | dynamic `g4f` providers |
| `ollama` | **Local Free** | `llama3.2` | `OLLAMA_BASE_URL` | `http://localhost:11434/v1` |
| `lmstudio` | **Local Free** | `local-model` | `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` |
| `openrouter` | **Hybrid** (`:free` + Paid) | `deepseek/deepseek-chat-v3-0324:free` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `groq` | **Hybrid** (Free Tier + Paid) | `llama-3.3-70b-versatile` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` |
| `gemini` | **Hybrid** (Free Tier + Paid) | `gemini-2.5-flash` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `openai` | **Paid** | `gpt-4o-mini` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `deepseek` | **Paid** | `deepseek-chat` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` |
| `proxyapi` | **Paid** (RU) | `gpt-4o-mini` | `PROXYAPI_API_KEY` | `https://api.proxyapi.ru/openai/v1` |

### 6. Config Files (`JSON` / `TOML`), Telegram Alerts & Legacy `ParseWB`

```python
from wb_parser import ParseWB, TelegramNotifier, WBConfig, WBClient

cfg = WBConfig.from_file("wb.toml")  # or wb.json
notifier = TelegramNotifier(bot_token="...", chat_id="...", proxy="socks5://127.0.0.1:1080")
with WBClient(dest=cfg.dest, tracker_db=cfg.tracker_db) as wb:
    item = wb.get_product(141217830)
    notifier.send_product(item)

# Backward-compatible Duff89 API:
ParseWB("https://www.wildberries.ru/seller/626520", output_path="seller.xlsx").parse()
```

---

<a id="desktop-gui"></a>
## 🖥️ Desktop GUI (`WB SDK Pro` — 7 Tabs)

Install with `[gui]` extra (`uv add "wb-sdk-pro[gui]"` or `uv sync --extra gui`), then launch:

```bash
uv run wb-gui
# or from cloned repo:
uv run python run_gui.py
```

1. **🔍 Парсер**: Scrape product links, `nm_id` articles, `/seller/...` stores, or search queries with price/discount/rating/whitelist/blacklist keyword filters and 24/7 loop monitoring.
2. **📦 Каталог товаров**: Live cards displaying price, `💳 WB Wallet` price, discount badge, price drop alert (`📉`), clickable *"Открыть на WB ↗"*, and 1-click export to **Excel `.xlsx`**, **CSV**, and **JSON**.
3. **📈 Позиции (Rank)**: Paste `nm_id : keyword` pairs, choose sort order (`popular`, `pricedown`, `priceup`, `rate`, `newly`), scan pages `1..N`, see position movement (`▲`/`▼`), and export rank reports to Excel.
4. **💬 Умные отзывы**: Enter any WB URL or `nm_id` to extract buyer reviews, rating histogram, size fit stats, and side-by-side **✅ Pros** & **❌ Cons** (instant offline mode OR optional LLM API).
5. **🌐 Прокси и Сессия**: Choose delivery region (`dest`), configure HTTP/SOCKS5 proxy, MobileProxy rotation URL, cookies/`x_wbaas_token`, and ping CDN + live WB Wallet discount rates in 1 click.
6. **✈️ Telegram**: Forward product cards & alerts via a decoupled Telegram proxy.
7. **📋 Журнал**: Live execution log (all settings persist in `storage/gui_config.json`).

---

## 💻 CLI Commands (`wb-parser` / `wb-sdk` — 12 Subcommands)

All data commands support `--dest`, `--proxy`, `--proxy-change-url`, `--cookies`, `--wbaas-token`, and `--db`:

```bash
# 1. Sync live CDN shards (01..65+) and check WB Wallet / WB Club discount %
uv run wb-parser upstreams

# 2. Fetch product card (CDN card.json + feedbacks1/2 + .webp + optional --history) & save Excel
uv run wb-parser card https://www.wildberries.ru/catalog/141217830/detail.aspx --history -o item.xlsx

# 3. Search catalog with price/discount/rating filters and optional CDN enrichment
uv run wb-parser search "кроссовки" --pages 2 --min-discount 20 -o search.xlsx

# 4. Scrape all products for a seller URL, supplier ID, or sample product URL
uv run wb-parser seller 626520 --pages 5 --enrich -o seller.xlsx

# 5. Calculate exact live WB Wallet (or --club) discounted price
uv run wb-parser wallet 4990 --club

# 6. Run Smart Review Analyzer (offline, free g4f, local Ollama, or paid OpenAI/DeepSeek/OpenRouter)
uv run wb-parser reviews 141217830 --mode free --limit 60 -o reviews.json
uv run wb-parser reviews 141217830 --mode paid --provider deepseek --ai-key sk-...

# 7. Track product search rank across pages (--sort popular|pricedown|priceup|rate|newly)
uv run wb-parser rank 141217830 "кроссовки dunk" --pages 3 -o ranks.xlsx

# 8. Discover, health-check & query Free (g4f/Ollama) + Paid AI providers (testg4f integration)
uv run wb-parser ai --list
uv run wb-parser ai --quick-scan
uv run wb-parser ai -p Pollinations --test --timeout 10
uv run wb-parser ai --ask "Выдели плюсы товара" --mode free

# 9. Check sharded feedbacks directly (--is-nm resolves nm_id -> root_id via CDN first)
uv run wb-parser feedbacks 181851928 --is-nm

# 10. View SQLite price drops
uv run wb-parser drops --db wb_prices.db

# 11. Start MCP JSON-RPC 2.0 server over stdio
uv run wb-parser mcp

# 12. Launch CustomTkinter Desktop GUI (requires [gui] extra)
uv run wb-parser gui
```

---

<a id="mcp-server-for-ai-agents"></a>
## 🤖 Native MCP Server (`wb-mcp` — 9 Tools)

Supports MCP protocol versions `2025-11-25`, `2025-06-18`, and `2024-11-05` (`serverInfo.name = "wb-parser-mcp"`), returning structured JSON alongside readable text:

```json
{
  "mcpServers": {
    "wildberries": {
      "command": "uvx",
      "args": ["--from", "wb-sdk-pro", "wb-mcp"],
      "env": {
        "WB_TRACKER_DB": "wb_prices.db",
        "WB_AI_MODE": "auto"
      }
    }
  }
}
```

Optional environment variables: `WB_PROXY`, `WB_PROXY_CHANGE_URL`, `WB_COOKIES`, `WB_WBAAS_TOKEN`, `WB_TRACKER_DB`, `WB_AI_MODE`, `WB_AI_PROVIDER`, `WB_AI_MODEL`, `WB_AI_BASE_URL`, `WB_AI_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `PROXYAPI_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`.

Available tools: `wb_get_card`, `wb_get_feedbacks`, `wb_search`, `wb_get_seller_catalog`, `wb_price_drops`, `wb_wallet_price`, `wb_check_rank`, `wb_smart_reviews`, `wb_ai_providers`.

---

## 🧪 Tests (`pytest`)

```bash
uv run pytest
```

**33 tests passing** across **18 Python runtimes** in CI on **Linux, Windows & macOS** (CPython 3.8–3.16, Free-Threaded 3.13t–3.16t, PyPy 3.8–3.12), covering shard math, models, TOML/JSON config, sync/async clients, WB Wallet rounding & thresholds, multi-page rank tracking & history deltas, smart review color filtering & pros/cons extraction, Free (`g4f`/Ollama) & Paid/Hybrid AI routing, health-check diagnostics, Excel/CSV exports, MCP tools (9 tools + `WB_TRACKER_DB`), CLI (12 commands), GUI config/missing-extra handling, and No-GIL thread safety.

## 📄 License

MIT License.
