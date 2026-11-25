<h1 align="center">WB SDK Pro (`wb-parser-sdk`)</h1>
<p align="center">
  <b>Современный Python SDK, CLI, нативный MCP-сервер и тёмный Desktop GUI для Wildberries</b>
</p>

<p align="center">
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README.md">🇬🇧 English</a> •
  <b>🇷🇺 Документация на русском</b>
</p>

> Полноценная, современная и активно поддерживаемая версия парсера Wildberries на базе форка `Duff89/wildberries_parser`.  
> Исправлены все старые баги (маршрутизация `feedbacks1`/`feedbacks2`, корзины до `basket-65+`, битые `.jpg` заменены на реальные `.webp`, добавлен прямой CDN-режим без WBAAS 498, Excel `.xlsx`, тёмный интерфейс и MCP-сервер для ИИ).

---

## 🛠️ Что исправлено и добавлено по сравнению с оригиналом

1. **Починена маршрутизация отзывов `feedbacks1` / `feedbacks2` (Issue #2):**
   - В оригинале был захардкожен `feedbacks1.wb.ru`, из-за чего половина товаров не находилась.
   - Теперь используется точная формула фронтенда WB: `root_id % 100 >= 50` $\rightarrow$ `feedbacks2.wb.ru`, иначе `feedbacks1.wb.ru` (с автоматическим fallback).
2. **Актуальные корзины `basket-01` .. `basket-65+` и автообновление:**
   - В оригинале диапазоны заканчивались на `basket-15`. Сейчас на Wildberries артикулы перевалили за сотни миллионов.
   - Встроенная таблица покрывает все 65 корзин (артикулы до `2.88+ млрд`) и умеет **живьём синхронизироваться** с `https://cdn.wbbasket.ru/api/v3/upstreams`.
3. **Исправлены ссылки на фото (`.webp` вместо битых `.jpg`):**
   - Картинки формируются в актуальном формате `https://basket-XX.wbbasket.ru/vol.../part.../.../images/big/1.webp`.
4. **Прямая работа с `wbbasket.ru` CDN без прокси и банов WBAAS (498):**
   - Информация о карточке (`card.json`: описание, характеристики, бренд, ID продавца, `imt_id`/`root_id`, фото) и статистика отзывов (`feedbacks1/2`) забираются напрямую без WBAAS-заглушек.
5. **Устойчивый сетевой слой (Chrome TLS + IPv4 failover):**
   - Поддержка `curl_cffi` с эмуляцией Chrome и принудительным IPv4 (`CURL_IPRESOLVE_V4`), чтобы не зависать на проблемных IPv6 CDN-узлах в Windows.
   - Раздельная маршрутизация прокси для WB и для Telegram.
6. **Desktop GUI (`WB SDK Pro` на CustomTkinter), CLI и MCP-сервер.**

---

## 📦 Установка (через `uv`)

```bash
git clone https://github.com/eminsk/wildberries_parser.git
cd wildberries_parser
uv sync
```

---

## 🖥️ Запуск графического интерфейса (GUI)

```bash
uv run wb-gui
# или
uv run python run_gui.py
```

Во вкладке **«🔍 Парсер»** можно вставить ссылки на товары, артикулы (`141217830`), ссылки на продавца (`/seller/626520`) или поисковые запросы, задать фильтры по цене/скидке/рейтингу и выгрузить результат в стильный **Excel (`.xlsx`)**, **CSV** или **JSON**.

---

## ⚡ Использование как Python-библиотеки

```python
from wb_parser import WBClient, calculate_feedback_shard, to_excel

with WBClient(tracker_db="wb_prices.db") as wb:
    # Обновить карту корзин (basket-01..65+) с cdn.wbbasket.ru
    wb.sync_upstreams()

    # Собрать карточку товара с CDN + отзывы с нужного шарда (feedbacks1 / feedbacks2)
    item = wb.get_product("https://www.wildberries.ru/catalog/141217830/detail.aspx")
    print(item.name, item.brand, f"Отзывов: {item.feedback_count}", f"Рейтинг: {item.valuation}")

    # Сохранить в Excel с гиперссылками
    to_excel([item], "result/wb_items.xlsx")
```

---

## 💻 Консольный режим (CLI)

```bash
# Проверить доступность CDN и получить список всех живых корзин
uv run wb-parser upstreams

# Спарсить карточку товара и сохранить в Excel
uv run wb-parser card 141217830 -o product.xlsx

# Проверить отзывы по root_id с точным расчетом шарда
uv run wb-parser feedbacks 181851928

# Запустить MCP-сервер для Claude / Cursor / Antigravity
uv run wb-mcp
```

---

## 🧪 Автотесты (`pytest`)

```bash
uv run pytest
```
