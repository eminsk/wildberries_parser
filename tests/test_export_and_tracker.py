"""
Tests for multi-format exporters (Excel, CSV, JSON, JSONL) and SQLite WBPriceTracker.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from wb_parser.export import _excel_safe, to_csv, to_excel, to_json, to_jsonl
from wb_parser.models import WBProduct
from wb_parser.tracker import WBPriceTracker


def _sample_products():
    return [
        WBProduct(
            id=141217830,
            root=181851928,
            name="=CMD('calc') Кроссовки Dunk",
            brand="Nike",
            subject="Кроссовки",
            price=4990.0,
            basic_price=7990.0,
            wallet_price=4890.0,
            old_price=5500.0,
            discount=38,
            rating=4.9,
            valuation="4.9",
            feedback_count=312,
            volume=15,
            supplier_id=626520,
            url="https://www.wildberries.ru/catalog/141217830/detail.aspx",
            image_links=["https://basket-10.wbbasket.ru/vol1412/part141217/141217830/images/big/1.webp"],
            specs={"Цвет": "серый"},
        )
    ]


def test_excel_formula_injection_guard():
    assert _excel_safe("=1+1") == "'=1+1"
    assert _excel_safe("+cmd") == "'+cmd"
    assert _excel_safe("normal string") == "normal string"


def test_exporters_roundtrip(tmp_path: Path):
    products = _sample_products()

    xlsx_path = to_excel(products, tmp_path / "catalog.xlsx")
    assert xlsx_path.exists()
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    assert ws.cell(row=2, column=1).value == 141217830
    assert str(ws.cell(row=2, column=3).value).startswith("'=CMD")
    assert ws.cell(row=2, column=7).value == 4890.0  # wallet_price
    assert ws.cell(row=2, column=10).value == 510.0  # price_drop
    assert ws.cell(row=2, column=15).hyperlink.target == "https://www.wildberries.ru/catalog/141217830/detail.aspx"

    csv_path = to_csv(products, tmp_path / "catalog.csv")
    assert csv_path.exists()
    assert "141217830" in csv_path.read_text(encoding="utf-8-sig")

    json_path = to_json(products, tmp_path / "catalog.json")
    assert json_path.exists()
    assert '"supplier_id": 626520' in json_path.read_text(encoding="utf-8")

    jsonl_path = to_jsonl(products, tmp_path / "catalog.jsonl")
    assert jsonl_path.exists()
    assert len(jsonl_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_sqlite_price_tracker_drop_detection(tmp_path: Path):
    db_file = tmp_path / "prices.db"
    tracker = WBPriceTracker(db_file)

    p1 = WBProduct(id=101, root=201, name="Товар А", price=2000.0, basic_price=2500.0, discount=20)
    tracker.track_products([p1])
    assert tracker.get_price_drops() == []

    # Price drops on second observation
    p2 = WBProduct(id=101, root=201, name="Товар А", price=1650.0, basic_price=2500.0, discount=34)
    tracker.track_products([p2])
    assert p2.old_price == 2000.0
    assert p2.price_drop == 350.0

    drops = tracker.get_price_drops()
    assert len(drops) == 1
    assert drops[0].price == 1650.0
    assert drops[0].old_price == 2000.0

    hist = tracker.get_history(101)
    assert [h.price for h in hist] == [2000.0, 1650.0]
