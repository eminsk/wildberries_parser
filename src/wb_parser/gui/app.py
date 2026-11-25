"""
Wildberries SDK Pro — Modern Dark Desktop GUI Application.

Modular, thread-safe CustomTkinter interface supporting:
- Direct CDN product card extraction (`card.json` + `.webp` images + `feedbacks1/2` shard reviews)
- Seller store & keyword search scraping (with optional proxy / browser session cookies / region)
- Live product feed with price-drop badges, filters, clickable WB & CDN links
- 1-click export to Excel (.xlsx), CSV, and JSON
- Dedicated proxy ping/latency diagnostics & decoupled Telegram alerts
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from tkinter import filedialog
except ImportError:  # pragma: no cover
    filedialog = None  # type: ignore[assignment]

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None

from wb_parser import __version__
from wb_parser.client import WBClient, filter_products
from wb_parser.config import DEFAULT_DEST, DEST_CODES, ISSUES_URL, TELEGRAM_CHANNEL_URL
from wb_parser.exceptions import WBAntiBotError
from wb_parser.export import rank_results_to_excel, to_csv, to_excel, to_json
from wb_parser.http import CURL_CFFI_AVAILABLE
from wb_parser.models import WBProduct
from wb_parser.rank import RankResult, WBRankTracker
from wb_parser.reviews import ReviewSummary, SmartReviewAnalyzer
from wb_parser.telegram import TelegramNotifier

logger = logging.getLogger("wb_parser.gui")


def _get_base_dir() -> Path:
    """Resolve base application directory safely for both normal and PyInstaller execution."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent.parent


class WBGUIConfig:
    """Persistent GUI settings stored in `storage/gui_config.json`."""

    CONFIG_PATH = _get_base_dir() / "storage" / "gui_config.json"

    def __init__(self) -> None:
        self.targets: List[str] = [
            "https://www.wildberries.ru/catalog/141217830/detail.aspx",
            "181851928",
        ]
        self.dest_name: str = "Москва"
        self.max_pages: int = 3
        self.limit: int = 100
        self.interval_sec: int = 60
        self.min_price: str = ""
        self.max_price: str = ""
        self.min_discount: str = ""
        self.min_rating: str = ""
        self.white_keywords: str = ""
        self.black_keywords: str = ""
        self.with_feedbacks: bool = True
        self.enrich_cdn: bool = True
        self.continuous_monitor: bool = False
        self.proxy_string: str = ""
        self.proxy_change_url: str = ""
        self.cookies: str = ""
        self.wbaas_token: str = ""
        self.tg_token: str = ""
        self.tg_chat_id: str = ""
        self.tg_proxy: str = ""
        self.tg_notify: bool = False
        self.rank_pairs: List[str] = [
            "141217830 : кроссовки sb dunk",
            "339182812 : кеды мужские",
        ]
        self.rank_pages: int = 3
        self.review_target: str = "141217830"
        self.review_only_color: bool = True
        self.review_ai_key: str = ""
        self.review_ai_url: str = "https://api.openai.com/v1"

    @classmethod
    def load(cls) -> "WBGUIConfig":
        cfg = cls()
        if cls.CONFIG_PATH.exists():
            try:
                data = json.loads(cls.CONFIG_PATH.read_text(encoding="utf-8"))
                for key, val in data.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, val)
            except Exception as exc:
                logger.warning(f"Could not load gui_config.json: {exc}")
        return cfg

    def save(self) -> None:
        try:
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.CONFIG_PATH.write_text(
                json.dumps(self.__dict__, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Could not save gui_config.json: {exc}")


class _QueueLogHandler(logging.Handler):
    """Forwards SDK log records into the GUI thread-safe queue."""

    def __init__(self, target_queue: "queue.Queue[str]") -> None:
        super().__init__()
        self.target_queue = target_queue

    def emit(self, record: logging.LogRecord) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.target_queue.put(f"[{ts}] [{record.levelname}] {record.getMessage()}")


class WBGUIApp:
    """Main dark-themed desktop interface built on CustomTkinter."""

    def __init__(self) -> None:
        if ctk is None:  # pragma: no cover
            raise RuntimeError('customtkinter is required for GUI. Run: uv add "wb-sdk-pro[gui]"')

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("WB SDK Pro — Парсер & Мониторинг Wildberries")
        self.root.geometry("1160x780")
        self.root.minsize(980, 660)

        self.config = WBGUIConfig.load()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.item_queue: queue.Queue[WBProduct] = queue.Queue()
        self.status_queue: queue.Queue[tuple[str, str, str]] = queue.Queue()

        self.seen_ids: Set[int] = set()
        self.discovered_items: List[WBProduct] = []
        self.rank_results: List[RankResult] = []
        self.stats_found = 0
        self.stats_discounts = 0
        self.stats_checks = 0
        self.stats_tg = 0

        self._attach_logger()
        self._build_ui()
        self._load_config_into_ui()
        self._start_pollers()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _attach_logger(self) -> None:
        handler = _QueueLogHandler(self.log_queue)
        root_logger = logging.getLogger("wb_parser")
        root_logger.setLevel(logging.INFO)
        if not any(isinstance(h, _QueueLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(handler)

    def _make_link_button(self, parent: Any, text: str, url: str, **kwargs: Any) -> Any:
        return ctk.CTkButton(parent, text=text, command=lambda: webbrowser.open(url), **kwargs)

    def _make_labeled_entry(
        self,
        parent: Any,
        label: str,
        placeholder: str,
        width: Optional[int] = None,
        expand: bool = False,
    ) -> Any:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(side="left", fill="x" if expand else "none", expand=expand, padx=4)
        ctk.CTkLabel(
            box, text=label, font=ctk.CTkFont(size=11), text_color="#94a3b8"
        ).pack(anchor="w", padx=2, pady=(0, 2))
        kw: Dict[str, Any] = {"placeholder_text": placeholder}
        if width is not None:
            kw["width"] = width
        entry = ctk.CTkEntry(box, **kw)
        entry.pack(fill="x" if expand else "none")
        return entry

    def _build_ui(self) -> None:
        # Top Header Bar
        header = ctk.CTkFrame(self.root, corner_radius=0, height=64, fg_color="#1a1625")
        header.pack(fill="x", side="top")

        ctk.CTkLabel(
            header,
            text="WB SDK PRO",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#c084fc",
        ).pack(side="left", padx=(20, 8), pady=14)

        tls_label = "Chrome TLS (curl_cffi)" if CURL_CFFI_AVAILABLE else "Standard HTTP/2"
        ctk.CTkLabel(
            header,
            text=f"v{__version__} • {tls_label} • basket-01..65+",
            font=ctk.CTkFont(size=11),
            text_color="#cbd5e1",
            fg_color="#312e81",
            corner_radius=6,
            padx=10,
            pady=3,
        ).pack(side="left", padx=6, pady=18)

        self._make_link_button(
            header,
            text="🐛 Баги / GitHub",
            url=ISSUES_URL,
            width=120,
            height=28,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="right", padx=(6, 16), pady=16)

        self._make_link_button(
            header,
            text="✈️ Telegram",
            url=TELEGRAM_CHANNEL_URL,
            width=110,
            height=28,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="right", padx=(6, 0), pady=16)

        self.status_pill = ctk.CTkLabel(
            header,
            text="● ГОТОВ К РАБОТЕ",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#22c55e",
            fg_color="#064e3b",
            corner_radius=12,
            padx=14,
            pady=4,
        )
        self.status_pill.pack(side="right", padx=(10, 6), pady=15)

        # Stats strip
        stats = ctk.CTkFrame(self.root, height=34, fg_color="#0f172a", corner_radius=0)
        stats.pack(fill="x", side="top")

        self.lbl_stats_found = ctk.CTkLabel(stats, text="📦 Найдено товаров: 0", text_color="#cbd5e1")
        self.lbl_stats_found.pack(side="left", padx=20, pady=4)

        self.lbl_stats_discounts = ctk.CTkLabel(stats, text="📉 Со скидкой / падением: 0", text_color="#cbd5e1")
        self.lbl_stats_discounts.pack(side="left", padx=20, pady=4)

        self.lbl_stats_checks = ctk.CTkLabel(stats, text="⏱️ Запусков: 0", text_color="#cbd5e1")
        self.lbl_stats_checks.pack(side="left", padx=20, pady=4)

        self.lbl_stats_tg = ctk.CTkLabel(stats, text="✈️ Отправлено в TG: 0", text_color="#cbd5e1")
        self.lbl_stats_tg.pack(side="left", padx=20, pady=4)

        # Tabs
        self.tabview = ctk.CTkTabview(self.root, corner_radius=10, fg_color="#1e293b")
        self.tabview.pack(fill="both", expand=True, padx=16, pady=12)

        self.tab_parse = self.tabview.add("🔍 Парсер")
        self.tab_feed = self.tabview.add("📦 Каталог товаров")
        self.tab_rank = self.tabview.add("📈 Позиции (Rank)")
        self.tab_reviews = self.tabview.add("💬 Умные отзывы")
        self.tab_proxy = self.tabview.add("🌐 Прокси и Сессия")
        self.tab_tg = self.tabview.add("✈️ Telegram")
        self.tab_logs = self.tabview.add("📋 Журнал")

        self._build_parse_tab()
        self._build_feed_tab()
        self._build_rank_tab()
        self._build_reviews_tab()
        self._build_proxy_tab()
        self._build_tg_tab()
        self._build_logs_tab()

    def _build_parse_tab(self) -> None:
        left = ctk.CTkFrame(self.tab_parse, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            left,
            text="Ссылки WB (товар, /seller/..., ?search=...), артикулы (nm_id) или запросы (по 1 на строке):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=4, pady=(0, 4))

        self.txt_targets = ctk.CTkTextbox(left, height=190, font=ctk.CTkFont(size=12))
        self.txt_targets.pack(fill="x", padx=4, pady=(0, 10))

        filter_card = ctk.CTkFrame(left, fg_color="#0f172a", corner_radius=8)
        filter_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(
            filter_card, text="Фильтры цен, скидок и ключевых слов:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))

        row1 = ctk.CTkFrame(filter_card, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=4)
        self.entry_min_price = self._make_labeled_entry(row1, "Мин. цена (₽)", "0", width=115)
        self.entry_max_price = self._make_labeled_entry(row1, "Макс. цена (₽)", "50000", width=115)
        self.entry_min_discount = self._make_labeled_entry(row1, "Мин. скидка (%)", "0", width=115)
        self.entry_min_rating = self._make_labeled_entry(row1, "Мин. рейтинг", "4.5", width=115)

        row2 = ctk.CTkFrame(filter_card, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(4, 10))
        self.entry_white = self._make_labeled_entry(row2, "Белый список (через запятую)", "nike, кожа", expand=True)
        self.entry_black = self._make_labeled_entry(row2, "Минус-слова (чёрный список)", "б/у, уценка", expand=True)

        # Right panel: execution settings & start/stop
        right = ctk.CTkFrame(self.tab_parse, width=290, fg_color="#0f172a", corner_radius=8)
        right.pack(side="right", fill="y", padx=10, pady=10)
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="Параметры сбора", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=14, pady=(14, 10)
        )

        row_lim = ctk.CTkFrame(right, fg_color="transparent")
        row_lim.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row_lim, text="Макс. страниц:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.entry_pages = ctk.CTkEntry(row_lim, width=70)
        self.entry_pages.pack(side="right")

        row_cnt = ctk.CTkFrame(right, fg_color="transparent")
        row_cnt.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row_cnt, text="Лимит товаров:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.entry_limit = ctk.CTkEntry(row_cnt, width=70)
        self.entry_limit.pack(side="right")

        row_int = ctk.CTkFrame(right, fg_color="transparent")
        row_int.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row_int, text="Интервал монитор. (сек):", font=ctk.CTkFont(size=12)).pack(side="left")
        self.entry_interval = ctk.CTkEntry(row_int, width=70)
        self.entry_interval.pack(side="right")

        self.var_feedbacks = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(right, text="Собирать отзывы (feedbacks1/2)", variable=self.var_feedbacks).pack(
            anchor="w", padx=14, pady=(10, 4)
        )

        self.var_cdn = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(right, text="Догружать card.json & .webp", variable=self.var_cdn).pack(
            anchor="w", padx=14, pady=4
        )

        self.var_continuous = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(right, text="Цикличный мониторинг 24/7", variable=self.var_continuous).pack(
            anchor="w", padx=14, pady=4
        )

        self.btn_start = ctk.CTkButton(
            right,
            text="▶ ЗАПУСТИТЬ ПАРСЕР",
            height=42,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_scrape,
        )
        self.btn_start.pack(fill="x", padx=14, pady=(18, 6))

        self.btn_stop = ctk.CTkButton(
            right,
            text="⏹ ОСТАНОВИТЬ",
            height=36,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            state="disabled",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._stop_scrape,
        )
        self.btn_stop.pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(
            right,
            text="💡 Подсказка: Артикулы и ссылки на\nтовары загружаются напрямую с CDN\nwbbasket.ru без прокси и банов!",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
            justify="left",
        ).pack(anchor="w", padx=14, pady=(14, 6))

    def _build_feed_tab(self) -> None:
        bar = ctk.CTkFrame(self.tab_feed, fg_color="#0f172a", height=46, corner_radius=8)
        bar.pack(fill="x", padx=10, pady=(10, 6))

        ctk.CTkButton(
            bar,
            text="📊 Экспорт Excel (.xlsx)",
            width=170,
            fg_color="#16a34a",
            hover_color="#15803d",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._export_excel,
        ).pack(side="left", padx=8, pady=8)

        ctk.CTkButton(
            bar,
            text="📄 Экспорт CSV",
            width=120,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self._export_csv,
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            bar,
            text="{} JSON",
            width=90,
            fg_color="#475569",
            hover_color="#334155",
            command=self._export_json,
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            bar,
            text="🗑 Очистить",
            width=90,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self._clear_feed,
        ).pack(side="right", padx=8, pady=8)

        self.feed_scroll = ctk.CTkScrollableFrame(self.tab_feed, fg_color="#0f172a", corner_radius=8)
        self.feed_scroll.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.lbl_empty_feed = ctk.CTkLabel(
            self.feed_scroll,
            text="Собранные товары появятся здесь. Введите артикулы или ссылки во вкладке «Парсер» и нажмите Старт.",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=13),
        )
        self.lbl_empty_feed.pack(pady=40)

    def _build_rank_tab(self) -> None:
        left = ctk.CTkFrame(self.tab_rank, width=370, fg_color="#0f172a", corner_radius=8)
        left.pack(side="left", fill="y", padx=(10, 6), pady=10)
        left.pack_propagate(False)

        ctk.CTkLabel(
            left,
            text="Проверка позиций в выдаче (артикул : запрос):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 4))

        self.txt_rank_pairs = ctk.CTkTextbox(left, height=220, font=ctk.CTkFont(size=12))
        self.txt_rank_pairs.pack(fill="x", padx=12, pady=(0, 10))

        row_opts = ctk.CTkFrame(left, fg_color="transparent")
        row_opts.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_opts, text="Глубина (страниц):", font=ctk.CTkFont(size=12)).pack(side="left")
        self.entry_rank_pages = ctk.CTkEntry(row_opts, width=65)
        self.entry_rank_pages.pack(side="right")

        row_sort = ctk.CTkFrame(left, fg_color="transparent")
        row_sort.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_sort, text="Сортировка:", font=ctk.CTkFont(size=12)).pack(side="left")
        self.opt_rank_sort = ctk.CTkOptionMenu(
            row_sort, values=["popular", "pricedown", "priceup", "rate", "newly"], width=150
        )
        self.opt_rank_sort.pack(side="right")

        self.btn_rank_check = ctk.CTkButton(
            left,
            text="📈 Проверить позиции",
            height=40,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_rank_check,
        )
        self.btn_rank_check.pack(fill="x", padx=12, pady=(14, 6))

        ctk.CTkButton(
            left,
            text="📊 Экспорт позиций (.xlsx)",
            height=34,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=self._export_rank_excel,
        ).pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            left,
            text="Формат строк: 401385455 : джинсы женские\nИстория позиций сохраняется в SQLite\nи показывает динамику ▲/▼.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
            justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.rank_scroll = ctk.CTkScrollableFrame(self.tab_rank, fg_color="#0f172a", corner_radius=8)
        self.rank_scroll.pack(side="right", fill="both", expand=True, padx=(6, 10), pady=10)
        self.lbl_rank_placeholder = ctk.CTkLabel(
            self.rank_scroll,
            text="Результаты позиций по ключевым запросам появятся здесь.",
            text_color="#94a3b8",
        )
        self.lbl_rank_placeholder.pack(pady=40)

    def _build_reviews_tab(self) -> None:
        top = ctk.CTkFrame(self.tab_reviews, fg_color="#0f172a", corner_radius=8)
        top.pack(fill="x", padx=10, pady=(10, 6))

        row1 = ctk.CTkFrame(top, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 6))

        self.entry_review_target = self._make_labeled_entry(
            row1, "Ссылка WB или артикул (nm_id)", "141217830 или https://www.wildberries.ru/catalog/...", expand=True
        )
        self.var_review_color = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row1, text="Только этот цвет (nm_id)", variable=self.var_review_color
        ).pack(side="left", padx=(10, 8), pady=(14, 0))

        self.btn_review_run = ctk.CTkButton(
            row1,
            text="🧠 Анализировать отзывы",
            width=200,
            height=36,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._run_review_analysis,
        )
        self.btn_review_run.pack(side="right", pady=(12, 0))

        row2 = ctk.CTkFrame(top, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 10))
        self.entry_review_ai_key = self._make_labeled_entry(
            row2, "OpenAI / DeepSeek / ProxyAPI Key (опционально — без ключа работает быстрый оффлайн-анализ)", "sk-...", expand=True
        )
        self.entry_review_ai_url = self._make_labeled_entry(
            row2, "API Base URL (опц.)", "https://api.openai.com/v1", width=260
        )

        # KPI & Pros/Cons Split
        self.lbl_review_kpi = ctk.CTkLabel(
            self.tab_reviews,
            text="Введите артикул и нажмите «Анализировать отзывы» (работает напрямую через CDN + feedbacks1/2 без прокси)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#cbd5e1",
        )
        self.lbl_review_kpi.pack(anchor="w", padx=14, pady=(2, 4))

        split = ctk.CTkFrame(self.tab_reviews, fg_color="transparent", height=185)
        split.pack(fill="x", padx=10, pady=4)
        split.pack_propagate(False)

        pros_card = ctk.CTkFrame(split, fg_color="#052e16", corner_radius=8)
        pros_card.pack(side="left", fill="both", expand=True, padx=(0, 5))
        ctk.CTkLabel(
            pros_card, text="✅ Главные плюсы", font=ctk.CTkFont(size=13, weight="bold"), text_color="#4ade80"
        ).pack(anchor="w", padx=12, pady=(8, 4))
        self.txt_review_pros = ctk.CTkTextbox(pros_card, fg_color="#052e16", font=ctk.CTkFont(size=12))
        self.txt_review_pros.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cons_card = ctk.CTkFrame(split, fg_color="#450a0a", corner_radius=8)
        cons_card.pack(side="right", fill="both", expand=True, padx=(5, 0))
        ctk.CTkLabel(
            cons_card, text="❌ Главные минусы", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f87171"
        ).pack(anchor="w", padx=12, pady=(8, 4))
        self.txt_review_cons = ctk.CTkTextbox(cons_card, fg_color="#450a0a", font=ctk.CTkFont(size=12))
        self.txt_review_cons.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.reviews_scroll = ctk.CTkScrollableFrame(self.tab_reviews, fg_color="#0f172a", corner_radius=8)
        self.reviews_scroll.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def _build_proxy_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_proxy, fg_color="#0f172a", corner_radius=8)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            frame,
            text="Настройка прокси, региона (dest) и опциональной браузерной сессии:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 10))

        # Region dropdown
        reg_row = ctk.CTkFrame(frame, fg_color="transparent")
        reg_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(reg_row, text="Регион доставки (dest):", width=200, anchor="w").pack(side="left")
        self.opt_dest = ctk.CTkOptionMenu(reg_row, values=list(DEST_CODES.keys()), width=220)
        self.opt_dest.pack(side="left", padx=6)

        # Proxy URL
        prx_row = ctk.CTkFrame(frame, fg_color="transparent")
        prx_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(prx_row, text="HTTP / SOCKS5 прокси:", width=200, anchor="w").pack(side="left")
        self.entry_proxy = ctk.CTkEntry(prx_row, placeholder_text="http://user:pass@ip:port или socks5://...", width=420)
        self.entry_proxy.pack(side="left", padx=6)

        # Rotation URL
        rot_row = ctk.CTkFrame(frame, fg_color="transparent")
        rot_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(rot_row, text="URL смены IP (MobileProxy):", width=200, anchor="w").pack(side="left")
        self.entry_proxy_rotate = ctk.CTkEntry(rot_row, placeholder_text="https://changeip.mobileproxy.space/...", width=420)
        self.entry_proxy_rotate.pack(side="left", padx=6)

        # Cookies & x-wbaas-token
        ck_row = ctk.CTkFrame(frame, fg_color="transparent")
        ck_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(ck_row, text="Cookie строка (опц.):", width=200, anchor="w").pack(side="left")
        self.entry_cookies = ctk.CTkEntry(ck_row, placeholder_text="Для обхода WBAAS 498 на поиске / каталоге", width=420)
        self.entry_cookies.pack(side="left", padx=6)

        tok_row = ctk.CTkFrame(frame, fg_color="transparent")
        tok_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(tok_row, text="x-wbaas-token (опц.):", width=200, anchor="w").pack(side="left")
        self.entry_wbaas = ctk.CTkEntry(tok_row, placeholder_text="Токен из браузера (если требуется WBAAS)", width=420)
        self.entry_wbaas.pack(side="left", padx=6)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkButton(
            btn_row,
            text="🔌 Проверить CDN и прокси (Ping + Upstreams)",
            width=300,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._test_proxy_connectivity,
        ).pack(side="left")

        self.lbl_proxy_status = ctk.CTkLabel(btn_row, text="", text_color="#cbd5e1", font=ctk.CTkFont(size=12))
        self.lbl_proxy_status.pack(side="left", padx=14)

    def _build_tg_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_tg, fg_color="#0f172a", corner_radius=8)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            frame,
            text="Уведомления в Telegram (поддержка отдельного SOCKS5/HTTP прокси для TG):",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 10))

        for label, attr, ph in [
            ("Bot Token:", "entry_tg_token", "123456789:AAF..."),
            ("Chat / Channel ID:", "entry_tg_chat", "@channel или -100..."),
            ("Telegram Proxy (опц.):", "entry_tg_proxy", "socks5://127.0.0.1:1080 (независим от WB прокси)"),
        ]:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(row, text=label, width=200, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=ph, width=420)
            entry.pack(side="left", padx=6)
            setattr(self, attr, entry)

        self.var_tg_notify = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="Отправлять новые найденные товары в Telegram", variable=self.var_tg_notify).pack(
            anchor="w", padx=16, pady=12
        )

        ctk.CTkButton(
            frame,
            text="✈ Отправить тестовое сообщение",
            width=240,
            fg_color="#0284c7",
            command=self._test_telegram,
        ).pack(anchor="w", padx=16, pady=6)

    def _build_logs_tab(self) -> None:
        self.txt_logs = ctk.CTkTextbox(self.tab_logs, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#0f172a")
        self.txt_logs.pack(fill="both", expand=True, padx=10, pady=10)

    def _load_config_into_ui(self) -> None:
        cfg = self.config
        self.txt_targets.delete("1.0", "end")
        self.txt_targets.insert("1.0", "\n".join(cfg.targets))
        self.entry_min_price.insert(0, cfg.min_price)
        self.entry_max_price.insert(0, cfg.max_price)
        self.entry_min_discount.insert(0, cfg.min_discount)
        self.entry_min_rating.insert(0, cfg.min_rating)
        self.entry_white.insert(0, cfg.white_keywords)
        self.entry_black.insert(0, cfg.black_keywords)
        self.entry_pages.insert(0, str(cfg.max_pages))
        self.entry_limit.insert(0, str(cfg.limit))
        self.entry_interval.insert(0, str(cfg.interval_sec))
        self.var_feedbacks.set(cfg.with_feedbacks)
        self.var_cdn.set(cfg.enrich_cdn)
        self.var_continuous.set(cfg.continuous_monitor)

        if cfg.dest_name in DEST_CODES:
            self.opt_dest.set(cfg.dest_name)
        self.entry_proxy.insert(0, cfg.proxy_string)
        self.entry_proxy_rotate.insert(0, cfg.proxy_change_url)
        self.entry_cookies.insert(0, cfg.cookies)
        self.entry_wbaas.insert(0, cfg.wbaas_token)
        self.entry_tg_token.insert(0, cfg.tg_token)
        self.entry_tg_chat.insert(0, cfg.tg_chat_id)
        self.entry_tg_proxy.insert(0, cfg.tg_proxy)
        self.var_tg_notify.set(cfg.tg_notify)

        self.txt_rank_pairs.delete("1.0", "end")
        self.txt_rank_pairs.insert("1.0", "\n".join(cfg.rank_pairs))
        self.entry_rank_pages.insert(0, str(cfg.rank_pages))
        self.entry_review_target.insert(0, cfg.review_target)
        self.var_review_color.set(cfg.review_only_color)
        self.entry_review_ai_key.insert(0, cfg.review_ai_key)
        self.entry_review_ai_url.insert(0, cfg.review_ai_url)

    def _save_ui_to_config(self) -> WBGUIConfig:
        cfg = self.config
        raw_targets = self.txt_targets.get("1.0", "end").splitlines()
        cfg.targets = [line.strip() for line in raw_targets if line.strip()]
        cfg.min_price = self.entry_min_price.get().strip()
        cfg.max_price = self.entry_max_price.get().strip()
        cfg.min_discount = self.entry_min_discount.get().strip()
        cfg.min_rating = self.entry_min_rating.get().strip()
        cfg.white_keywords = self.entry_white.get().strip()
        cfg.black_keywords = self.entry_black.get().strip()
        cfg.max_pages = int(self.entry_pages.get().strip() or 3)
        cfg.limit = int(self.entry_limit.get().strip() or 100)
        cfg.interval_sec = int(self.entry_interval.get().strip() or 60)
        cfg.with_feedbacks = bool(self.var_feedbacks.get())
        cfg.enrich_cdn = bool(self.var_cdn.get())
        cfg.continuous_monitor = bool(self.var_continuous.get())
        cfg.dest_name = self.opt_dest.get()
        cfg.proxy_string = self.entry_proxy.get().strip()
        cfg.proxy_change_url = self.entry_proxy_rotate.get().strip()
        cfg.cookies = self.entry_cookies.get().strip()
        cfg.wbaas_token = self.entry_wbaas.get().strip()
        cfg.tg_token = self.entry_tg_token.get().strip()
        cfg.tg_chat_id = self.entry_tg_chat.get().strip()
        cfg.tg_proxy = self.entry_tg_proxy.get().strip()
        cfg.tg_notify = bool(self.var_tg_notify.get())
        raw_ranks = self.txt_rank_pairs.get("1.0", "end").splitlines()
        cfg.rank_pairs = [line.strip() for line in raw_ranks if line.strip()]
        cfg.rank_pages = int(self.entry_rank_pages.get().strip() or 3)
        cfg.review_target = self.entry_review_target.get().strip()
        cfg.review_only_color = bool(self.var_review_color.get())
        cfg.review_ai_key = self.entry_review_ai_key.get().strip()
        cfg.review_ai_url = self.entry_review_ai_url.get().strip() or "https://api.openai.com/v1"
        cfg.save()
        return cfg

    def _log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {text}")

    def _start_pollers(self) -> None:
        self._poll_queues()

    def _poll_queues(self) -> None:
        # 1. Flush logs
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.txt_logs.insert("end", line + "\n")
            self.txt_logs.see("end")

        # 2. Flush status pill updates
        while not self.status_queue.empty():
            txt, fg, bg = self.status_queue.get_nowait()
            self.status_pill.configure(text=txt, text_color=fg, fg_color=bg)

        # 3. Flush new product cards
        added = 0
        while not self.item_queue.empty() and added < 20:
            item = self.item_queue.get_nowait()
            self._render_product_card(item)
            added += 1

        self._update_stats_strip()
        self.root.after(150, self._poll_queues)

    def _update_stats_strip(self) -> None:
        self.lbl_stats_found.configure(text=f"📦 Найдено товаров: {self.stats_found}")
        self.lbl_stats_discounts.configure(text=f"📉 Со скидкой / падением: {self.stats_discounts}")
        self.lbl_stats_checks.configure(text=f"⏱️ Запусков: {self.stats_checks}")
        self.lbl_stats_tg.configure(text=f"✈️ Отправлено в TG: {self.stats_tg}")

    def _render_product_card(self, product: WBProduct) -> None:
        if self.lbl_empty_feed.winfo_exists():
            self.lbl_empty_feed.destroy()

        card = ctk.CTkFrame(self.feed_scroll, fg_color="#1e293b", corner_radius=8)
        card.pack(fill="x", padx=6, pady=5)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 4))

        price_str = f"{product.price:,.0f} ₽" if product.price > 0 else "CDN Карточка"
        if product.wallet_price:
            price_str += f" (💳 {product.wallet_price:,.0f} ₽)"
        if product.discount > 0:
            price_str += f" (-{product.discount}%)"
        if product.price_drop:
            price_str += f" (📉 -{product.price_drop:,.0f} ₽)"

        ctk.CTkLabel(
            top,
            text=product.name or f"Товар {product.id}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f8fafc",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            top,
            text=price_str,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#a78bfa",
        ).pack(side="right", padx=6)

        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(0, 8))

        shard_note = f"feedbacks{product.feedback_shard}" if product.feedback_shard else "feedbacks"
        info_text = (
            f"🆔 nm={product.id} | root={product.root} ({shard_note}) | "
            f"🏷 {product.brand or '—'} | ⭐ {product.valuation or product.rating or '—'} "
            f"({product.feedback_count} отз.) | Фото: {len(product.image_links)} .webp"
        )
        ctk.CTkLabel(
            meta,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        ).pack(side="left")

        if product.card_json_url:
            ctk.CTkButton(
                meta,
                text="CDN JSON",
                width=85,
                height=24,
                fg_color="#334155",
                hover_color="#475569",
                font=ctk.CTkFont(size=11),
                command=lambda u=product.card_json_url: webbrowser.open(u),
            ).pack(side="right", padx=4)

        ctk.CTkButton(
            meta,
            text="Открыть на WB ↗",
            width=125,
            height=24,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda u=product.url: webbrowser.open(u),
        ).pack(side="right", padx=4)

    def _start_scrape(self) -> None:
        if self.is_running:
            return
        cfg = self._save_ui_to_config()
        if not cfg.targets:
            self._log("[!] Укажите хотя бы одну ссылку, артикул (nm_id) или запрос.")
            return

        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_queue.put(("● РАБОТАЕТ", "#38bdf8", "#0c4a6e"))

        self.worker_thread = threading.Thread(target=self._worker_loop, args=(cfg,), daemon=True)
        self.worker_thread.start()

    def _stop_scrape(self) -> None:
        self.stop_event.set()
        self._log("Остановка запрошена пользователем...")
        self.status_queue.put(("● ОСТАНОВКА...", "#f59e0b", "#451a03"))

    def _worker_loop(self, cfg: WBGUIConfig) -> None:
        dest = DEST_CODES.get(cfg.dest_name, DEFAULT_DEST)
        try:
            with WBClient(
                dest=dest,
                proxy=cfg.proxy_string or None,
                proxy_change_url=cfg.proxy_change_url or None,
                cookies=cfg.cookies or None,
                wbaas_token=cfg.wbaas_token or None,
                tracker_db=str(_get_base_dir() / "storage" / "wb_prices.db"),
            ) as client:
                try:
                    routes = client.sync_upstreams()
                    self._log(f"Синхронизировано {routes} живых CDN-баскетов с cdn.wbbasket.ru")
                except Exception as exc:
                    self._log(f"Используется встроенная таблица basket-01..65 ({exc})")

                notifier = (
                    TelegramNotifier(cfg.tg_token, cfg.tg_chat_id, proxy=cfg.tg_proxy or None)
                    if (cfg.tg_notify and cfg.tg_token and cfg.tg_chat_id)
                    else None
                )

                while not self.stop_event.is_set():
                    self.stats_checks += 1
                    self._log(f"Запуск #{self.stats_checks}: обработка {len(cfg.targets)} целей...")
                    try:
                        raw = client.scrape_targets(
                            cfg.targets,
                            max_pages=cfg.max_pages,
                            limit_per_target=cfg.limit,
                            enrich_cdn=cfg.enrich_cdn,
                            with_feedbacks=cfg.with_feedbacks,
                        )
                        min_p = int(cfg.min_price) if cfg.min_price.isdigit() else 0
                        max_p = int(cfg.max_price) if cfg.max_price.isdigit() else 999_999_999
                        min_d = int(cfg.min_discount) if cfg.min_discount.isdigit() else 0
                        try:
                            min_r = float(cfg.min_rating.replace(",", ".")) if cfg.min_rating else 0.0
                        except ValueError:
                            min_r = 0.0

                        whites = [x.strip() for x in cfg.white_keywords.split(",") if x.strip()]
                        blacks = [x.strip() for x in cfg.black_keywords.split(",") if x.strip()]

                        filtered = filter_products(
                            raw,
                            min_price=min_p,
                            max_price=max_p,
                            min_discount=min_d,
                            min_rating=min_r,
                            white_keywords=whites,
                            black_keywords=blacks,
                        )

                        new_count = 0
                        for item in filtered:
                            if item.id not in self.seen_ids:
                                self.seen_ids.add(item.id)
                                self.discovered_items.append(item)
                                self.stats_found += 1
                                if item.discount > 0 or item.price_drop:
                                    self.stats_discounts += 1
                                self.item_queue.put(item)
                                new_count += 1
                                if notifier and notifier.send_product(item):
                                    self.stats_tg += 1
                        self._log(f"Цикл завершён: получено {len(filtered)}, новых в ленте: {new_count}.")
                    except WBAntiBotError as exc:
                        self._log(f"[WBAAS 498/403] {exc}")
                    except Exception as exc:
                        self._log(f"[Ошибка цикла] {exc}")

                    if not cfg.continuous_monitor:
                        break
                    self.stop_event.wait(max(5, cfg.interval_sec))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.btn_start.configure(state="normal"))
            self.root.after(0, lambda: self.btn_stop.configure(state="disabled"))
            self.status_queue.put(("● ГОТОВ К РАБОТЕ", "#22c55e", "#064e3b"))

    def _build_client_from_cfg(self, cfg: WBGUIConfig) -> WBClient:
        return WBClient(
            dest=DEST_CODES.get(cfg.dest_name, DEFAULT_DEST),
            proxy=cfg.proxy_string or None,
            proxy_change_url=cfg.proxy_change_url or None,
            cookies=cfg.cookies or None,
            wbaas_token=cfg.wbaas_token or None,
            tracker_db=str(_get_base_dir() / "storage" / "wb_prices.db"),
        )

    def _run_rank_check(self) -> None:
        cfg = self._save_ui_to_config()
        pairs: List[tuple[str, str]] = []
        for line in cfg.rank_pairs:
            if ":" in line:
                left, right = line.split(":", 1)
                pairs.append((left.strip(), right.strip()))
        if not pairs:
            self._log("[!] Укажите пары вида `артикул : запрос` во вкладке Позиции.")
            return

        self.btn_rank_check.configure(state="disabled")
        sort_mode = self.opt_rank_sort.get()

        def worker() -> None:
            try:
                with self._build_client_from_cfg(cfg) as c:
                    tracker = WBRankTracker(c, db_path=str(_get_base_dir() / "storage" / "wb_prices.db"))
                    res = tracker.check_batch(pairs, max_pages=cfg.rank_pages, sort=sort_mode)
                self.rank_results = res
                self.root.after(0, lambda: self._render_rank_results(res))
            except WBAntiBotError as exc:
                self._log(f"[Rank WBAAS 498/403] {exc}")
            except Exception as exc:
                self._log(f"[Ошибка Rank] {exc}")
            finally:
                self.root.after(0, lambda: self.btn_rank_check.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _render_rank_results(self, results: List[RankResult]) -> None:
        for child in self.rank_scroll.winfo_children():
            child.destroy()
        if not results:
            ctk.CTkLabel(self.rank_scroll, text="Совпадений не найдено.", text_color="#94a3b8").pack(pady=30)
            return

        for r in results:
            card = ctk.CTkFrame(self.rank_scroll, fg_color="#1e293b", corner_radius=8)
            card.pack(fill="x", padx=6, pady=4)
            pos_str = f"#{r.position} (стр. {r.page}, слот {r.page_position})" if r.position else f"Не найден (проверено {r.total_scanned})"
            delta_str = ""
            pos_color = "#a78bfa" if r.position else "#ef4444"
            if r.rank_delta is not None:
                if r.rank_delta > 0:
                    delta_str = f"  ▲ +{r.rank_delta}"
                elif r.rank_delta < 0:
                    delta_str = f"  ▼ {r.rank_delta}"
                else:
                    delta_str = "  = 0"

            ctk.CTkLabel(
                card,
                text=f"🔎 «{r.query}» • nm={r.nm_id}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#f8fafc",
            ).pack(side="left", padx=12, pady=8)

            ctk.CTkLabel(
                card,
                text=f"{pos_str}{delta_str}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=pos_color,
            ).pack(side="right", padx=12, pady=8)

    def _export_rank_excel(self) -> None:
        if not self.rank_results:
            self._log("Нет результатов позиций для экспорта.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            rank_results_to_excel(self.rank_results, path)
            self._log(f"Позиции экспортированы в Excel: {path}")

    def _run_review_analysis(self) -> None:
        cfg = self._save_ui_to_config()
        if not cfg.review_target:
            self._log("[!] Введите артикул или ссылку во вкладке «Умные отзывы».")
            return

        self.btn_review_run.configure(state="disabled")
        self.lbl_review_kpi.configure(text="⏳ Загрузка карточки с CDN и отзывов с feedbacks1/2...")

        def worker() -> None:
            try:
                with self._build_client_from_cfg(cfg) as c:
                    summary = c.analyze_reviews(
                        cfg.review_target,
                        only_this_color=cfg.review_only_color,
                        limit=120,
                        ai_key=cfg.review_ai_key or None,
                        ai_base_url=cfg.review_ai_url,
                    )
                self.root.after(0, lambda: self._render_review_summary(summary))
            except Exception as exc:
                self._log(f"[Ошибка Smart Review] {exc}")
                self.root.after(0, lambda: self.lbl_review_kpi.configure(text=f"❌ Ошибка: {exc}"))
            finally:
                self.root.after(0, lambda: self.btn_review_run.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _render_review_summary(self, s: ReviewSummary) -> None:
        fit_str = ", ".join(f"{k}: {v}" for k, v in s.size_fit.items()) if s.size_fit else "н/д"
        scope = "цвет nm_id" if s.filtered_by_nm else "вся карточка root_id"
        self.lbl_review_kpi.configure(
            text=(
                f"🛍 {s.product_name[:55]} | ⭐ {s.avg_rating} | Отзывов: {s.total_analyzed}/{s.total_available} "
                f"| Шард: feedbacks{s.shard} ({scope}) | Размер: {fit_str} | [{s.summary_mode}]"
            )
        )
        self.txt_review_pros.delete("1.0", "end")
        self.txt_review_pros.insert("1.0", "\n".join(f"• {x}" for x in s.top_pros) or "Нет выделенных плюсов")

        self.txt_review_cons.delete("1.0", "end")
        self.txt_review_cons.insert("1.0", "\n".join(f"• {x}" for x in s.top_cons) or "Существенных минусов не найдено")

        for child in self.reviews_scroll.winfo_children():
            child.destroy()
        for rev in s.reviews[:40]:
            box = ctk.CTkFrame(self.reviews_scroll, fg_color="#1e293b", corner_radius=6)
            box.pack(fill="x", padx=6, pady=4)
            parts = []
            if rev.pros:
                parts.append(f"+ {rev.pros}")
            if rev.cons:
                parts.append(f"- {rev.cons}")
            if rev.text:
                parts.append(rev.text)
            body = " | ".join(parts)
            ctk.CTkLabel(
                box,
                text=f"[{rev.rating}★] {body[:280]}",
                anchor="w",
                justify="left",
                wraplength=980,
                font=ctk.CTkFont(size=12),
                text_color="#e2e8f0",
            ).pack(fill="x", padx=10, pady=6)

    def _test_proxy_connectivity(self) -> None:
        cfg = self._save_ui_to_config()
        self.lbl_proxy_status.configure(text="⏳ Проверка...", text_color="#facc15")

        def run_check() -> None:
            with WBClient(proxy=cfg.proxy_string or None) as c:
                res = c.ping()
                w = c.wallet.fetch_settings()
            if res["ok"]:
                msg = (
                    f"✅ OK • {res['latency_ms']} мс ({res['tls']}) • "
                    f"WB Кошелёк: {w.wallet_discount_pct}% / Клуб: {w.club_discount_pct}% (до {w.max_price} ₽)"
                )
                color = "#22c55e"
            else:
                msg = f"❌ Ошибка: {res.get('error', res['status_code'])}"
                color = "#ef4444"
            self.root.after(0, lambda: self.lbl_proxy_status.configure(text=msg, text_color=color))

        threading.Thread(target=run_check, daemon=True).start()

    def _test_telegram(self) -> None:
        cfg = self._save_ui_to_config()
        if not cfg.tg_token or not cfg.tg_chat_id:
            self._log("[!] Заполните Bot Token и Chat ID во вкладке Telegram.")
            return
        notifier = TelegramNotifier(cfg.tg_token, cfg.tg_chat_id, proxy=cfg.tg_proxy or None)
        ok = notifier.send_message("✅ <b>WB SDK Pro</b>: подключение Telegram настроено успешно!")
        self._log("Тест Telegram: отправлено успешно!" if ok else "[!] Ошибка отправки в Telegram.")

    def _export_excel(self) -> None:
        if not self.discovered_items:
            self._log("Нет данных для экспорта.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            to_excel(self.discovered_items, path)
            self._log(f"Экспортировано в Excel: {path}")

    def _export_csv(self) -> None:
        if not self.discovered_items:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            to_csv(self.discovered_items, path)
            self._log(f"Экспортировано в CSV: {path}")

    def _export_json(self) -> None:
        if not self.discovered_items:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            to_json(self.discovered_items, path)
            self._log(f"Экспортировано в JSON: {path}")

    def _clear_feed(self) -> None:
        for child in self.feed_scroll.winfo_children():
            child.destroy()
        self.discovered_items.clear()
        self.seen_ids.clear()
        self.stats_found = 0
        self.stats_discounts = 0

    def _on_close(self) -> None:
        self.stop_event.set()
        self._save_ui_to_config()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
