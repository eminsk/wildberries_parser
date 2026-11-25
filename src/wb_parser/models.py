"""
Typed data models for Wildberries Parser SDK.

Supports both modern Wildberries v2/v4 schemas (`sizes[].price.product / basic`)
and legacy catalog schemas (`salePriceU`, `priceU`), as well as direct `wbbasket.ru` CDN cards.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from wb_parser._model import BaseModel, ConfigDict, Field, model_validator


def _extract_kopecks(val: Any) -> Optional[float]:
    """Convert raw integer kopeck prices (e.g. 245000) to ruble floats (2450.0)."""
    if val is None:
        return None
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return 0.0
    return round(num / 100.0, 2)


class FeedbackInfo(BaseModel):
    """Product feedback summary returned by `feedbacks1/2.wb.ru`."""

    model_config = ConfigDict(extra="ignore")

    root_id: int = 0
    shard: int = 1
    feedback_count: int = Field(default=0, alias="feedbackCountWithText")
    total_feedback_count: int = Field(default=0, alias="feedbackCount")
    valuation: str = "0.0"
    valuation_distribution: Dict[str, int] = Field(
        default_factory=dict, alias="valuationDistributionPercent"
    )
    feedbacks: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def valuation_float(self) -> float:
        """Numeric average rating extracted from string valuation."""
        try:
            return float(str(self.valuation).replace(",", "."))
        except ValueError:
            return 0.0


class WBProduct(BaseModel):
    """Unified product representation combining catalog, CDN card, and feedback data."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int = Field(alias="nm_id")
    root: int = Field(default=0, alias="imt_id")
    name: str = ""
    brand: str = ""
    supplier: str = ""
    supplier_id: int = Field(default=0, alias="supplierId")
    subject: str = ""
    subject_id: int = 0
    vendor_code: str = ""
    description: str = ""

    price: float = 0.0
    basic_price: float = 0.0
    wallet_price: Optional[float] = None
    wallet_discount_pct: Optional[float] = None
    old_price: Optional[float] = None
    discount: int = Field(default=0, alias="sale")

    rating: float = 0.0
    review_rating: float = 0.0
    volume: int = 0
    pics: int = 0

    feedback_count: int = 0
    valuation: str = ""
    feedback_shard: Optional[int] = None

    url: str = ""
    card_json_url: str = ""
    image_links: List[str] = Field(default_factory=list)
    specs: Dict[str, str] = Field(default_factory=dict)
    sizes: List[str] = Field(default_factory=list)
    color_ids: List[int] = Field(default_factory=list)
    price_history: List[Dict[str, Any]] = Field(default_factory=list)
    collected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_wb_payload(cls, raw: Any) -> Any:
        """Normalize legacy catalog fields, v2/v4 `sizes[].price`, and `card.json` payloads."""
        if not isinstance(raw, dict):
            return raw

        data = dict(raw)

        # Normalize product ID & root ID across card.json (`nm_id`, `imt_id`) & API (`id`, `root`)
        nm_id = int(data.get("id") or data.get("nm_id") or data.get("nmId") or 0)
        if nm_id:
            data["id"] = nm_id
            data["nm_id"] = nm_id
        root_id = int(data.get("root") or data.get("imt_id") or data.get("imtId") or nm_id)
        data["root"] = root_id

        # Name fallback (`imt_name` in card.json vs `name` in search/catalog)
        if not data.get("name"):
            data["name"] = str(data.get("imt_name") or data.get("title") or "").strip()

        # Brand & supplier inside `selling` block (card.json)
        selling = data.get("selling")
        if isinstance(selling, dict):
            data.setdefault("brand", selling.get("brand_name") or "")
            if not data.get("supplier_id") and selling.get("supplier_id"):
                data["supplier_id"] = int(selling["supplier_id"])
            if not data.get("supplier") and selling.get("supplier_name"):
                data["supplier"] = str(selling["supplier_name"])

        if not data.get("supplier_id") and data.get("supplierId"):
            data["supplier_id"] = int(data["supplierId"])

        # Subject & vendor_code
        if not data.get("subject") and data.get("subj_name"):
            data["subject"] = str(data["subj_name"])
        if not data.get("subject_id"):
            inner_data = data.get("data")
            if isinstance(inner_data, dict) and inner_data.get("subject_id"):
                data["subject_id"] = int(inner_data["subject_id"])
            elif data.get("subjectId"):
                data["subject_id"] = int(data["subjectId"])

        # Media photo count
        media = data.get("media")
        if isinstance(media, dict) and media.get("photo_count") is not None and not data.get("pics"):
            data["pics"] = int(media["photo_count"])

        # Extract prices: prefer modern `sizes[].price`, then `salePriceU` / `priceU`
        price_val = data.get("price")
        basic_val = data.get("basic_price")
        sizes_raw = data.get("sizes")

        extracted_sizes: List[str] = []
        if isinstance(sizes_raw, list) and sizes_raw:
            first_price = None
            for sz in sizes_raw:
                if isinstance(sz, dict):
                    label = str(sz.get("name") or sz.get("origName") or "").strip()
                    if label:
                        extracted_sizes.append(label)
                    if first_price is None and isinstance(sz.get("price"), dict):
                        first_price = sz["price"]
                elif isinstance(sz, str):
                    extracted_sizes.append(sz)
            data["sizes"] = extracted_sizes
            if isinstance(first_price, dict):
                if price_val is None:
                    raw_prod = first_price.get("product") or first_price.get("total")
                    price_val = _extract_kopecks(raw_prod)
                if basic_val is None:
                    basic_val = _extract_kopecks(first_price.get("basic"))

        if price_val is None and data.get("salePriceU") is not None:
            price_val = _extract_kopecks(data.get("salePriceU"))
        if basic_val is None and data.get("priceU") is not None:
            basic_val = _extract_kopecks(data.get("priceU"))

        if price_val is not None:
            data["price"] = float(price_val)
        if basic_val is not None:
            data["basic_price"] = float(basic_val)

        # Compute discount % if missing
        cur_price = float(data.get("price") or 0)
        orig_price = float(data.get("basic_price") or 0)
        if not data.get("discount") and not data.get("sale") and orig_price > cur_price > 0:
            data["discount"] = round((1.0 - (cur_price / orig_price)) * 100)

        # Rating normalization
        r_rating = data.get("reviewRating") or data.get("review_rating") or 0
        rating = data.get("rating") or r_rating or 0
        data["review_rating"] = float(r_rating)
        data["rating"] = float(rating)

        # Specs from card.json `options`
        if not data.get("specs") and isinstance(data.get("options"), list):
            specs: Dict[str, str] = {}
            for opt in data["options"]:
                if isinstance(opt, dict) and opt.get("name") and opt.get("value") is not None:
                    specs[str(opt["name"])] = str(opt["value"])
            data["specs"] = specs

        # Color IDs
        if not data.get("color_ids") and isinstance(data.get("colors"), list):
            c_ids: List[int] = []
            for c in data["colors"]:
                if isinstance(c, int):
                    c_ids.append(c)
                elif isinstance(c, dict) and c.get("id"):
                    c_ids.append(int(c["id"]))
            data["color_ids"] = c_ids

        # Product page URL
        if not data.get("url") and nm_id:
            data["url"] = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"

        return data

    @property
    def salePriceU(self) -> float:
        """Backward-compatible property returning ruble price (mirrors Duff89's Item.salePriceU)."""
        return self.price

    @property
    def supplierId(self) -> int:
        """Backward-compatible alias for `supplier_id`."""
        return self.supplier_id

    @property
    def sale(self) -> int:
        """Backward-compatible alias for `discount`."""
        return self.discount

    @property
    def price_drop(self) -> Optional[float]:
        """Amount the price decreased compared to recorded `old_price`, or None."""
        if self.old_price is not None and self.old_price > self.price > 0:
            return round(self.old_price - self.price, 2)
        return None

    @property
    def image_links_str(self) -> str:
        """Semicolon-separated image URLs string (compatible with Duff89 CSV column)."""
        return ";".join(self.image_links)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict including derived properties."""
        d = self.model_dump()
        d["price_drop"] = self.price_drop
        return d

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize product to UTF-8 JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class WBSearchPage(BaseModel):
    """Collection of products parsed from a single search or seller catalog page."""

    model_config = ConfigDict(extra="ignore")

    products: List[WBProduct] = Field(default_factory=list)
    total: int = 0
    page: int = 1


class PriceRecord(BaseModel):
    """Historical price snapshot stored in SQLite tracker."""

    nm_id: int
    name: str
    price: float
    basic_price: float = 0.0
    old_price: Optional[float] = None
    discount: int = 0
    supplier_id: int = 0
    recorded_at: str


# Backward-compatible aliases matching Duff89's `models.py`
Item = WBProduct
Items = WBSearchPage
Feedback = FeedbackInfo
