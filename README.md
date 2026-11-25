<h1 align="center">WB SDK Pro (`wb-sdk-pro`)</h1>
<p align="center">
  <b>All-in-One Wildberries Suite: Catalog Parser + WB Wallet Pricing + Search Rank Tracker + Smart Review Analyzer + Desktop GUI &amp; MCP Server</b>
</p>

<p align="center">
  <b>🇬🇧 English</b> •
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README_RU.md">🇷🇺 Документация на русском</a>
</p>

[![PyPI Version](https://img.shields.io/pypi/v/wb-sdk-pro.svg?style=flat&logo=pypi&color=blue)](https://pypi.org/project/wb-sdk-pro/)
[![Release](https://img.shields.io/badge/release-v2.1.1-7c3aed.svg?style=flat&logo=github)](https://github.com/eminsk/wildberries_parser/releases/tag/v2.1.1)
[![Python Versions](https://img.shields.io/badge/python-3.10%20--%203.13+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![uv Powered](https://img.shields.io/badge/uv-package%20manager-DE5FE9.svg?style=flat)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/pytest-24%20passed-2ea44f.svg?style=flat&logo=pytest&logoColor=white)](https://github.com/eminsk/wildberries_parser/tree/master/tests)
[![Desktop GUI](https://img.shields.io/badge/Desktop%20GUI-7%20Tabs%20%7C%20CustomTkinter-blueviolet.svg?style=flat)](https://github.com/eminsk/wildberries_parser#desktop-gui)
[![MCP Server](https://img.shields.io/badge/MCP-8%20Tools%20JSON--RPC%202.0-00C853.svg?style=flat)](https://github.com/eminsk/wildberries_parser#mcp-server-for-ai-agents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)

> **Unified 3-in-1 Wildberries Architecture** upgrading and merging `wildberries_parser` + `wb_rank` + `wb_smart_review` into one modular, type-safe SDK, Desktop App, CLI, and MCP Server.

---

## 🚀 Unified Modules & Features

| Module | What It Solves | Highlights |
|---|---|---|
| **Catalog & CDN Engine** (`wb_parser.shards`, `client`) | Broken `basket-15` caps, 404 `.jpg` links & Issue #2 (`feedbacks1/2`) | Dynamic live sync (`basket-01..65+`, articles up to `2.88B+`), real `.webp` URLs, `root_id % 100 >= 50` feedback routing, direct `card.json` without WBAAS blocks |
| **WB Wallet Pricing** (`wb_parser.wallet`) | Calculating real buyer checkout price with `WB Кошелёк` / `ВБ Клуб` | Fetches live `default-payment.json` + `settings-front.json` thresholds (`wlt1DiscountDisplayMaxPrice`), floors prices via `ROUND_FLOOR` |
| **Search Rank Tracker** (`wb_parser.rank`) | Monitoring keyword positions across WB search (`wb_rank`) | Scans pages `1..N` (Top 100–500+), saves SQLite history, calculates position deltas (`▲ +5` / `▼ -3`), exports styled Excel `.xlsx` |
| **Smart Review Analyzer** (`wb_parser.reviews`) | Extracting buyer pros, cons & size fit (`wb_smart_review`) | Filters reviews by exact `nm_id` color or whole `root_id`, runs **instant Zero-API offline pros/cons/size analysis** OR optional OpenAI-compatible LLM summary |
| **Desktop GUI (`wb-gui`)** | Visual control center without touching terminal | Dark `CustomTkinter` UI with 7 tabs (Parser, Catalog Feed, Rank Tracker, Smart Reviews, Proxy & Session, Telegram, Logs) |
| **Native MCP Server (`wb-mcp`)** | Giving AI agents live Wildberries market intelligence | 8 JSON-RPC 2.0 tools for Claude Desktop, Cursor, Windsurf, and Antigravity |

---

## 📦 Installation (`uv` / `pip`)

```bash
# Using uv (recommended)
uv add wb-sdk-pro

# Or run GUI / CLI ephemerally via uvx
uvx --from wb-sdk-pro wb-gui

# Or via pip
pip install wb-sdk-pro
```

From source:
```bash
git clone https://github.com/eminsk/wildberries_parser.git
cd wildberries_parser
uv sync
```

---

## ⚡ Quick Start — Python Library

### 1. Card Inspection, Sharded Feedbacks & Excel Export

```python
from wb_parser import WBClient, to_excel

with WBClient(tracker_db="wb_prices.db") as wb:
    wb.sync_upstreams()
    item = wb.get_product("https://www.wildberries.ru/catalog/141217830/detail.aspx")
    print(item.name, item.brand, f"Reviews: {item.feedback_count} (★ {item.valuation})")
    to_excel([item], "result/wb_catalog.xlsx")
```

### 2. WB Wallet Discount Price (`wb_parser.wallet`)

```python
from wb_parser import WBClient

with WBClient() as wb:
    res = wb.wallet_price(4990)
    print(f"Base: {res.base_price} ₽ -> With WB Wallet (-{res.discount_pct}%): {res.wallet_price} ₽")
```

### 3. Search Rank Tracking (`wb_parser.rank`)

```python
from wb_parser import WBClient, rank_results_to_excel

with WBClient(cookies="x_wbaas_token=...", proxy="http://user:pass@ip:port") as wb:
    rank = wb.check_rank(141217830, "кроссовки sb dunk", max_pages=3)
    print(f"Position: #{rank.position} (Page {rank.page}, Delta: {rank.rank_delta})")
    rank_results_to_excel([rank], "result/ranks.xlsx")
```

### 4. Smart Review Summary (`wb_parser.reviews`)

```python
from wb_parser import WBClient

with WBClient() as wb:
    summary = wb.analyze_reviews(141217830, only_this_color=True, limit=100)
    print("Size fit:", summary.size_fit)
    print("Pros:", summary.top_pros)
    print("Cons:", summary.top_cons)

    # Optional OpenAI / DeepSeek / ProxyAPI summarization:
    # summary = wb.analyze_reviews(141217830, ai_key="sk-...", ai_base_url="https://api.openai.com/v1")
```

---

## 🖥️ Desktop GUI (`WB SDK Pro` — 7 Tabs)

```bash
uv run wb-gui
# or
uv run python run_gui.py
```

1. **🔍 Парсер**: Scrape product links, `nm_id` articles, `/seller/...` stores, or search queries with price/discount/rating/keyword filters and 24/7 monitoring.
2. **📦 Каталог товаров**: Live cards displaying price, `💳 WB Wallet` price, discount badge, price drop alert (`📉`), clickable *"Открыть на WB ↗"*, and 1-click export to **Excel `.xlsx`**, **CSV**, and **JSON**.
3. **📈 Позиции (Rank)**: Paste `nm_id : keyword` pairs, scan Top 100–500+, see position movement (`▲`/`▼`), and export rank reports to Excel.
4. **💬 Умные отзывы**: Enter any WB URL or `nm_id` to extract buyer reviews, rating histogram, size fit stats, and side-by-side **✅ Pros** & **❌ Cons** (instant offline mode OR optional LLM API).
5. **🌐 Прокси и Сессия**: Choose delivery region (`dest`), configure HTTP/SOCKS5 proxy, rotation URL, `x_wbaas_token` cookie, and ping CDN + live WB Wallet discount rates in 1 click.
6. **✈️ Telegram**: Forward product cards & alerts via a decoupled Telegram proxy.
7. **📋 Журнал**: Live execution log.

---

## 💻 CLI Commands (`wb-parser`)

```bash
# 1. Sync live CDN shards (01..65+) and check WB Wallet discount %
uv run wb-parser upstreams

# 2. Fetch product card (CDN card.json + feedbacks1/2 + .webp links) & save Excel
uv run wb-parser card https://www.wildberries.ru/catalog/141217830/detail.aspx -o item.xlsx

# 3. Calculate exact live WB Wallet discounted price
uv run wb-parser wallet 4990

# 4. Run Smart Review Analyzer (works directly without proxy or AI key!)
uv run wb-parser reviews 141217830 --limit 60

# 5. Track product search rank across pages
uv run wb-parser rank 141217830 "кроссовки dunk" --pages 3 -o ranks.xlsx

# 6. Check sharded feedbacks directly
uv run wb-parser feedbacks 181851928

# 7. View SQLite price drops
uv run wb-parser drops --db wb_prices.db
```

---

## 🤖 Native MCP Server (`wb-mcp` — 8 Tools)

```json
{
  "mcpServers": {
    "wildberries": {
      "command": "uvx",
      "args": ["--from", "wb-sdk-pro", "wb-mcp"]
    }
  }
}
```

Available tools: `wb_get_card`, `wb_get_feedbacks`, `wb_search`, `wb_get_seller_catalog`, `wb_price_drops`, `wb_wallet_price`, `wb_check_rank`, `wb_smart_reviews`.

---

## 🧪 Tests (`pytest`)

```bash
uv run pytest
```

**24 tests passing** covering shard math, models, sync/async clients, WB Wallet rounding & thresholds, multi-page rank tracking & history deltas, smart review color filtering & pros/cons extraction, Excel exports, MCP tools, CLI, and GUI config persistence.

## 📄 License

MIT License.
