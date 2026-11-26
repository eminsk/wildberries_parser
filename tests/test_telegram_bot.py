"""Tests for WBTelegramBot, upgraded TelegramNotifier, reviews_to_excel, and CLI `bot` command."""

from __future__ import annotations

from pathlib import Path

from wb_parser import (
    BotInstanceLock,
    ReviewItem,
    ReviewSummary,
    TelegramNotifier,
    WBProduct,
    WBPriceTracker,
    WBTelegramBot,
    mask_proxy_url,
    normalize_tg_proxy,
    render_progress_bar,
    render_telegram_progress_bar,
    reviews_to_excel,
)
from wb_parser.cli import main as cli_main


def test_helpers_proxy_masking_and_progress_bars() -> None:
    assert "50%" in render_progress_bar(5, 10, width=10)
    assert "█████░░░░░" in render_progress_bar(5, 10, width=10)
    assert "🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜ 50%" in render_telegram_progress_bar(5, 10, width=10)

    assert normalize_tg_proxy("u:p@127.0.0.1:1080") == "http://u:p@127.0.0.1:1080"
    assert normalize_tg_proxy("socks5://127.0.0.1:1080") == "socks5://127.0.0.1:1080"

    masked = mask_proxy_url("http://myuser:supersecret@mproxy.site:12411")
    assert "supersecret" not in masked
    assert "mproxy.site:12411" in masked
    assert mask_proxy_url(None) == "НЕ ПОДКЛЮЧЕН (прямой IP)"


def test_notifier_progress_excel_and_reviews_export(tmp_path: Path, monkeypatch) -> None:
    posts = []

    def fake_post(self, method, *, json_payload=None, data=None, files=None, timeout=None):
        posts.append((method, json_payload, data, bool(files), self.proxy))
        if method == "sendMessage":
            return True, {"ok": True, "result": {"message_id": 100 + len(posts)}}
        return True, {"ok": True}

    monkeypatch.setattr(TelegramNotifier, "_post", fake_post)

    notifier = TelegramNotifier("123:ABC", "111, 222", proxy="127.0.0.1:1080")
    assert notifier.chat_ids == ["111", "222"]
    assert notifier.send_message("hello") is True

    pids = notifier.start_progress("кроссовки", total=20, use_mobile_proxy=True, workers=4)
    assert pids == {"111": 103, "222": 104}
    notifier.update_progress(pids, "кроссовки", 10, 20, use_mobile_proxy=True, workers=4, drops_count=2, ip_rotations=1)

    csv_fallback = tmp_path / "report.csv"
    csv_fallback.write_text("col\nval\n", encoding="utf-8")
    notifier.finish_progress(pids, "кроссовки", 10, excel_path=tmp_path / "report.xlsx")
    assert any(p[0] == "sendDocument" and p[3] is True for p in posts)

    summary = ReviewSummary(
        nm_id=141217830,
        root_id=181851928,
        product_name="Кроссовки Dunk",
        shard=1,
        total_available=2,
        total_analyzed=1,
        avg_rating=4.9,
        size_fit={"ok": 1},
        top_pros=["Удобные"],
        top_cons=["Маломерят на полразмера"],
        reviews=[ReviewItem(id="r1", nmId=141217830, productValuation=5, pros="Мягкие", text="Супер")],
    )
    rev_xlsx = reviews_to_excel(summary, tmp_path / "wb_reviews.xlsx")
    assert rev_xlsx.exists() and rev_xlsx.stat().st_size > 1000
    assert notifier.send_review_summary(summary) is True


def test_wb_telegram_bot_commands_callbacks_and_batch(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "wb_bot.db"
    tracker = WBPriceTracker(db_file)
    tracker.track_products([WBProduct(id=141217830, root=181851928, name="Кроссовки", price=6000.0)])
    tracker.track_products([WBProduct(id=141217830, root=181851928, name="Кроссовки", price=4800.0)])

    sent_texts = []
    edited_texts = []

    monkeypatch.setattr(
        TelegramNotifier,
        "send_message",
        lambda self, text, parse_mode="HTML", **kw: sent_texts.append((text, self.proxy)) or True,
    )
    monkeypatch.setattr(
        TelegramNotifier,
        "_send_message_impl",
        lambda self, text, **kw: (sent_texts.append((text, self.proxy)) or {cid: 55 for cid in self.chat_ids}, True),
    )
    monkeypatch.setattr(
        TelegramNotifier,
        "edit_message",
        lambda self, cid, mid, text, **kw: edited_texts.append(text) or True,
    )
    monkeypatch.setattr(TelegramNotifier, "answer_callback", lambda self, cb_id, text=None, **kw: True)
    monkeypatch.setattr(TelegramNotifier, "send_excel", lambda self, fp, caption="", **kw: True)

    bot = WBTelegramBot(
        bot_token="999:WB_TEST_TOKEN",
        tg_proxy="socks5://127.0.0.1:1080",
        tracker_db=db_file,
    )

    bot.handle_update({"message": {"chat": {"id": 777}, "text": "/start"}})
    bot.handle_update({"message": {"chat": {"id": 777}, "text": "/drops"}})
    bot.handle_update({"message": {"chat": {"id": 777}, "text": "/proxy http://user1:secretPass@1.2.3.4:8080 MYKEY77"}})
    assert bot.proxy == "http://user1:secretPass@1.2.3.4:8080"
    assert bot.proxy_change_url == "https://changeip.mobileproxy.space/?proxy_key=MYKEY77&format=json"
    assert not any("secretPass" in txt for txt, _ in sent_texts)
    assert any("1,200" in txt or "4,800" in txt for txt, _ in sent_texts)
    assert all(proxy == "socks5://127.0.0.1:1080" for _, proxy in sent_texts)

    bot.handle_update({"message": {"chat": {"id": 777}, "text": "/workers 99"}})
    assert bot.workers == 16
    bot.handle_update({"message": {"chat": {"id": 777}, "text": "/limit 9000"}})
    assert bot.limit == 5000

    bot.handle_callback({"id": "cb1", "message": {"chat": {"id": 777}, "message_id": 10}, "data": "set_workers:4"})
    assert bot.workers == 4
    bot.handle_callback({"id": "cb2", "message": {"chat": {"id": 777}, "message_id": 10}, "data": "set_limit:200"})
    assert bot.limit == 200
    bot.handle_callback({"id": "cb3", "message": {"chat": {"id": 777}, "message_id": 10}, "data": "toggle_enrich"})
    assert bot.enrich_cdn is False

    # Multiline batch workflow
    flow_calls = []
    dummy_xlsx = tmp_path / "dummy.xlsx"
    dummy_xlsx.write_bytes(b"PK\x03\x04")
    monkeypatch.setattr(
        bot,
        "_run_search_flow",
        lambda cid, q, on_progress=None, suppress_individual_progress=False: (flow_calls.append(q) or (3, dummy_xlsx)),
    )
    bot.handle_update({
        "message": {
            "chat": {"id": 777},
            "text": "https://www.wildberries.ru/catalog/141217830/detail.aspx\nhttps://www.wildberries.ru/seller/626520",
        }
    })
    if bot._last_worker_thread:
        bot._last_worker_thread.join(timeout=3.0)
    assert len(flow_calls) == 2
    assert "141217830" in flow_calls[0]
    assert "626520" in flow_calls[1]


def test_bot_instance_lock_and_cli_bot_validation(monkeypatch, capsys) -> None:
    lock = BotInstanceLock("unique_test_token_wb_12345")
    lock.acquire()
    try:
        assert lock.acquired is True
    finally:
        lock.release()
    assert lock.acquired is False

    monkeypatch.delenv("WB_TG_TOKEN", raising=False)
    rc = cli_main(["bot"])
    assert rc == 1
    assert "WB_TG_TOKEN" in capsys.readouterr().err


def test_wb_bot_wallet_rank_reviews_and_cli_tg_export(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace
    from wb_parser.client import WBClient
    from wb_parser.rank import RankResult

    messages = []
    excels = []
    monkeypatch.setattr(TelegramNotifier, "send_message", lambda self, txt, **kw: messages.append(txt) or True)
    monkeypatch.setattr(TelegramNotifier, "send_review_summary", lambda self, s: messages.append(s.product_name) or True)
    monkeypatch.setattr(TelegramNotifier, "send_excel", lambda self, fp, caption="", **kw: excels.append(Path(fp).name) or True)

    monkeypatch.setattr(
        WBClient,
        "wallet_price",
        lambda self, price, *, use_club=False: SimpleNamespace(
            base_price=float(price), wallet_price=4750.0, discount_pct=5.0, savings=250.0
        ),
    )
    monkeypatch.setattr(
        WBClient,
        "check_rank",
        lambda self, target, query, **kw: RankResult(
            nm_id=141217830, query=query, position=3, page=1, page_position=3, total_scanned=100, price=4990.0
        ),
    )
    monkeypatch.setattr(
        WBClient,
        "analyze_reviews",
        lambda self, target, **kw: ReviewSummary(
            nm_id=141217830, root_id=181851928, product_name="SB Dunk", avg_rating=4.8, top_pros=["Удобные"]
        ),
    )
    monkeypatch.setattr(
        WBClient,
        "search",
        lambda self, q, **kw: [WBProduct(id=141217830, root=181851928, name="SB Dunk", price=4990.0)],
    )

    bot = WBTelegramBot(bot_token="999:WB_FLOW", tracker_db=tmp_path / "wb_flow.db")
    bot.handle_update({"message": {"chat": {"id": 888}, "text": "/wallet 5000"}})
    assert any("4,750" in m for m in messages)

    bot.handle_update({"message": {"chat": {"id": 888}, "text": "/rank 141217830 кроссовки"}})
    if bot._last_worker_thread:
        bot._last_worker_thread.join(timeout=3.0)
    bot.handle_update({"message": {"chat": {"id": 888}, "text": "/reviews 141217830"}})
    if bot._last_worker_thread:
        bot._last_worker_thread.join(timeout=3.0)

    out_xlsx = tmp_path / "cli_search.xlsx"
    rc = cli_main([
        "search", "кроссовки", "-o", str(out_xlsx),
        "--db", str(tmp_path / "cli_s.db"),
        "--tg-token", "999:CLI", "--tg-chat-id", "888",
    ])
    assert rc == 0
    assert out_xlsx.exists()
    assert len(excels) >= 3
