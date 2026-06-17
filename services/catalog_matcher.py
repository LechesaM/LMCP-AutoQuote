import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.supplier_product import SupplierProduct


STOPWORDS = {
    "the", "and", "for", "with", "supply", "delivery", "of", "to", "a", "an",
    "or", "in", "on", "at", "by", "from", "including", "suitable", "required",
    "item", "items", "goods", "equipment", "material", "materials"
}


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s\-\.]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def tokenize(value: Optional[str]) -> List[str]:
    cleaned = normalize_text(value)
    parts = cleaned.split()
    return [p for p in parts if p not in STOPWORDS and len(p) > 1]


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def keyword_overlap_score(a_tokens: List[str], b_tokens: List[str]) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    a_set = set(a_tokens)
    b_set = set(b_tokens)
    overlap = len(a_set.intersection(b_set))
    base = max(len(a_set), len(b_set))
    if base == 0:
        return 0.0
    return overlap / base


def build_candidate_text(product: SupplierProduct) -> str:
    parts = [
        product.product_name or "",
        product.brand or "",
        product.model or "",
        product.category or "",
        product.subcategory or "",
        product.description or "",
        product.supplier_name or "",
        product.sku or "",
    ]
    return normalize_text(" ".join(parts))


def score_product_match(item_text: str, product: SupplierProduct) -> float:
    item_text_norm = normalize_text(item_text)
    product_text = build_candidate_text(product)

    seq_score = similarity(item_text_norm, product_text)

    item_tokens = tokenize(item_text_norm)
    product_tokens = tokenize(product_text)
    overlap = keyword_overlap_score(item_tokens, product_tokens)

    preferred_bonus = 0.05 if product.preferred else 0.0
    active_bonus = 0.05 if product.active else -0.25

    final_score = (seq_score * 0.55) + (overlap * 0.35) + preferred_bonus + active_bonus
    return round(max(0.0, min(final_score, 1.0)), 4)


def find_best_catalog_match(
    db: Session,
    item_description: str,
    category: Optional[str] = None,
    limit: int = 25,
) -> Tuple[Optional[SupplierProduct], List[Dict[str, Any]]]:
    query = db.query(SupplierProduct).filter(SupplierProduct.active == True)  # noqa: E712

    if category:
        category_norm = normalize_text(category)
        if category_norm:
            query = query.filter(SupplierProduct.category.ilike(f"%{category_norm}%"))

    candidates = query.order_by(SupplierProduct.preferred.desc(), SupplierProduct.updated_at.desc()).limit(limit).all()

    ranked: List[Dict[str, Any]] = []
    for product in candidates:
        match_score = score_product_match(item_description, product)
        ranked.append(
            {
                "product_id": product.id,
                "supplier_name": product.supplier_name,
                "product_name": product.product_name,
                "brand": product.brand,
                "model": product.model,
                "sku": product.sku,
                "unit": product.unit,
                "unit_cost": product.unit_cost,
                "stock_qty": product.stock_qty,
                "lead_time_days": product.lead_time_days,
                "preferred": product.preferred,
                "match_score": match_score,
                "product": product,
            }
        )

    ranked.sort(key=lambda x: x["match_score"], reverse=True)

    best = ranked[0]["product"] if ranked else None
    return best, ranked
