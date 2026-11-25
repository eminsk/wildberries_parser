<h1 align="center">WB SDK Pro (`wb-parser-sdk`)</h1>
<p align="center">
  <b>Modern Wildberries Python SDK, CLI, Native MCP Server & Dark-Themed Desktop GUI</b>
</p>

<p align="center">
  <b>🇬🇧 English</b> •
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README_RU.md">🇷🇺 Документация на русском</a>
</p>

[![Release](https://img.shields.io/badge/version-v2.0.0-7c3aed.svg?style=flat&logo=github)](https://github.com/eminsk/wildberries_parser)
[![Python Versions](https://img.shields.io/badge/python-3.10%20--%203.13+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![uv Powered](https://img.shields.io/badge/uv-package%20manager-DE5FE9.svg?style=flat)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/pytest-20%20passed-2ea44f.svg?style=flat&logo=pytest&logoColor=white)](https://github.com/eminsk/wildberries_parser/tree/master/tests)
[![Desktop GUI](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet.svg?style=flat)](https://github.com/eminsk/wildberries_parser#desktop-gui)
[![MCP Server](https://img.shields.io/badge/MCP-JSON--RPC%202.0-00C853.svg?style=flat)](https://github.com/eminsk/wildberries_parser#mcp-server-for-ai-agents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)

> An actively maintained, full architectural upgrade of `Duff89/wildberries_parser`.  
> Works cleanly out of the box with **modern `wbbasket.ru` CDN sharding (`basket-01..65+`)**, **exact `feedbacks1` / `feedbacks2` routing**, **Chrome TLS fingerprinting**, **SQLite price drop tracking**, **Excel `.xlsx` export**, **CustomTkinter Desktop GUI**, and a **native MCP server** for AI agents.

---

## 🛠️ What Was Fixed Compared to Upstream `Duff89/wildberries_parser`

| Component | Legacy Upstream (`v1.0`) | WB SDK Pro (`v2.0.0`) |
|---|---|---|
| **Feedbacks Routing (Issue #2)** | Hardcoded `feedbacks1.wb.ru` (50% 404 failure) | Exact WB formula: `root_id % 100 >= 50 -> feedbacks2` else `feedbacks1` + fallback |
| **Image & Card Shards** | Hardcoded up to `basket-15` (broken for modern articles) | Dynamic live sync via `cdn.wbbasket.ru/api/v3/upstreams` (`basket-01..65+`, articles up to `2.88B+`) |
| **Image Format** | Broken `.jpg` URLs on `basket-*.wb.ru` (HTTP 404) | Real live `.webp` URLs on `basket-*.wbbasket.ru` (`images/big/1.webp`) |
| **API Schema Support** | Legacy `salePriceU` only | Unified Pydantic v2 normalizing both `sizes[].price.product / basic` and `salePriceU` / CDN `card.json` |
| **Direct CDN Access** | None (fails immediately if search gateway blocks) | Direct `wbbasket.ru` `card.json` + `.webp` + `feedbacks1/2` works natively without WBAAS cookies |
| **Network Resilience** | Synchronous `requests.get`, IPv6 stalls | `curl_cffi` Chrome TLS + IPv4 failover + `AsyncWBClient` + retries with jitter + proxy rotation |
| **Interfaces** | Single Python file `parser.py` | **Modular Python Library** + **CLI** (`wb-parser`) + **Desktop GUI** (`wb-gui`) + **MCP Server** (`wb-mcp`) |
| **Exports & Tracking** | Basic CSV | Styled Excel (`.xlsx` with hyperlinks & drop highlights), CSV BOM, JSON, JSONL, SQLite `WBPriceTracker` |

---

## 📦 Installation (`uv` Recommended)

```bash
git clone https://github.com/eminsk/wildberries_parser.git
cd wildberries_parser

# Sync environment & dependencies via uv
uv sync
```

---

## ⚡ Quick Start — Python SDK (Sync & Async)

### Synchronous Client (`WBClient`)

```python
from wb_parser import WBClient, calculate_feedback_shard, to_excel

with WBClient(tracker_db="wb_prices.db") as wb:
    # 1. Fetch latest live basket-01..65+ map from cdn.wbbasket.ru
    wb.sync_upstreams()

    # 2. Fetch product card directly from wbbasket.ru CDN + sharded feedbacks
    product = wb.get_product("https://www.wildberries.ru/catalog/141217830/detail.aspx")
    print(f"{product.name} | Brand: {product.brand} | Root: {product.root}")
    print(f"Feedback shard: feedbacks{calculate_feedback_shard(product.root)}.wb.ru")
    print(f"Reviews: {product.feedback_count} (★ {product.valuation})")
    print(f"Main .webp image: {product.image_links[0]}")

    # 3. Export styled Excel spreadsheet
    to_excel([product], "result/wb_catalog.xlsx")
```

### Asynchronous Concurrent Client (`AsyncWBClient`)

```python
import asyncio
from wb_parser import AsyncWBClient

async def main():
    async with AsyncWBClient(concurrency=16) as wb:
        products = await wb.gather_cards([141217830, 339182812])
        for p in products:
            print(p.id, p.name, p.feedback_count)

asyncio.run(main())
```

### Search & Seller Catalog (with Optional Proxy / Browser Session Cookies)

```python
from wb_parser import WBClient

with WBClient(proxy="http://user:pass@ip:port") as wb:
    seller_items = wb.get_seller_catalog("https://www.wildberries.ru/seller/626520", max_pages=3)
    search_items = wb.search("беговые кроссовки", limit=50, enrich_cdn=True)
```

### Backward-Compatible `ParseWB` Drop-in

```python
from parser import ParseWB

ParseWB("https://www.wildberries.ru/catalog/141217830/detail.aspx", output_path="wb_data.xlsx").parse()
```

---

## 🖥️ Desktop GUI (`WB SDK Pro`)

Launch the dark-themed `CustomTkinter` desktop app:

```bash
uv run wb-gui
# or
uv run python run_gui.py
```

**Features inside the GUI:**
- **🔍 Парсер tab:** Paste product URLs, numeric `nm_id` articles, `/seller/...` links, or search queries; filter by min/max price, min discount %, min rating, white/black keywords; enable 24/7 interval monitoring.
- **📦 Каталог товаров tab:** Live product cards with prices, discounts, review counts (`feedbacks1/2`), clickable *"Открыть на WB ↗"* and *"CDN JSON"* buttons, plus 1-click export to **Excel `.xlsx`**, **CSV**, and **JSON**.
- **🌐 Прокси и Сессия tab:** Regional delivery selector (`dest`), HTTP/SOCKS5 proxy, MobileProxy rotation URL, optional browser `Cookie` / `x-wbaas-token`, and live ping diagnostics.
- **✈️ Telegram tab:** Decoupled Telegram alerts with separate SOCKS5/HTTP proxy support.

---

## 💻 CLI Usage (`wb-parser`)

```bash
# Test live CDN latency & fetch latest basket-01..65+ shard boundaries
uv run wb-parser upstreams

# Fetch single card from CDN + sharded feedbacks + save Excel
uv run wb-parser card https://www.wildberries.ru/catalog/141217830/detail.aspx -o item.xlsx

# Query feedbacks directly by root_id (or --is-nm for article ID)
uv run wb-parser feedbacks 181851928

# Search & export (with optional proxy/cookies)
uv run wb-parser search "велосипед" --min-price 5000 --min-rating 4.5 -o bikes.xlsx

# View SQLite tracked price drops
uv run wb-parser drops --db wb_prices.db
```

---

## 🤖 Native MCP Server (`wb-mcp`) for AI Agents

Add Wildberries search, CDN card inspection, sharded review lookup, and price-drop tools to **Claude Desktop**, **Cursor**, **Windsurf**, or **Antigravity**:

```json
{
  "mcpServers": {
    "wildberries": {
      "command": "uv",
      "args": ["--directory", "C:/proekts/wildberries_parser", "run", "wb-mcp"]
    }
  }
}
```

Available MCP tools:
- `wb_get_card` — Full CDN card metadata, `.webp` links, specs, and sharded reviews.
- `wb_get_feedbacks` — Exact `feedbacks1` vs `feedbacks2` routing by `root_id`.
- `wb_search` — Catalog search with price/discount/rating filters & Excel export.
- `wb_get_seller_catalog` — Extract full seller assortment.
- `wb_price_drops` — Query tracked price drops from SQLite.

---

## 🧪 Running Tests (`pytest`)

```bash
uv run pytest
```

All tests run cleanly via `pytest` covering sharding math (`basket-01..65+`, `feedbacks1/2`), Pydantic v2 model normalization, CDN fallbacks, SQLite price tracking, Excel formula sanitization & exports, MCP JSON-RPC 2.0 protocol, CLI, and GUI configuration persistence.

---

## 💬 Community & Support

- 📢 **Telegram Channel:** [@avito_sdk_pro](https://t.me/avito_sdk_pro)
- 🐛 **Issues & Feature Requests:** [GitHub Issues](https://github.com/eminsk/wildberries_parser/issues)
- 🌐 **Portal & Ecosystem:** [eminsk.github.io](https://eminsk.github.io/)

## 📄 License

MIT License.
