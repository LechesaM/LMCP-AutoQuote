from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Opportunity, SupplierItem


@dataclass
class MatchCandidate:
    supplier_item_id: int
    item_name: str
    description: Optional[str]
    unit: str
    default_cost: float
    default_quantity: float
    markup_pct: float
    match_score: float
    match_reason: str


WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def tokenize(value: Optional[str]) -> List[str]:
    return WORD_RE.findall(normalize_text(value))


def build_opportunity_text(opportunity: Opportunity) -> str:
    parts = [
        opportunity.title,
        opportunity.description,
        opportunity.category,
        opportunity.buyer_name,
        opportunity.province,
        opportunity.city,
    ]
    return " ".join([normalize_text(p) for p in parts if p])


def parse_keywords(keywords: Optional[str]) -> List[str]:
    if not keywords:
        return []
    parts = []
    for raw in re.split(r"[,\n;|]+", keywords):
        kw = normalize_text(raw)
        if kw:
            parts.append(kw)
    return parts


def infer_quantity(opportunity_text: str, item: SupplierItem) -> float:
    text = opportunity_text

    quantity_patterns = [
        (r"(\d+)\s*(x|each|units|unit|items)", 1.0),
        (r"(\d+)\s*(chairs|desks|vests|inverters|printers|laptops|signs)", 1.0),
        (r"(\d+)\s*(m|meter|meters|metres)", 1.0),
        (r"(\d+)\s*(boxes|packs)", 1.0),
    ]

    for pattern, multiplier in quantity_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return max(1.0, float(match.group(1)) * multiplier)
            except Exception:
                pass

    return float(item.default_quantity or 1.0)


def score_supplier_item_match(opportunity: Opportunity, item: SupplierItem) -> MatchCandidate:
    opportunity_text = build_opportunity_text(opportunity)
    title_text = normalize_text(opportunity.title)
    category_text = normalize_text(opportunity.category)
    item_name = normalize_text(item.item_name)
    item_desc = normalize_text(item.description)
    item_category = normalize_text(item.category)

    keywords = parse_keywords(item.keywords)
    score = 0.0
    reasons = []

    if item_name and item_name in opportunity_text:
        score += 60
        reasons.append(f"item name match: {item.item_name}")

    if item_category and item_category in category_text:
        score += 25
        reasons.append(f"category match: {item.category}")

    if item_category and item_category in opportunity_text:
        score += 15
        reasons.append(f"category found in text: {item.category}")

    item_tokens = set(tokenize(item.item_name) + tokenize(item.description) + tokenize(item.category))
    opp_tokens = set(tokenize(opportunity_text))
    shared = item_tokens.intersection(opp_tokens)
    if shared:
        token_bonus = min(20, len(shared) * 4)
        score += token_bonus
        reasons.append(f"shared tokens: {', '.join(sorted(shared)[:6])}")

    keyword_hits = []
    for kw in keywords:
        if kw and kw in opportunity_text:
            score += 18
            keyword_hits.append(kw)
    if keyword_hits:
        score += min(20, len(keyword_hits) * 2)
        reasons.append(f"keyword hits: {', '.join(keyword_hits[:8])}")

    if item_desc and item_desc in opportunity_text:
        score += 20
        reasons.append("description match")

    score = min(100.0, round(score, 2))

    quantity = infer_quantity(opportunity_text, item)

    markup_pct = 18.0
    if opportunity.recommended_markup_pct is not None:
        markup_pct = float(opportunity.recommended_markup_pct)

    return MatchCandidate(
        supplier_item_id=item.id,
        item_name=item.item_name,
        description=item.description,
        unit=item.unit,
        default_cost=float(item.default_cost or 0.0),
        default_quantity=quantity,
        markup_pct=markup_pct,
        match_score=score,
        match_reason=" | ".join(reasons) if reasons else "weak generic match",
    )


def find_best_supplier_matches(
    db: Session,
    opportunity: Opportunity,
    max_items: int = 10,
    min_match_score: float = 20.0,
) -> List[MatchCandidate]:
    items = (
        db.query(SupplierItem)
        .filter(SupplierItem.is_active == True)  # noqa: E712
        .order_by(SupplierItem.item_name.asc())
        .all()
    )

    candidates: List[MatchCandidate] = []
    for item in items:
        candidate = score_supplier_item_match(opportunity, item)
        if candidate.match_score >= min_match_score:
            candidates.append(candidate)

    candidates.sort(key=lambda x: (-x.match_score, x.item_name.lower()))
    return candidates[:max_items]
