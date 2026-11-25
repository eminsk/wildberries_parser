<h1 align="center">WB SDK Pro (`wb-sdk-pro`)</h1>
<p align="center">
  <b>Единая экосистема для Wildberries: Sync/Async SDK + CDN + WB Кошелёк + Позиции (Rank) + Умные отзывы + Бесплатные/Платные AI (`g4f` / Ollama / OpenAI / DeepSeek / OpenRouter) + 12 команд CLI + MCP (9 инструментов) + 7-Tab GUI</b>
</p>

<p align="center">
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README.md">🇬🇧 English</a> •
  <b>🇷🇺 Документация на русском</b>
</p>

> Современное объединение 4 проектов (`wildberries_parser` с совместимостью `ParseWB` / `Item` / `Items` / `Feedback` + `wb_rank` + `wb_smart_review` + **`testg4f`**) в единую потокобезопасную библиотеку (`uv add wb-sdk-pro`), CLI на 12 подкоманд (`wb-parser` / `wb-sdk`), MCP-сервер (`wb-mcp`, 9 инструментов) и опциональный 7-вкладочный GUI (`wb-gui`).

---

## 🐍 Совместимость с Python

| Среда | Версии | Статус |
|---|---|---|
| **CPython** | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16 | ✅ Все 34 теста (Win / Linux / macOS) |
| **Free-Threaded (No-GIL)** | 3.13t, 3.14t, 3.15t, 3.16t | ✅ Потокобезопасно (`RLock` + `wb_parser._model`) |
| **PyPy** | 3.8 (Linux CI), 3.9, 3.10, 3.11, 3.12 | ✅ Все 34 теста |

Ядро SDK, CLI и MCP-сервера написано на чистом Python (`wb_parser._model` вместо `pydantic`) с каскадным HTTP-транспортом (`curl_cffi` с TLS Chrome 124 если установлен → `httpx[http2]` → `requests`), поэтому устанавливается и работает на **18 рантаймах Python** без Rust/C-зависимостей в ядре.

---

## 🚀 Что объединено в одном проекте (`v2.3.1`)

1. **Ядро парсера, Async-клиент и CDN-роутер (`shards.py`, `client.py`, `http.py`):**
   - Исправлена маршрутизация отзывов **`feedbacks1` / `feedbacks2`** по точной формуле `root_id % 100 >= 50` (с резервным переключением на второй шард).
   - Поддержка **всех 65+ корзин (`basket-01..65+`)** + математическая экстраполяция выше `vol 28,805` и живая синхронизация карты с `https://cdn.wbbasket.ru/api/v3/upstreams`.
   - Актуальные фото **`.webp`** на `wbbasket.ru`, история цен `price-history.json` и прямой сбор карточек из CDN `card.json` **без банов WBAAS 498 и без прокси**.
   - Синхронный `WBClient` (включая смешанный сбор `scrape_targets`), асинхронный `AsyncWBClient` (`gather_cards` с ограничением конкурентности) и совместимая обёртка `ParseWB` от Duff89.
   - Устойчивый HTTP-слой: принудительный IPv4, HTTP/SOCKS5-прокси, ротация IP (`proxy_change_url`), опциональный Chrome TLS через `[tls]` (`curl_cffi`), экспоненциальный backoff с джиттером.

2. **Калькулятор цены с WB Кошельком (`wallet.py`, из `wb_rank`):**
   - Забирает актуальные ставки из `default-payment.json` («Незалогиненный кошелёк» и «ВБ Клуб») и лимиты из `settings-front.json` (`wlt1DiscountDisplayMaxPrice`, `pricesDeltaToShowSale`) с резервным зеркалом `geobasket` и округлением `ROUND_FLOOR`.
   - Поддерживает расчёт через `WB Кошелёк` и `ВБ Клуб` (`use_club=True`), добавляет `Цена с WB Кошельком (₽)` в карточки, Excel, CSV и Telegram-уведомления.

3. **Мониторинг позиций в поиске (`rank.py`, из `wb_rank`):**
   - Сканирует страницы поиска `1..N` с выбором сортировки (`popular`, `pricedown`, `priceup`, `rate`, `newly`), вычисляет сквозную позицию и место на странице (`page_position`).
   - Поддерживает пакетную проверку (`check_batch`), сохраняет историю в SQLite (`wb_rank_history`) и считает динамику (`▲ +5` / `▼ -3`).
   - Выгружает отчёты по позициям в стильный Excel (`.xlsx`) через `rank_results_to_excel`.

4. **Умные отзывы + Гибридный движок Бесплатных/Платных AI (`reviews.py`, `ai.py`, из `wb_smart_review` + `testg4f`):**
   - Переводит `nm_id` → `root_id` через CDN `card.json` и забирает отзывы с `feedbacks1/2`, фильтрует по цвету (`nm_id`) или всей карточке (`root_id`).
   - **Без ключа и без интернета (Оффлайн):** статистика размерности (`matchingSize`), оценки 1★–5★, теги (`bables_tags`) и группировка плюсов/минусов.
   - **Бесплатные модели (без API-ключей, `wb-sdk-pro[ai]`):** интеграция `g4f` — каталог провайдеров (`Yqcloud`, `Airforce`, `LLM7`, `GLM`, `DeepInfra`, `Cerebras` и др.), диагностика ошибок/задержки (`Health Check` 401/402/403/Timeout), автоперебор живых провайдеров + бесплатный локальный **Ollama** (`OLLAMA_BASE_URL`) / **LM Studio**.
   - **Платные и гибридные API:** встроенные пресеты **OpenAI** (`OPENAI_API_KEY`), **DeepSeek** (`DEEPSEEK_API_KEY`), **OpenRouter** (`OPENROUTER_API_KEY`, включая модели `:free`), **ProxyAPI** (`PROXYAPI_API_KEY`), **Groq** (`openai/gpt-oss-20b`, `GROQ_API_KEY`), **Google Gemini** (`gemini-3.8-flash`, `GEMINI_API_KEY`) или любой кастомный `base_url`.

5. **Трекер цен, экспорт, конфиги и Telegram (`tracker.py`, `export.py`, `config.py`, `telegram.py`):**
   - Потокобезопасная история цен и отслеживание снижения цены в SQLite (`wb_latest_prices`, `wb_price_history`).
   - Экспорт в **Excel `.xlsx`** (с гиперссылками, защитой от CSV/Excel-инъекций и зелёным выделением падений цен), **CSV UTF-8 BOM**, **JSON**, **JSONL** и `pandas.DataFrame` (опциональный `[dataframe]`).
   - Загрузка настроек `WBConfig.from_file()` из **`.json`** и **`.toml`** (с `tomli` для Python <3.11) + справочник регионов `DEST_CODES`.
   - Отправка HTML-карточек и файлов-отчётов в Telegram через изолированный прокси (`TelegramNotifier`).

> **Важно про антибот Wildberries (WBAAS 498/403):** Прямой CDN (`wbbasket.ru`: `card.json`, `upstreams`, `.webp`, `price-history.json`, `feedbacks1/2.wb.ru` и ставки WB Кошелька) работает напрямую без прокси и cookies. Поиск, каталог продавца и живые цены checkout (`__internal/u-search`, `u-card`) при запросах с серверных/зарубежных IP могут требовать RU/мобильный прокси, `cookies` или `x-wbaas-token`.

---

## 📦 Установка

### PyPI (`uv` / `pip`)

```bash
# Базовый SDK, 12 команд CLI (wb-parser / wb-sdk) и MCP-сервер (wb-mcp)
uv add wb-sdk-pro

# Мгновенный запуск GUI через uvx (требуется опция [gui])
uvx --from "wb-sdk-pro[gui]" wb-gui

# Или через pip
pip install wb-sdk-pro
```

### Дополнительные опции (Extras)

```bash
# Бесплатные AI-модели без API-ключей через g4f (Pollinations, Cerebras и др.)
uv add "wb-sdk-pro[ai]"        # или "wb-sdk-pro[free-ai]"

# Desktop GUI (customtkinter, Pillow, curl_cffi)
uv add "wb-sdk-pro[gui]"

# Chrome 124 TLS движок для HTTP и async-запросов (curl_cffi)
uv add "wb-sdk-pro[tls]"

# Экспорт в pandas.DataFrame через to_dataframe()
uv add "wb-sdk-pro[dataframe]"   # или "wb-sdk-pro[pandas]"

# Всё сразу (GUI + Free AI g4f + Chrome TLS + pandas)
uv add "wb-sdk-pro[all]"
```

### Debian / Ubuntu (APT PPA)

Устанавливает ядро SDK на чистом Python, CLI (`wb-parser` / `wb-sdk`) и MCP-сервер (`wb-mcp`):

```bash
# Настройка PPA в 1 строку
curl -sS https://eminsk.github.io/ppa/setup.sh | sudo bash

# Установка
sudo apt install python3-wb-sdk-pro
```

### Из исходников

```bash
git clone https://github.com/eminsk/wildberries_parser.git
cd wildberries_parser
uv sync              # ядро SDK + CLI + MCP
uv sync --extra ai   # с бесплатным движком g4f
uv sync --extra gui  # с Desktop GUI и Chrome TLS
uv sync --all-extras # всё сразу
```

---

## ⚡ Быстрый старт — Python SDK

### 1. Карточка товара, шардированные отзывы и экспорт

```python
from wb_parser import DEST_CODES, WBClient, to_csv, to_excel, to_json

with WBClient(dest=DEST_CODES["Москва"], tracker_db="wb_prices.db") as wb:
    wb.sync_upstreams()
    item = wb.get_product(
        "https://www.wildberries.ru/catalog/141217830/detail.aspx",
        with_price_history=True,
    )
    print(item.name, item.brand, f"Отзывы: {item.feedback_count} (★ {item.valuation})")
    to_excel([item], "result/wb_catalog.xlsx")
    to_csv([item], "result/wb_catalog.csv")
    to_json([item], "result/wb_catalog.json")
```

### 2. Асинхронный сбор (`AsyncWBClient`), WB Кошелёк и Позиции (Rank)

```python
import asyncio
from wb_parser import AsyncWBClient, WBClient

async def fetch_many():
    async with AsyncWBClient(concurrency=16) as wb:
        return await wb.gather_cards([141217830, 181851928])

with WBClient() as wb:
    res = wb.wallet_price(4990, use_club=True)
    print(f"WB Клуб (-{res.discount_pct}%): {res.wallet_price} ₽")
```

### 3. Умные отзывы + Бесплатные (`g4f` / Ollama) и Платные AI-модели

```python
from wb_parser import AIClient, WBClient, list_ai_providers, test_ai_provider

with WBClient() as wb:
    # A) Быстрый оффлайн-разбор без интернета и ключей
    offline = wb.analyze_reviews(141217830, only_this_color=True, limit=100)
    print(offline.summary_mode, offline.top_pros, offline.top_cons)

    # B) Бесплатный AI без ключа через g4f (требует `uv add "wb-sdk-pro[ai]"`)
    free_res = wb.analyze_reviews(141217830, ai_mode="free", ai_provider="g4f")

    # C) Бесплатный локальный Ollama (`http://localhost:11434/v1`)
    local_res = wb.analyze_reviews(141217830, ai_mode="local", ai_provider="ollama", ai_model="llama3.2")

    # D) Платные / гибридные API (OpenAI, DeepSeek, OpenRouter, ProxyAPI, Groq, Gemini)
    paid_res = wb.analyze_reviews(
        141217830,
        ai_mode="paid",
        ai_provider="deepseek",
        ai_key="sk-...",
    )

# Сканер и проверка провайдеров (из testg4f):
health = test_ai_provider("Yqcloud", mode="free", timeout=10.0)
print(health.success, health.latency_seconds, health.hint)

ai = AIClient(mode="auto")
reply = ai.chat("Дай 3 совета для роста карточки на Wildberries")
print(reply.provider, reply.tier, reply.content)
```

| Пресет (`--provider`) | Уровень | Модель по умолчанию | Env-переменная | Base URL |
|---|---|---|---|---|
| `g4f` / `Yqcloud`, `Airforce`, `LLM7`... | **Free** (без ключа) | модель провайдера | — *(нужен `[ai]`)* | динамические `g4f` |
| `ollama` | **Local Free** | `llama3.2` | `OLLAMA_BASE_URL` | `http://localhost:11434/v1` |
| `lmstudio` | **Local Free** | `local-model` | `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` |
| `openrouter` | **Hybrid** (`:free` + Paid) | `deepseek/deepseek-chat-v3-0324:free` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `groq` | **Hybrid** (Free + Paid) | `openai/gpt-oss-20b` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` |
| `gemini` | **Hybrid** (Free + Paid) | `gemini-3.8-flash` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `openai` | **Paid** | `gpt-4o-mini` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `deepseek` | **Paid** | `deepseek-chat` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` |
| `proxyapi` | **Paid** (РФ) | `gpt-4o-mini` | `PROXYAPI_API_KEY` | `https://api.proxyapi.ru/openai/v1` |

---

## 🖥️ Графический интерфейс (Desktop GUI — 7 вкладок)

Требует установки опции `[gui]` (`uv add "wb-sdk-pro[gui]"` или `uv sync --extra gui`):

```bash
uv run wb-gui
# или из исходников:
uv run python run_gui.py
```

* **🔍 Парсер:** ссылки на товары, артикулы, продавцы (`/seller/...`), поисковые запросы, фильтры цен/скидок/рейтинга и белых/чёрных ключевых слов, мониторинг 24/7.
* **📦 Каталог товаров:** живые карточки с ценами, ценой по WB Кошельку (`💳`), снижением цены (`📉`) и экспортом в **Excel `.xlsx`**, CSV и JSON.
* **📈 Позиции (Rank):** пакетная проверка пар `артикул : запрос`, выбор сортировки, история динамики (`▲`/`▼`), экспорт в Excel.
* **💬 Умные отзывы + AI:** выбор режима (`Авто`, `Бесплатно g4f`, `Платный API`, `Локальный Ollama`, `Оффлайн`), выпадающий список провайдеров, поле модели, кнопка **⚡ Проверить AI** (диагностика как в `testg4f`) и мгновенная сводка **✅ Плюсы / ❌ Минусы**.
* **🌐 Прокси и Сессия:** выбор региона (`dest`), прокси HTTP/SOCKS5, URL смены IP, `cookies` и `x_wbaas_token`, кнопка проверки пинга CDN и живых ставок WB Кошелька.
* **✈️ Telegram & 📋 Журнал:** алерты через отдельный прокси для Telegram и живые логи (настройки сохраняются в `storage/gui_config.json`).

---

## 💻 Команды CLI (`wb-parser` / `wb-sdk` — 12 подкоманд)

```bash
# 1. Проверка CDN-корзин и текущих ставок WB Кошелька / ВБ Клуба
uv run wb-parser upstreams

# 2. Полная карточка товара + отзывы + история цен + экспорт в Excel
uv run wb-parser card https://www.wildberries.ru/catalog/141217830/detail.aspx --history -o item.xlsx

# 3. Поиск по каталогу с фильтрами и экспортом
uv run wb-parser search "кроссовки" --pages 2 --min-discount 20 -o search.xlsx

# 4. Сбор каталога продавца (URL продавца, supplier_id или ссылка на его товар)
uv run wb-parser seller 626520 --pages 5 --enrich -o seller.xlsx

# 5. Расчёт цены с WB Кошельком (или с флагом --club для ВБ Клуба)
uv run wb-parser wallet 4990 --club

# 6. Умный разбор отзывов (оффлайн / --mode free g4f / --mode local ollama / --mode paid deepseek)
uv run wb-parser reviews 141217830 --mode free --limit 60 -o reviews.json
uv run wb-parser reviews 141217830 --mode paid --provider deepseek --ai-key sk-...

# 7. Проверка позиции товара по поисковому запросу
uv run wb-parser rank 141217830 "кроссовки dunk" --pages 3 -o ranks.xlsx

# 8. Бесплатные и платные AI-провайдеры (список, модели, Health Check, quick-scan, запрос)
uv run wb-parser ai --list
uv run wb-parser ai --quick-scan
uv run wb-parser ai -p Yqcloud --test
uv run wb-parser ai --ask "Оцени плюсы кроссовок" --mode free

# 9. Прямой запрос отзывов по root_id (или по nm_id с флагом --is-nm)
uv run wb-parser feedbacks 181851928
uv run wb-parser feedbacks 141217830 --is-nm

# 10. Просмотр снижений цен из SQLite
uv run wb-parser drops --db wb_prices.db

# 11. Запуск MCP-сервера для ИИ-агентов (9 инструментов, stdio)
uv run wb-parser mcp

# 12. Запуск Desktop GUI (требует [gui])
uv run wb-parser gui
```

---

## 🤖 Нативный MCP-сервер (`wb-mcp` — 9 инструментов)

Поддерживает версии протокола MCP `2025-11-25`, `2025-06-18`, `2024-11-05` (`serverInfo.name = "wb-parser-mcp"`), возвращает `structuredContent` и принимает переменные окружения `WB_PROXY`, `WB_PROXY_CHANGE_URL`, `WB_COOKIES`, `WB_WBAAS_TOKEN`, `WB_TRACKER_DB`, `WB_AI_MODE`, `WB_AI_PROVIDER`, `WB_AI_MODEL`, `WB_AI_BASE_URL`, `WB_AI_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `PROXYAPI_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`.

Инструменты: `wb_get_card`, `wb_get_feedbacks`, `wb_search`, `wb_get_seller_catalog`, `wb_price_drops`, `wb_wallet_price`, `wb_check_rank`, `wb_smart_reviews`, `wb_ai_providers`.

---

## 🧪 Автотесты (`pytest`)

```bash
uv run pytest
```

**34 теста** подтверждены на всех версиях Python в GitHub Actions на **Linux, Windows и macOS** (CPython 3.8–3.16, Free-Threaded 3.13t–3.16t, PyPy 3.8–3.12): шардинг, модели, TOML/JSON-конфиг, sync/async клиенты, WB Кошелёк, ранжирование, отзывы, Free/Paid AI-движок (`g4f`, Ollama/`OLLAMA_BASE_URL`, OpenAI/DeepSeek/Groq), Excel/CSV, 9 инструментов MCP, 12 команд CLI, GUI и потокобезопасность без GIL.
