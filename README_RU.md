<h1 align="center">WB SDK Pro (`wb-sdk-pro`)</h1>
<p align="center">
  <b>Единая экосистема для Wildberries: Парсер + WB Кошелёк + Позиции в поиске (Rank) + Умные отзывы + Desktop GUI + MCP-сервер</b>
</p>

<p align="center">
  <a href="https://github.com/eminsk/wildberries_parser/blob/master/README.md">🇬🇧 English</a> •
  <b>🇷🇺 Документация на русском</b>
</p>

> Современное объединение и глубокий рефакторинг трёх проектов (`wildberries_parser` + `wb_rank` + `wb_smart_review`) в единую модульную библиотеку на Python (`uv add wb-sdk-pro`), 7-вкладочный тёмный Desktop GUI, CLI и нативный MCP-сервер.

---

## 🐍 Совместимость с Python

| Среда | Версии | Статус |
|---|---|---|
| **CPython** | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16 | ✅ Все 25 тестов |
| **Free-Threaded (No-GIL)** | 3.13t, 3.14t, 3.15t, 3.16t | ✅ Потокобезопасно |
| **PyPy** | 3.9, 3.10, 3.11, 3.12 | ✅ Все 25 тестов |

**17 рантаймов протестировано** — ядро полностью на чистом Python без Rust/C-расширений. Встроенная `BaseModel` вместо `pydantic` для максимальной переносимости.

---

## 🚀 Что объединено в одном проекте (`v2.2.0`)

1. **Ядро парсера и CDN-роутер (`shards.py`, `client.py`, `http.py`):**
   - Исправлена маршрутизация отзывов **`feedbacks1` / `feedbacks2`** по точной формуле `root_id % 100 >= 50` (решение Issue #2).
   - Поддержка **всех 65+ корзин (`basket-01..65+`)** и живая синхронизация карты с `https://cdn.wbbasket.ru/api/v3/upstreams`.
   - Актуальные фото **`.webp`** на `wbbasket.ru` и прямой сбор карточек из CDN `card.json` **без банов WBAAS 498 и без прокси**.

2. **Калькулятор цены с WB Кошельком (`wallet.py`, из `wb_rank`):**
   - Забирает актуальные ставки из `default-payment.json` («Незалогиненный кошелёк» и «ВБ Клуб») и лимиты из `settings-front.json` (`wlt1DiscountDisplayMaxPrice`) с резервным зеркалом `geobasket`.
   - Автоматически добавляет `Цена с WB Кошельком (₽)` в карточки, Excel и Telegram-уведомления.

3. **Мониторинг позиций в поиске (`rank.py`, из `wb_rank`):**
   - Сканирует страницы поиска `1..N` (Топ 100–500+ выдачи), вычисляет сквозную позицию и страницу.
   - Сохраняет историю позиций в SQLite и показывает динамику (`▲ +5` / `▼ -3`).
   - Выгружает отчёты по позициям в стильный Excel (`.xlsx`).

4. **Умные отзывы (`reviews.py`, из `wb_smart_review`):**
   - Автоматически переводит `nm_id` → `root_id` через CDN `card.json` (без падений на `card.wb.ru`) и забирает реальные отзывы покупателей с `feedbacks1/2`.
   - Фильтрует отзывы строго по выбранному цвету (`nm_id`) или по всей карточке (`root_id`).
   - **Два режима сводки:** встроенный быстрый **оффлайн-анализатор** (без API-ключей — сразу выделяет плюсы, минусы и соответствие размера *«в размер / маломерит»*) и опциональный **OpenAI-совместимый LLM** (OpenAI, DeepSeek, ProxyAPI).

---

## 📦 Установка

### PyPI (`uv` / `pip`)

```bash
# Через uv (рекомендуется)
uv add wb-sdk-pro

# Мгновенный запуск GUI без установки в проект
uvx --from wb-sdk-pro wb-gui

# Или через pip
pip install wb-sdk-pro
```

### Дополнительные опции

```bash
# Desktop GUI (добавит customtkinter, Pillow, curl_cffi)
uv add "wb-sdk-pro[gui]"

# Chrome TLS движок (curl_cffi)
uv add "wb-sdk-pro[tls]"

# Всё сразу
uv add "wb-sdk-pro[all]"
```

### Debian / Ubuntu (APT)

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
uv sync
```

---

## 🖥️ Графический интерфейс (Desktop GUI — 7 вкладок)

```bash
uv run wb-gui
# или
uv run python run_gui.py
```

* **🔍 Парсер:** ссылки на товары, артикулы, продавцы (`/seller/...`), поиск, фильтры цен/скидок/рейтинга/ключевых слов, мониторинг 24/7.
* **📦 Каталог товаров:** живые карточки с ценами, ценой по WB Кошельку (`💳`), скидками и экспортом в **Excel `.xlsx`**, CSV и JSON.
* **📈 Позиции (Rank):** пакетная проверка пар `артикул : запрос`, история динамики (`▲`/`▼`), экспорт в Excel.
* **💬 Умные отзывы:** мгновенная выжимка плюсов (**✅**) и минусов (**❌**), анализ размерности и лента реальных отзывов (работает без прокси и без API-ключа).
* **🌐 Прокси и Сессия:** выбор региона (`dest`), прокси HTTP/SOCKS5, URL смены IP, `x_wbaas_token` cookie, кнопка проверки пинга и живых ставок WB Кошелька.
* **✈️ Telegram & 📋 Журнал:** алерты через отдельный прокси для Telegram и живые логи.

---

## 💻 Быстрые команды CLI (`wb-parser`)

```bash
# Проверка CDN-корзин и текущих ставок WB Кошелька
uv run wb-parser upstreams

# Расчёт цены с WB Кошельком
uv run wb-parser wallet 4990

# Полная карточка товара + отзывы + экспорт в Excel
uv run wb-parser card https://www.wildberries.ru/catalog/141217830/detail.aspx -o item.xlsx

# Умный разбор отзывов товара (плюсы / минусы / размерность)
uv run wb-parser reviews 141217830 --limit 60

# Проверка позиции товара по поисковому запросу
uv run wb-parser rank 141217830 "кроссовки dunk" --pages 3 -o ranks.xlsx

# Запуск MCP-сервера для ИИ-агентов (8 инструментов)
uv run wb-mcp
```

---

## 🧪 Автотесты (`pytest`)

```bash
uv run pytest
```

**25 тестов × 17 рантаймов** (CPython 3.8–3.16, PyPy 3.9–3.12, Free-Threaded 3.13t–3.16t): шардинг, модели, клиент, WB Кошелёк, ранжирование, отзывы, Excel, MCP, CLI, GUI и потокобезопасность.
