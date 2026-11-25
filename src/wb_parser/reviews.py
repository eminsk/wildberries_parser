"""
Wildberries Smart Review Analyzer & Extractor (`wb_smart_review` integration).

Features:
- Resolves `nm_id` -> `root_id` via CDN `card.json` (`imt_id`) without relying on blocked `card.wb.ru`.
- Automatically targets the exact feedback shard (`feedbacks1` vs `feedbacks2`) using `root_id % 100 >= 50`.
- Parses structured `pros` (Достоинства), `cons` (Недостатки), `text`, `matchingSize`, and ratings.
- Provides a Zero-API Offline NLP Summarizer (pros/cons frequency clustering + size fit analysis),
  Free AI via `g4f` / local `Ollama` (`wb-sdk-pro[ai]`), AND Paid/Hybrid OpenAI-compatible
  LLMs (`OpenAI`, `DeepSeek`, `OpenRouter`, `ProxyAPI`, `Groq`, `Gemini`).
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from wb_parser._model import BaseModel, ConfigDict, Field
from wb_parser.ai import _detect_any_paid_env, generate_completion, parse_json_payload
from wb_parser.shards import calculate_feedback_shard, extract_nm_id

if TYPE_CHECKING:
    from wb_parser.client import WBClient

logger = logging.getLogger("wb_parser.reviews")


class ReviewItem(BaseModel):
    """Single buyer review parsed from `feedbacks1/2.wb.ru`."""

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    nm_id: int = Field(default=0, alias="nmId")
    rating: int = Field(default=5, alias="productValuation")
    text: str = ""
    pros: str = ""
    cons: str = ""
    matching_size: str = Field(default="", alias="matchingSize")
    color: str = ""
    size: str = ""
    created_date: str = Field(default="", alias="createdDate")
    has_answer: bool = False
    bables: List[str] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    """Aggregated review insights (offline structured extraction + optional AI summary)."""

    nm_id: int
    root_id: int
    product_name: str = ""
    shard: int = 1
    total_available: int = 0
    total_analyzed: int = 0
    filtered_by_nm: bool = True
    avg_rating: float = 0.0
    rating_distribution: Dict[int, int] = Field(default_factory=dict)
    size_fit: Dict[str, int] = Field(default_factory=dict)
    top_pros: List[str] = Field(default_factory=list)
    top_cons: List[str] = Field(default_factory=list)
    bables_tags: List[str] = Field(default_factory=list)
    reviews: List[ReviewItem] = Field(default_factory=list)
    ai_summary: Optional[Dict[str, List[str]]] = None
    summary_mode: str = "offline"
    ai_provider: str = ""
    ai_model: str = ""


def _extract_phrases(texts: List[str], top_k: int = 5) -> List[str]:
    """Extract normalized, de-duplicated top review highlights cleanly."""
    counter: Counter[str] = Counter()
    originals: Dict[str, str] = {}

    for raw in texts:
        cleaned = str(raw).strip()
        if not cleaned or len(cleaned) < 3:
            continue
        # Split compound points cleanly on newlines/semicolons/periods
        for chunk in re.split(r"[\n;]+", cleaned):
            part = chunk.strip(" .,-!—")
            if len(part) < 3 or len(part) > 120:
                continue
            norm = re.sub(r"\s+", " ", part.lower())
            counter[norm] += 1
            if norm not in originals:
                originals[norm] = part[0].upper() + part[1:]

    result: List[str] = []
    for norm, count in counter.most_common(top_k):
        label = originals[norm]
        if count > 1:
            result.append(f"{label} ({count}x)")
        else:
            result.append(label)
    return result


class SmartReviewAnalyzer:
    """Fetches sharded Wildberries reviews and produces offline & AI pros/cons summaries."""

    def __init__(self, client: "WBClient") -> None:
        self.client = client

    def fetch_reviews(
        self,
        url_or_nm_id: Union[str, int],
        *,
        only_this_color: bool = True,
        limit: int = 100,
    ) -> ReviewSummary:
        """
        Fetch product card (`card.json`) -> `root_id`, pull sharded reviews from `feedbacks1/2`,
        and produce an instant offline summary of pros, cons, rating histogram, and size fit.
        """
        nm_id = extract_nm_id(url_or_nm_id)
        card = self.client.get_card_cdn(nm_id)
        root_id = card.root or nm_id
        expected_shard = calculate_feedback_shard(root_id)

        fb_info = self.client.get_feedbacks(root_id)
        if fb_info is None:
            return ReviewSummary(
                nm_id=nm_id,
                root_id=root_id,
                product_name=card.name,
                shard=expected_shard,
                filtered_by_nm=only_this_color,
            )

        parsed_items: List[ReviewItem] = []
        raw_fbs = fb_info.feedbacks or []
        for raw in raw_fbs:
            if not isinstance(raw, dict):
                continue
            item_nm = int(raw.get("nmId") or 0)
            if only_this_color and item_nm and item_nm != nm_id:
                continue
            has_text = bool(
                str(raw.get("text") or "").strip()
                or str(raw.get("pros") or "").strip()
                or str(raw.get("cons") or "").strip()
            )
            if not has_text:
                continue
            parsed_items.append(
                ReviewItem.model_validate(
                    {**raw, "has_answer": bool(raw.get("answer"))}
                )
            )
            if len(parsed_items) >= limit:
                break

        # If filtering by exact color yields 0 text reviews, fall back seamlessly to whole card (`root_id`)
        filtered_flag = only_this_color
        if only_this_color and not parsed_items and raw_fbs:
            filtered_flag = False
            for raw in raw_fbs:
                if not isinstance(raw, dict):
                    continue
                if any(str(raw.get(k) or "").strip() for k in ("text", "pros", "cons")):
                    parsed_items.append(
                        ReviewItem.model_validate(
                            {**raw, "has_answer": bool(raw.get("answer"))}
                        )
                    )
                    if len(parsed_items) >= limit:
                        break

        return self._build_offline_summary(
            nm_id=nm_id,
            root_id=root_id,
            product_name=card.name,
            shard=fb_info.shard,
            total_available=fb_info.total_feedback_count or fb_info.feedback_count,
            reviews=parsed_items,
            filtered_by_nm=filtered_flag,
        )

    @staticmethod
    def _build_offline_summary(
        *,
        nm_id: int,
        root_id: int,
        product_name: str,
        shard: int,
        total_available: int,
        reviews: List[ReviewItem],
        filtered_by_nm: bool,
    ) -> ReviewSummary:
        """Build deterministic offline insights from review pros, cons, ratings, and size tags."""
        rating_dist: Dict[int, int] = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        size_dist: Counter[str] = Counter()
        bables_counter: Counter[str] = Counter()
        pros_pool: List[str] = []
        cons_pool: List[str] = []

        rating_sum = 0
        for r in reviews:
            val = min(5, max(1, int(r.rating or 5)))
            rating_dist[val] = rating_dist.get(val, 0) + 1
            rating_sum += val

            if r.matching_size:
                size_dist[r.matching_size] += 1
            for tag in r.bables:
                bables_counter[tag] += 1

            if r.pros:
                pros_pool.append(r.pros)
            elif val == 5 and r.text:
                pros_pool.append(r.text[:100])

            if r.cons:
                cons_pool.append(r.cons)
            elif val <= 2 and r.text:
                cons_pool.append(r.text[:100])

        avg = round(rating_sum / len(reviews), 2) if reviews else 0.0
        top_pros = _extract_phrases(pros_pool, top_k=5)
        top_cons = _extract_phrases(cons_pool, top_k=5)

        return ReviewSummary(
            nm_id=nm_id,
            root_id=root_id,
            product_name=product_name,
            shard=shard,
            total_available=total_available,
            total_analyzed=len(reviews),
            filtered_by_nm=filtered_by_nm,
            avg_rating=avg,
            rating_distribution=rating_dist,
            size_fit=dict(size_dist),
            top_pros=top_pros,
            top_cons=top_cons,
            bables_tags=[k for k, _ in bables_counter.most_common(6)],
            reviews=reviews,
            ai_summary={"plus": top_pros, "minus": top_cons},
            summary_mode="offline",
        )

    def summarize_with_llm(
        self,
        summary: ReviewSummary,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
        timeout: float = 25.0,
    ) -> ReviewSummary:
        """
        Optionally enrich a `ReviewSummary` using either Free (`g4f` / local `Ollama`),
        Hybrid (`OpenRouter` `:free` / `Groq` / `Gemini`), or Paid (`OpenAI` / `DeepSeek` /
        `ProxyAPI` / custom OpenAI-compatible) LLM backends.
        Leaves offline summary intact on failure or when unconfigured.
        """
        if not summary.reviews:
            return summary

        eff_mode = (mode or os.environ.get("WB_AI_MODE") or "auto").strip().lower()
        eff_provider = (provider or os.environ.get("WB_AI_PROVIDER") or "").strip() or None
        eff_model = (model or os.environ.get("WB_AI_MODEL") or "").strip() or None
        eff_url = (base_url or os.environ.get("WB_AI_BASE_URL") or "").strip() or None
        eff_key = (api_key or "").strip() or None

        if eff_mode == "offline":
            return summary
        if eff_mode == "auto" and not any((eff_key, eff_provider, eff_url, _detect_any_paid_env())):
            return summary

        snippets = []
        for r in summary.reviews[:60]:
            parts = []
            if r.pros:
                parts.append(f"+ {r.pros}")
            if r.cons:
                parts.append(f"- {r.cons}")
            if r.text:
                parts.append(r.text[:200])
            if parts:
                snippets.append(f"[{r.rating}★] " + " | ".join(parts))

        prompt = (
            "На основе отзывов покупателей Wildberries кратко выдели главные плюсы и минусы товара "
            "(до 5 пунктов в каждом списке, на русском). Верни ТОЛЬКО валидный JSON формата:\n"
            '{"plus": ["..."], "minus": ["..."]}\n\n'
            f"Товар: {summary.product_name}\n"
            "Отзывы:\n" + "\n".join(snippets)
        )

        res = generate_completion(
            prompt,
            mode=eff_mode,
            provider=eff_provider,
            model=eff_model,
            api_key=eff_key,
            base_url=eff_url,
            temperature=0.2,
            timeout=timeout,
        )
        if not res.ok:
            logger.warning(f"LLM review summarization skipped ({res.error}); using offline summary.")
            return summary

        try:
            parsed = parse_json_payload(res.content)
            plus = [str(x).strip() for x in (parsed.get("plus") or []) if str(x).strip()]
            minus = [str(x).strip() for x in (parsed.get("minus") or []) if str(x).strip()]
            summary.ai_summary = {"plus": plus, "minus": minus}
            if plus:
                summary.top_pros = plus
            if minus:
                summary.top_cons = minus
            summary.ai_provider = res.provider
            summary.ai_model = res.model
            summary.summary_mode = f"{res.tier}:{res.provider}/{res.model}"
        except Exception as exc:
            logger.warning(f"LLM review JSON parse skipped ({exc}); using offline summary.")
        return summary
