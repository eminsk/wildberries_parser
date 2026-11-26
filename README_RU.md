<p align="center">
  <img src="assets/logo.png" width="140" alt="WB SDK Pro Logo">
</p>
<h1 align="center">WB SDK Pro (`wb-sdk-pro`)</h1>
<p align="center">
  <b>Единая экосистема для Wildberries: Sync/Async SDK + Интерактивный Telegram-бот (`WBTelegramBot`) + Автономное Windows .exe приложение + CDN + WB Кошелёк + Позиции (Rank) + Умные отзывы + Бесплатные/Платные AI (`g4f` / Ollama / OpenAI / DeepSeek / OpenRouter) + 13 команд CLI + MCP (9 инструментов)</b>
</p>

<p align="center">
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README.md">🇬🇧 English</a> •
  <b>🇷🇺 Документация на русском</b>
</p>

[![Release](https://img.shields.io/badge/релиз-v2.5.0-7c3aed.svg?style=flat&logo=github)](https://github.com/eminsk/wildberries_parser/releases/tag/v2.5.0)
[![Бесплатный тест прокси 3 часа](https://img.shields.io/badge/Прокси_без_VPN-Тест_3_часа_бесплатно-00C853?style=flat&logo=cloudflare&logoColor=white)](https://mobileproxy.rent/user.html?free&p=279117)
[![PyPI Version](https://img.shields.io/pypi/v/wb-sdk-pro.svg?style=flat&logo=pypi&color=blue)](https://pypi.org/project/wb-sdk-pro/)
[![Python Versions](https://img.shields.io/badge/python-3.8%20--%203.16+%20%7C%20PyPy%20%7C%20No--GIL-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Desktop GUI](https://img.shields.io/badge/Desktop%20GUI-Windows%20.exe%20%7C%207%20Вкладок-blueviolet.svg?style=flat)](https://github.com/eminsk/wildberries_parser/blob/master/README_RU.md#%D0%B3%D1%80%D0%B0%D1%84%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D0%B9-%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D1%84%D0%B5%D0%B9%D1%81-desktop-gui--%D0%B0%D0%B2%D1%82%D0%BE%D0%BD%D0%BE%D0%BC%D0%BD%D1%8B%D0%B9-exe--7-%D0%B2%D0%BA%D0%BB%D0%B0%D0%B4%D0%BE%D0%BA)
[![Telegram Канал](https://img.shields.io/badge/Telegram_Канал-@avito__sdk__pro-26A5E4?style=flat&logo=telegram&logoColor=white)](https://t.me/avito_sdk_pro)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)

> Современное объединение 4 проектов (`wildberries_parser` с совместимостью `ParseWB` / `Item` / `Items` / `Feedback` + `wb_rank` + `wb_smart_review` + **`testg4f`**) в единую потокобезопасную библиотеку (`uv add wb-sdk-pro`), **интерактивного Telegram-бота (`WBTelegramBot`)**, CLI на 13 подкоманд (`wb-parser` / `wb-sdk`), MCP-сервер (`wb-mcp`, 9 инструментов), 7-вкладочный GUI (`wb-gui`) и **готовое Windows `.exe`-приложение (`WBSDK_Pro.exe`)**.

> ### 🤝 Сообщество, мобильные прокси и поддержка
> - 🌐 **Ошибка 498 (WBAAS) / 429 на поиске и каталогах?** Возьмите [бесплатный тест мобильного прокси на 3 часа](https://mobileproxy.rent/user.html?free&p=279117) ([личный кабинет MobileProxy](https://mobileproxy.rent/?p=279117) — работает в РФ без VPN).
> - 📢 **Релизы, настройка прокси и чат:** подписывайтесь на [Telegram-канал @avito_sdk_pro](https://t.me/avito_sdk_pro).
> - 🐛 **Нашли баг или изменился API WB?** [Откройте Issue](https://github.com/eminsk/wildberries_parser/issues) — исправления выходят оперативно!
> - ⭐ **Полезен проект?** Поставьте звезду репозиторию на GitHub!
> - ☕ **Поддержать разработку (USDT TRC-20):** `TDVbEdnpgNgoAhNcn1EwXxWHiR3RKLit5P` ([Проверить в TronScan](https://tronscan.org/#/address/TDVbEdnpgNgoAhNcn1EwXxWHiR3RKLit5P))

<p align="center">
  <img src="docs/images/gui_parser.png" alt="WB SDK Pro Desktop GUI — Вкладка Парсер" width="820">
</p>

---

## 🐍 Совместимость с Python

| Среда | Версии | Статус |
|---|---|---|
| **CPython** | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16 | ✅ Все 34 теста (Win / Linux / macOS) |
| **Free-Threaded (No-GIL)** | 3.13t, 3.14t, 3.15t, 3.16t | ✅ Потокобезопасно (`RLock` + `wb_parser._model`) |
| **PyPy** | 3.8 (Linux CI), 3.9, 3.10, 3.11, 3.12 | ✅ Все 34 теста |

Ядро SDK, CLI и MCP-сервера написано на чистом Python (`wb_parser._model` вместо `pydantic`) с каскадным HTTP-транспортом (`curl_cffi` с TLS Chrome 124 если установлен → `httpx[http2]` → `requests`), поэтому устанавливается и работает на **18 рантаймах Python** без Rust/C-зависимостей в ядре.

---

## 🚀 Что объединено в одном проекте (`v2.5.0`)

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

5. **Трекер цен, Excel-отчёты и интерактивный Telegram-бот (`tracker.py`, `export.py`, `config.py`, `telegram.py`):**
   - Потокобезопасная история цен и отслеживание снижения цены в SQLite (`wb_latest_prices`, `wb_price_history`).
   - Экспорт в **Excel `.xlsx`** (товары `to_excel`, позиции `rank_results_to_excel`, отзывы и AI-саммари `reviews_to_excel` с гиперссылками, защитой от формульных инъекций и зелёным выделением падений цен), **CSV UTF-8 BOM**, **JSON**, **JSONL** и `pandas.DataFrame` (опциональный `[dataframe]`).
   - Загрузка настроек `WBConfig.from_file()` из **`.json`** и **`.toml`** (с `tomli` для Python <3.11) + справочник регионов `DEST_CODES`.
   - **`TelegramNotifier`** (HTML-карточки, сводки отзывов, отправка `.xlsx`-файлов и живые прогресс-бары) + полноценный интерактивный бот **`WBTelegramBot`** (команды `/start`, `/search`, `/drops`, `/wallet`, `/rank`, `/reviews`, `/workers`, `/limit`, `/proxy`, пакетный сбор списка ссылок и выгрузка `.xlsx` в чат через изолированный `tg_proxy` + `run_telegram_bot.py`).

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

## 🖥️ Графический интерфейс (Desktop GUI — автономный `.exe` + 7 вкладок)

### 1. Запуск готового приложения для Windows (без установки Python):
1. Скачайте архив **[WBSDK_Pro_Windows_x64.zip](https://github.com/eminsk/wildberries_parser/releases/latest)** из раздела [Releases](https://github.com/eminsk/wildberries_parser/releases).
2. Распакуйте и запустите `WBSDK_Pro.exe` (внутри уже вшиты Chrome TLS `curl_cffi` и бесплатный AI-движок `g4f`).

### 2. Или запуск через Python / PyPI:
Требует установки опции `[gui]` (`uv add "wb-sdk-pro[gui]"` или `uv sync --extra gui`):

```bash
uvx --from "wb-sdk-pro[gui]" wb-gui
# или из исходников:
uv run python run_gui.py
# или двойным кликом по run_gui.bat
```

* **🔍 Парсер:** ссылки на товары, артикулы, продавцы (`/seller/...`), поисковые запросы, фильтры цен/скидок/рейтинга и белых/чёрных ключевых слов, мониторинг 24/7.
* **📦 Каталог товаров:** живые карточки с ценами, ценой по WB Кошельку (`💳`), снижением цены (`📉`) и экспортом в **Excel `.xlsx`**, **✈ Excel → TG**, CSV и JSON.
* **📈 Позиции (Rank):** пакетная проверка пар `артикул : запрос`, выбор сортировки, история динамики (`▲`/`▼`), экспорт в Excel и **✈ Позиции → TG**.
* **💬 Умные отзывы + AI:** выбор режима (`Авто`, `Бесплатно g4f`, `Платный API`, `Локальный Ollama`, `Оффлайн`), выпадающий список провайдеров, кнопка **⚡ Проверить AI**, экспорт отзывов в **📊 Excel (`reviews_to_excel`)** и отправка в **✈ TG**.
* **🌐 Прокси и Сессия:** выбор региона (`dest`), прокси HTTP/SOCKS5, **URL/ключ смены IP MobileProxy.rent** (с кнопкой бесплатного 3-часового теста), `cookies` и `x_wbaas_token`, кнопка проверки пинга CDN и живых ставок WB Кошелька.
* **✈️ Telegram & 📋 Журнал:** алерты через отдельный прокси для Telegram, **запуск интерактивного `WBTelegramBot` одной кнопкой** прямо из вкладки Telegram, живые логи и кнопка **`☕ Донат`** в шапке окна (`storage/gui_config.json`).

<p align="center">
  <img src="docs/images/gui_catalog.png" alt="WB SDK Pro Desktop GUI — Каталог товаров и WB Кошелёк" width="820">
</p>
<p align="center">
  <img src="docs/images/gui_reviews_ai.png" alt="WB SDK Pro Desktop GUI — Умные отзывы и бесплатный AI g4f" width="820">
</p>
<p align="center">
  <img src="docs/images/gui_telegram.png" alt="WB SDK Pro Desktop GUI — Интерактивный Telegram-бот" width="820">
</p>
<p align="center">
  <img src="docs/images/gui_proxy.png" alt="WB SDK Pro Desktop GUI — Вкладка Прокси и MobileProxy" width="820">
</p>

---

## 🌐 Выбор и настройка сетевых прокси

Прямые карточки `wbbasket.ru` (`card.json`, `.webp`) и отзывы `feedbacks1/2` работают **без прокси**. Для поиска, витрин продавцов и многопоточного мониторинга без ограничений WBAAS `498`/`429`:

1. **Серверные статические (IPv4 / SOCKS5 — от 30–50 ₽/мес):** подходят для 1–3 запросов в спокойном режиме.
2. **Оплата за трафик (Pay-As-You-Go — ~200 ₽/ГБ):** [AstroProxy](https://astroproxy.com), [Asocks](https://asocks.com) — экономичный расход только под JSON/HTML.
3. **Выделенные 4G/LTE модемы с ротацией IP (рекомендуется):** [MobileProxy (mobileproxy.rent)](https://mobileproxy.rent/?p=279117) ([бесплатный тест 3 часа без VPN](https://mobileproxy.rent/user.html?free&p=279117)):
   ```python
   from wb_parser import WBClient

   with WBClient(
       proxy="http://login:password@proxy-domain.space:port",
       mobileproxy_key="ВАШ_КЛЮЧ_РОТАЦИИ",  # подставит URL changeip.mobileproxy.space автоматически
   ) as wb:
       items = wb.search("кроссовки", max_pages=3)
   ```

---

## 💻 Команды CLI (`wb-parser` / `wb-sdk` — 13 подкоманд)

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

# 13. Интерактивный Telegram-бот (прогресс-бар, /drops, /wallet, /rank, /reviews, Excel в чат)
uv run wb-parser bot --tg-token "123:AAF..." --mobileproxy-key "KEY" --tg-proxy "socks5://127.0.0.1:1080"
# или автономный скрипт:
uv run python run_telegram_bot.py
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

**40 тестов** подтверждены на всех версиях Python в GitHub Actions на **Linux, Windows и macOS** (CPython 3.8–3.16, Free-Threaded 3.13t–3.16t, PyPy 3.8–3.12): шардинг, модели, TOML/JSON-конфиг, sync/async клиенты, MobileProxy-ротация, WB Кошелёк, ранжирование, отзывы, Free/Paid AI-движок (`g4f`, Ollama/`OLLAMA_BASE_URL`, OpenAI/DeepSeek/Groq), Excel (`to_excel`, `reviews_to_excel`, `rank_results_to_excel`), интерактивный `WBTelegramBot`, 9 инструментов MCP, 13 команд CLI, GUI (включая иконки и `.exe`) и потокобезопасность без GIL.

---

## ☕ Поддержать проект (Донат)

Если библиотека помогает в работе или экономит время разработки:
* ⭐ Поставьте звезду на [GitHub](https://github.com/eminsk/wildberries_parser)
* 🌐 Воспользуйтесь партнёрской ссылкой: [MobileProxy — 3 часа бесплатно без VPN](https://mobileproxy.rent/user.html?free&p=279117)
* 💎 **USDT (TRC-20):** `TDVbEdnpgNgoAhNcn1EwXxWHiR3RKLit5P` ([Проверить в TronScan](https://tronscan.org/#/address/TDVbEdnpgNgoAhNcn1EwXxWHiR3RKLit5P))

## 📄 Лицензия

MIT License.
