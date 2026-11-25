"""
Multi-format exporters for Wildberries Parser SDK:
Styled Excel (.xlsx), UTF-8 BOM CSV, JSON, JSONL, and Pandas DataFrame.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, List, Union

from wb_parser.models import WBProduct


def _excel_safe(value: Any) -> Any:
    """Prevent CSV/Excel formula injection on strings beginning with =, +, -, @."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def to_json(products: List[WBProduct], filepath: Union[str, Path], indent: int = 2) -> Path:
    """Export products to formatted UTF-8 JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [p.to_dict() for p in products]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


def to_jsonl(products: List[WBProduct], filepath: Union[str, Path]) -> Path:
    """Export products to newline-delimited JSON Lines (JSONL) file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p in products:
            f.write(p.to_json() + "\n")
    return path


def to_csv(
    products: List[WBProduct],
    filepath: Union[str, Path],
    delimiter: str = ";",
) -> Path:
    """Export products to UTF-8 BOM CSV (opens cleanly in Russian Excel without encoding garbling)."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "nm_id",
        "root_id",
        "name",
        "brand",
        "subject",
        "price",
        "basic_price",
        "discount_pct",
        "old_price",
        "price_drop",
        "rating",
        "valuation",
        "feedback_count",
        "volume",
        "supplier_id",
        "url",
        "image_links",
        "specs",
    ]

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        for p in products:
            specs_str = "; ".join(f"{k}: {v}" for k, v in p.specs.items())
            writer.writerow(
                {
                    "nm_id": p.id,
                    "root_id": p.root,
                    "name": p.name,
                    "brand": p.brand,
                    "subject": p.subject,
                    "price": p.price,
                    "basic_price": p.basic_price,
                    "discount_pct": p.discount,
                    "old_price": p.old_price if p.old_price is not None else "",
                    "price_drop": p.price_drop if p.price_drop is not None else "",
                    "rating": p.rating,
                    "valuation": p.valuation,
                    "feedback_count": p.feedback_count,
                    "volume": p.volume,
                    "supplier_id": p.supplier_id,
                    "url": p.url,
                    "image_links": p.image_links_str,
                    "specs": specs_str,
                }
            )
    return path


def to_excel(
    products: List[WBProduct],
    filepath: Union[str, Path],
    sheet_name: str = "Wildberries Catalog",
) -> Path:
    """Export products to a styled `.xlsx` spreadsheet with clickable WB links and price-drop highlights."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:  # pragma: no cover
        return to_csv(products, path.with_suffix(".csv"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]

    headers = [
        "Артикул (nm_id)",
        "Root ID (imt_id)",
        "Название",
        "Бренд",
        "Категория",
        "Цена (₽)",
        "До скидки (₽)",
        "Скидка (%)",
        "Снижение цены (₽)",
        "Рейтинг",
        "Отзывы (текст)",
        "Остаток",
        "ID продавца",
        "Ссылка WB",
        "Главное фото (.webp)",
        "Характеристики",
    ]

    header_fill = PatternFill(start_color="4C1D95", end_color="4C1D95", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    drop_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    link_font = Font(color="2563EB", underline="single")

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.freeze_panes = "A2"

    for row_idx, p in enumerate(products, start=2):
        specs_str = "\n".join(f"{k}: {v}" for k, v in p.specs.items())
        main_img = p.image_links[0] if p.image_links else ""
        drop_val = p.price_drop if p.price_drop is not None else 0

        row_values = [
            p.id,
            p.root,
            _excel_safe(p.name),
            _excel_safe(p.brand),
            _excel_safe(p.subject),
            p.price,
            p.basic_price,
            p.discount,
            drop_val if drop_val > 0 else "",
            p.valuation or p.rating,
            p.feedback_count,
            p.volume,
            p.supplier_id,
            p.url,
            main_img,
            _excel_safe(specs_str),
        ]
        ws.append(row_values)

        if p.url:
            c_url = ws.cell(row=row_idx, column=14)
            c_url.hyperlink = p.url
            c_url.font = link_font

        if main_img:
            c_img = ws.cell(row=row_idx, column=15)
            c_img.hyperlink = main_img
            c_img.font = link_font

        if drop_val > 0:
            ws.cell(row=row_idx, column=6).fill = drop_fill
            ws.cell(row=row_idx, column=9).fill = drop_fill

    col_widths = {
        1: 16,
        2: 16,
        3: 42,
        4: 20,
        5: 20,
        6: 12,
        7: 14,
        8: 12,
        9: 16,
        10: 10,
        11: 14,
        12: 10,
        13: 14,
        14: 36,
        15: 36,
        16: 44,
    }
    for col_idx, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    wb.save(str(path))
    return path


def to_dataframe(products: List[WBProduct]) -> Any:
    """Convert products to a `pandas.DataFrame` (requires `pandas` optional dependency)."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pandas is required for to_dataframe(): uv add pandas") from exc
    return pd.DataFrame([p.to_dict() for p in products])
