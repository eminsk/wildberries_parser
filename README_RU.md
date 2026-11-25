<h1 align="center">WB SDK Pro (`wb-sdk-pro`)</h1>
<p align="center">
  <b>Единая экосистема для Wildberries: Sync/Async SDK + CDN-роутер + WB Кошелёк + Позиции в поиске (Rank) + Умные отзывы + 11 команд CLI + MCP-сервер + 7-вкладочный Desktop GUI</b>
</p>

<p align="center">
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README.md">🇬🇧 English</a> •
  <b>🇷🇺 Документация на русском</b>
</p>

> Современное объединение трёх проектов (`wildberries_parser` с полной совместимостью `ParseWB` / `Item` / `Items` / `Feedback` + `wb_rank` + `wb_smart_review`) в единую потокобезопасную библиотеку на чистом Python (`uv add wb-sdk-pro`), CLI с 11 подкомандами (`wb-parser` / `wb-sdk`), нативный MCP-сервер (`wb-mcp`, 8 инструментов) и опциональный 7-вкладочный Desktop GUI (`wb-gui`).

---

## 🐍 Совместимость с Python

| Среда | Версии | Статус |
|---|---|---|
| **CPython** | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16 | ✅ Все 25 тестов (Win / Linux / macOS) |
| **Free-Threaded (No-GIL)** | 3.13t, 3.14t, 3.15t, 3.16t | ✅ Потокобезопасно (`RLock` + `wb_parser._model`) |
| **PyPy** | 3.8 (Linux CI), 3.9, 3.10, 3.11, 3.12 | ✅ Все 25 тестов |

Ядро SDK, CLI и MCP-сервера написано на чистом Python (`wb_parser._model` вместо `pydantic`) с каскадным HTTP-транспортом (`curl_cffi` с TLS Chrome 124 если установлен → `httpx[http2]` → `requests`), поэтому устанавливается и работает на **18 рантаймах Python** без Rust/C-зависимостей в ядре.

---

## 🚀 Что объединено в одном проекте (`v2.2.0`)

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

4. **Умные отзывы (`reviews.py`, из `wb_smart_review`):**
   - Переводит `nm_id` → `root_id` через CDN `card.json` и забирает отзывы с `feedbacks1/2`.
   - Фильтрует отзывы строго по выбранному цвету (`nm_id`) или по всей карточке (`root_id`), автоматически переключаясь на всю карточку, если по конкретному цвету нет текстовых отзывов.
   - Строит распределение оценок (1★–5★), статистику размерности (`matchingSize`), популярные теги (`bables_tags`) и **быструю оффлайн-сводку** плюсов/минусов (без API-ключей) либо **LLM-резюме** через любой OpenAI-совместимый API (`OPENAI_API_KEY` / OpenAI / DeepSeek / ProxyAPI / OpenRouter / Ollama).

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
# Базовый SDK, 11 команд CLI (wb-parser / wb-sdk) и MCP-сервер (wb-mcp)
uv add wb-sdk-pro

# Мгновенный запуск GUI через uvx (требуется опция [gui])
uvx --from "wb-sdk-pro[gui]" wb-gui

# Или через pip
pip install wb-sdk-pro
```

### Дополнительные опции (Extras)

```bash
# Desktop GUI (customtkinter, Pillow, curl_cffi)
uv add "wb-sdk-pro[gui]"

# Chrome 124 TLS движок для HTTP и async-запросов (curl_cffi)
uv add "wb-sdk-pro[tls]"

# Экспорт в pandas.DataFrame через to_dataframe()
uv add "wb-sdk-pro[dataframe]"   # или "wb-sdk-pro[pandas]"

# Всё сразу (GUI + Chrome TLS + pandas)
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
uv sync --extra gui  # с Desktop GUI и Chrome TLS
```

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
* **💬 Умные отзывы:** мгновенная выжимка плюсов (**✅**) и минусов (**❌**), гистограмма оценок, анализ размерности и лента отзывов (работает без прокси и без API-ключа или с опциональным LLM).
* **🌐 Прокси и Сессия:** выбор региона (`dest`), прокси HTTP/SOCKS5, URL смены IP, `cookies` и `x_wbaas_token`, кнопка проверки пинга CDN и живых ставок WB Кошелька.
* **✈️ Telegram & 📋 Журнал:** алерты через отдельный прокси для Telegram и живые логи (настройки сохраняются в `storage/gui_config.json`).

---

## 💻 Команды CLI (`wb-parser` / `wb-sdk` — 11 подкоманд)

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

# 6. Умный разбор отзывов товара (плюсы / минусы / размерность)
uv run wb-parser reviews 141217830 --limit 60 -o reviews.json

# 7. Проверка позиции товара по поисковому запросу
uv run wb-parser rank 141217830 "кроссовки dunk" --pages 3 -o ranks.xlsx

# 8. Прямой запрос отзывов по root_id (или по nm_id с флагом --is-nm)
uv run wb-parser feedbacks 181851928

# 9. Просмотр снижений цен из SQLite
uv run wb-parser drops --db wb_prices.db

# 10. Запуск MCP-сервера для ИИ-агентов (8 инструментов, stdio)
uv run wb-parser mcp

# 11. Запуск Desktop GUI (требует [gui])
uv run wb-parser gui
```

---

## 🤖 Нативный MCP-сервер (`wb-mcp` — 8 инструментов)

Поддерживает версии протокола MCP `2025-11-25`, `2025-06-18`, `2024-11-05` (`serverInfo.name = "wb-parser-mcp"`), возвращает `structuredContent` и принимает переменные окружения `WB_PROXY`, `WB_PROXY_CHANGE_URL`, `WB_COOKIES`, `WB_WBAAS_TOKEN`, `WB_TRACKER_DB`.

Инструменты: `wb_get_card`, `wb_get_feedbacks`, `wb_search`, `wb_get_seller_catalog`, `wb_price_drops`, `wb_wallet_price`, `wb_check_rank`, `wb_smart_reviews`.

---

## 🧪 Автотесты (`pytest`)

```bash
uv run pytest
```

**25 тестов** подтверждены локально на 17 версиях Python и в GitHub Actions на **Linux, Windows и macOS** (CPython 3.8–3.16, Free-Threaded 3.13t–3.16t, PyPy 3.8–3.12): шардинг, модели, TOML/JSON-конфиг, sync/async клиенты, WB Кошелёк, ранжирование, отзывы, Excel/CSV, MCP, CLI, GUI и потокобезопасность без GIL.
