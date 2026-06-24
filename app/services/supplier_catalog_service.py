from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency path
    from sqlalchemy import or_  # type: ignore
    from sqlalchemy.orm import Session  # type: ignore
    from app.models.supplier_product import SupplierProduct  # type: ignore
except Exception:  # pragma: no cover - fallback for read-only governance/runtime use
    or_ = None  # type: ignore
    Session = Any  # type: ignore
    SupplierProduct = Any  # type: ignore


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    return " ".join(_safe_str(value).lower().split())


def _tokenize(value: Any) -> List[str]:
    text = _normalize_text(value)
    if not text:
        return []
    return [token for token in text.replace(",", " ").replace("/", " ").split() if token]


def _combine_opportunity_text(opportunity: Any) -> str:
    if isinstance(opportunity, dict):
        parts = [
            opportunity.get("title"),
            opportunity.get("description"),
            opportunity.get("category"),
            opportunity.get("entity_name"),
            opportunity.get("procurement_type"),
            opportunity.get("keywords"),
        ]
    else:
        parts = [
            getattr(opportunity, "title", ""),
            getattr(opportunity, "description", ""),
            getattr(opportunity, "category", ""),
            getattr(opportunity, "entity_name", ""),
            getattr(opportunity, "procurement_type", ""),
            getattr(opportunity, "keywords", ""),
        ]

    return _normalize_text(" ".join(_safe_str(part) for part in parts if part))


def _product_search_blob(product: SupplierProduct) -> str:
    return _normalize_text(
        " ".join(
            [
                _safe_str(product.product_name),
                _safe_str(product.product_code),
                _safe_str(product.category),
                _safe_str(product.brand),
                _safe_str(product.description),
                _safe_str(product.specification),
                _safe_str(product.keywords),
                _safe_str(product.supplier_name),
                _safe_str(product.supplier_city),
                _safe_str(product.supplier_province),
            ]
        )
    )


def _score_match(opportunity_text: str, product: SupplierProduct) -> float:
    if not opportunity_text:
        return 0.0

    product_blob = _product_search_blob(product)
    if not product_blob:
        return 0.0

    opp_tokens = set(_tokenize(opportunity_text))
    product_tokens = set(_tokenize(product_blob))

    if not opp_tokens or not product_tokens:
        return 0.0

    overlap = opp_tokens.intersection(product_tokens)
    overlap_score = len(overlap) / max(len(opp_tokens), 1)

    exact_phrase_bonus = 0.0
    product_name = _normalize_text(product.product_name)
    category = _normalize_text(product.category)

    if product_name and product_name in opportunity_text:
        exact_phrase_bonus += 0.35

    if category and category in opportunity_text:
        exact_phrase_bonus += 0.15

    preferred_bonus = 0.10 if product.is_preferred else 0.0
    stock_bonus = 0.10 if product.in_stock else -0.15
    active_bonus = 0.05 if product.is_active else -1.0

    total = overlap_score + exact_phrase_bonus + preferred_bonus + stock_bonus + active_bonus
    return round(max(total, 0.0), 4)


def get_all_supplier_products(
    db: Session,
    active_only: bool = True,
    in_stock_only: bool = False,
    limit: int = 500,
) -> List[SupplierProduct]:
    if or_ is None or SupplierProduct is Any:
        return []
    query = db.query(SupplierProduct)

    if active_only:
        query = query.filter(SupplierProduct.is_active.is_(True))

    if in_stock_only:
        query = query.filter(SupplierProduct.in_stock.is_(True))

    return query.order_by(
        SupplierProduct.is_preferred.desc(),
        SupplierProduct.supplier_name.asc(),
        SupplierProduct.product_name.asc(),
    ).limit(limit).all()


def search_supplier_products(
    db: Session,
    search_text: str,
    active_only: bool = True,
    in_stock_only: bool = False,
    limit: int = 100,
) -> List[SupplierProduct]:
    if or_ is None or SupplierProduct is Any:
        return []
    search_text = _safe_str(search_text)
    query = db.query(SupplierProduct)

    if active_only:
        query = query.filter(SupplierProduct.is_active.is_(True))

    if in_stock_only:
        query = query.filter(SupplierProduct.in_stock.is_(True))

    if search_text:
        like_pattern = f"%{search_text}%"
        query = query.filter(
            or_(
                SupplierProduct.product_name.ilike(like_pattern),
                SupplierProduct.product_code.ilike(like_pattern),
                SupplierProduct.category.ilike(like_pattern),
                SupplierProduct.brand.ilike(like_pattern),
                SupplierProduct.description.ilike(like_pattern),
                SupplierProduct.specification.ilike(like_pattern),
                SupplierProduct.keywords.ilike(like_pattern),
                SupplierProduct.supplier_name.ilike(like_pattern),
            )
        )

    return query.order_by(
        SupplierProduct.is_preferred.desc(),
        SupplierProduct.in_stock.desc(),
        SupplierProduct.product_name.asc(),
    ).limit(limit).all()


def match_opportunity_to_supplier_products(
    db: Session,
    opportunity: Any,
    min_score: float = 0.20,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    if or_ is None or SupplierProduct is Any:
        return []
    opportunity_text = _combine_opportunity_text(opportunity)
    candidates = get_all_supplier_products(
        db=db,
        active_only=True,
        in_stock_only=False,
        limit=1000,
    )

    scored_matches: List[Dict[str, Any]] = []

    for product in candidates:
        match_score = _score_match(opportunity_text, product)
        if match_score < min_score:
            continue

        scored_matches.append(
            {
                "match_score": match_score,
                "supplier_product_id": product.id,
                "supplier_name": product.supplier_name,
                "product_name": product.product_name,
                "product_code": product.product_code,
                "category": product.category,
                "brand": product.brand,
                "unit": product.unit,
                "description": product.description,
                "specification": product.specification,
                "currency": product.currency,
                "cost_price": float(product.cost_price) if product.cost_price is not None else 0.0,
                "sell_price": float(product.sell_price) if product.sell_price is not None else 0.0,
                "min_order_qty": product.min_order_qty,
                "lead_time_days": product.lead_time_days,
                "supplier_email": product.supplier_email,
                "supplier_phone": product.supplier_phone,
                "supplier_city": product.supplier_city,
                "supplier_province": product.supplier_province,
                "is_preferred": product.is_preferred,
                "in_stock": product.in_stock,
            }
        )

    scored_matches.sort(
        key=lambda item: (
            item["match_score"],
            item["is_preferred"],
            item["in_stock"],
            -item["sell_price"] if item["sell_price"] else 0.0,
        ),
        reverse=True,
    )

    return scored_matches[:limit]


def build_pricing_summary_from_matches(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not matches:
        return {
            "matched": False,
            "match_count": 0,
            "recommended_supplier": None,
            "recommended_product": None,
            "estimated_cost_price": 0.0,
            "estimated_sell_price": 0.0,
            "currency": "ZAR",
            "notes": "No supplier products matched this opportunity.",
        }

    top = matches[0]

    return {
        "matched": True,
        "match_count": len(matches),
        "recommended_supplier": top.get("supplier_name"),
        "recommended_product": top.get("product_name"),
        "estimated_cost_price": top.get("cost_price", 0.0),
        "estimated_sell_price": top.get("sell_price", 0.0),
        "currency": top.get("currency", "ZAR"),
        "notes": (
            f"Top supplier match is {top.get('supplier_name')} for "
            f"{top.get('product_name')} with score {top.get('match_score')}."
        ),
    }


def estimate_margin(cost_price: Any, sell_price: Any) -> Dict[str, float]:
    cost = Decimal(str(cost_price or 0))
    sell = Decimal(str(sell_price or 0))

    if sell <= 0:
        return {
            "markup_amount": 0.0,
            "markup_percent": 0.0,
            "gross_margin_percent": 0.0,
        }

    markup_amount = sell - cost
    markup_percent = (markup_amount / cost * Decimal("100")) if cost > 0 else Decimal("0")
    gross_margin_percent = (markup_amount / sell * Decimal("100")) if sell > 0 else Decimal("0")

    return {
        "markup_amount": float(round(markup_amount, 2)),
        "markup_percent": float(round(markup_percent, 2)),
        "gross_margin_percent": float(round(gross_margin_percent, 2)),
    }


def build_supplier_quote_input(
    db: Session,
    opportunity: Any,
    min_score: float = 0.20,
    limit: int = 5,
) -> Dict[str, Any]:
    matches = match_opportunity_to_supplier_products(
        db=db,
        opportunity=opportunity,
        min_score=min_score,
        limit=limit,
    )

    pricing_summary = build_pricing_summary_from_matches(matches)

    margin_summary = estimate_margin(
        pricing_summary.get("estimated_cost_price", 0.0),
        pricing_summary.get("estimated_sell_price", 0.0),
    )

    return {
        "opportunity_title": (
            opportunity.get("title")
            if isinstance(opportunity, dict)
            else getattr(opportunity, "title", None)
        ),
        "pricing_summary": pricing_summary,
        "margin_summary": margin_summary,
        "supplier_matches": matches,
    }
