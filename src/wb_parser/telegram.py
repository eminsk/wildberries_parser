"""
Telegram notification helper with separate proxy support (decoupled from WB proxies).
"""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Optional

import httpx

from wb_parser.models import WBProduct

logger = logging.getLogger("wb_parser.telegram")


class TelegramNotifier:
    """Lightweight Telegram Bot API client for sending WB deal/product alerts & Excel reports."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        proxy: Optional[str] = None,
        timeout: float = 15.0,
    ) -> None:
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()
        self.proxy = proxy.strip() if proxy and proxy.strip() else None
        self.timeout = float(timeout)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    @staticmethod
    def format_product_message(product: WBProduct) -> str:
        """Build rich HTML-formatted Telegram alert card for a Wildberries product."""
        title = html.escape(product.name or f"Артикул {product.id}")
        brand = html.escape(product.brand or "—")
        price_line = f"<b>{product.price:,.0f} ₽</b>" if product.price > 0 else "<b>Цена уточняется</b>"
        if product.wallet_price:
            price_line += f" (💳 Кошелёк: <b>{product.wallet_price:,.0f} ₽</b>)"
        if product.discount > 0:
            price_line += f"  <i>(-{product.discount}%)</i>"
        if product.price_drop:
            price_line += f"  📉 <b>Снижение на -{product.price_drop:,.0f} ₽</b>"

        rating_str = product.valuation or (f"{product.rating:.1f}" if product.rating else "—")
        lines = [
            f"🛍 <b>{title}</b>",
            f"🏷 Бренд: {brand} | 🆔 <code>{product.id}</code>",
            f"💰 Цена: {price_line}",
            f"⭐ Рейтинг: {rating_str} | 💬 Отзывов: {product.feedback_count}",
        ]
        if product.supplier_id:
            lines.append(f"🏪 Продавец ID: <code>{product.supplier_id}</code>")
        lines.append(f"🔗 <a href=\"{html.escape(product.url)}\">Открыть на Wildberries ↗</a>")
        return "\n".join(lines)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a plain/HTML message to configured Telegram chat."""
        if not self.bot_token or not self.chat_id:
            return False
        try:
            with httpx.Client(proxy=self.proxy, timeout=self.timeout) as client:
                r = client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": False,
                    },
                )
                return r.status_code == 200
        except Exception as exc:
            logger.warning(f"Telegram send_message failed: {exc}")
            return False

    def send_product(self, product: WBProduct) -> bool:
        """Send formatted Wildberries product card alert."""
        return self.send_message(self.format_product_message(product))

    def send_document(self, filepath: Path, caption: str = "") -> bool:
        """Upload an Excel / CSV / JSON report to Telegram chat."""
        if not self.bot_token or not self.chat_id or not filepath.exists():
            return False
        try:
            with httpx.Client(proxy=self.proxy, timeout=max(30.0, self.timeout)) as client:
                with open(filepath, "rb") as f:
                    r = client.post(
                        f"{self.base_url}/sendDocument",
                        data={"chat_id": self.chat_id, "caption": caption[:1024]},
                        files={"document": (filepath.name, f)},
                    )
                return r.status_code == 200
        except Exception as exc:
            logger.warning(f"Telegram send_document failed: {exc}")
            return False
