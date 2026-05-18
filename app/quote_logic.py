from __future__ import annotations

from datetime import datetime
from typing import Dict, Tuple, Optional, List

from sqlalchemy.orm import Session

from app.models import Opportunity, MarkupRule


LMCP_PREFERRED_PROVINCES = {
    "free state": 10,
    "gauteng": 8,
    "northern cape": 7,
    "north west": 6,
    "eastern cape": 5,
    "western cape": 5,
    "kwazulu-natal": 4,
    "limpopo": 4,
    "mpumalanga": 4,
    "mpumalanga province": 4,
}

LMCP_PREFERRED_KEYWORDS = {
    "supply": 8,
    "delivery": 8,
    "equipment": 6,
    "materials": 6,
    "stationery": 5,
    "furniture": 5,
    "consumables": 5,
    "ppe": 7,
    "uniform": 6,
    "cleaning": 6,
    "water": 5,
    "pipes": 6,
    "electrical": 6,
    "solar": 7,
    "inverter": 7,
    "laptop": 5,
    "printer": 5,
    "road signs": 7,
    "building materials": 8,
}

LMCP_PREFERRED_BUYERS = {
    "municipality": 8,
    "local municipality": 8,
    "department": 7,
    "government": 7,
    "sanral": 10,
    "dpwi": 9,
    "human settlements": 9,
    "sassa": 8,
    "museum": 6,
    "correctional": 7,
    "water board": 8,
    "school": 5,
    "hospital": 7,
}

LMCP_SUPPLY_POSITIVE_TERMS = [
    "supply",
    "delivery",
    "supply and delivery",
    "appointment of service provider for supply",
    "procurement of",
    "purchase of",
    "supply, delivery and offloading",
    "supply and install",
    "supply and installation",
    "supply, deliver and install",
]

LMCP_SERVICE_HEAVY_TERMS = [
    "consulting",
    "consultancy",
    "professional services",
    "advisory",
    "feasibility study",
    "design services",
    "legal services",
    "audit services",
    "cleaning services",
    "security services",
    "maintenance services",
]

DEFAULT_VAT_PCT = 15.0


def _text(*parts: Optional[str]) -> str:
    return " ".join([p.strip().lower() for p in parts if p and p.strip()])


def _clean_phrase(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def opportunity_full_text(opportunity: Opportunity) -> str:
    return _text(
        opportunity.title,
        opportunity.description,
        opportunity.buyer_name,
        opportunity.category,
        opportunity.province,
    )


def extract_matching_keywords(opportunity: Opportunity) -> List[str]:
    full_text = opportunity_full_text(opportunity)
    matches: List[str] = []

    for keyword in LMCP_PREFERRED_KEYWORDS.keys():
        if keyword in full_text:
            matches.append(keyword)

    return sorted(set(matches))


def is_supply_delivery_like(opportunity: Opportunity) -> bool:
    if getattr(opportunity, "is_supply_delivery", False):
        return True

    full_text = opportunity_full_text(opportunity)

    positive_hits = sum(1 for term in LMCP_SUPPLY_POSITIVE_TERMS if term in full_text)
    service_hits = sum(1 for term in LMCP_SERVICE_HEAVY_TERMS if term in full_text)

    return positive_hits > service_hits and positive_hits > 0


def score_opportunity(opportunity: Opportunity) -> Tuple[float, Dict]:
    title = (opportunity.title or "").lower()
    desc = (opportunity.description or "").lower()
    buyer = (opportunity.buyer_name or "").lower()
    province = (opportunity.province or "").lower()
    category = (opportunity.category or "").lower()

    full_text = _text(title, desc, buyer, category)

    breakdown = {
        "supply_delivery_gate": 0,
        "keyword_score": 0,
        "buyer_score": 0,
        "province_score": 0,
        "value_score": 0,
        "deadline_score": 0,
        "total_before_cap": 0,
        "matched_keywords": [],
        "recommended_strategy": "",
    }

    total = 0.0

    if is_supply_delivery_like(opportunity):
        breakdown["supply_delivery_gate"] = 35
        total += 35
    else:
        breakdown["supply_delivery_gate"] = 0

    keyword_total = 0
    matched_keywords: List[str] = []
    for keyword, points in LMCP_PREFERRED_KEYWORDS.items():
        if keyword in full_text:
            keyword_total += points
            matched_keywords.append(keyword)

    keyword_total = min(keyword_total, 25)
    breakdown["keyword_score"] = keyword_total
    breakdown["matched_keywords"] = sorted(set(matched_keywords))
    total += keyword_total

    buyer_total = 0
    for keyword, points in LMCP_PREFERRED_BUYERS.items():
        if keyword in buyer:
            buyer_total = max(buyer_total, points)

    breakdown["buyer_score"] = buyer_total
    total += buyer_total

    province_points = LMCP_PREFERRED_PROVINCES.get(province, 3 if province else 0)
    breakdown["province_score"] = province_points
    total += province_points

    value_score = 0
    if opportunity.estimated_value is not None:
        value = opportunity.estimated_value
        if value <= 50000:
            value_score = 4
        elif value <= 250000:
            value_score = 7
        elif value <= 1000000:
            value_score = 10
        elif value <= 5000000:
            value_score = 8
        else:
            value_score = 6

    breakdown["value_score"] = value_score
    total += value_score

    deadline_score = 0
    if opportunity.closing_at:
        days_left = (opportunity.closing_at - datetime.utcnow()).days
        if days_left >= 14:
            deadline_score = 10
        elif days_left >= 7:
            deadline_score = 7
        elif days_left >= 3:
            deadline_score = 4
        elif days_left >= 0:
            deadline_score = 2

    breakdown["deadline_score"] = deadline_score
    total += deadline_score

    breakdown["total_before_cap"] = total
    total = max(0.0, min(100.0, round(total, 2)))
    breakdown["recommended_strategy"] = recommend_quote_strategy(total)

    return total, breakdown


def default_markup_for_value(estimated_value: Optional[float]) -> float:
    if estimated_value is None:
        return 22.0
    if estimated_value <= 50000:
        return 30.0
    if estimated_value <= 250000:
        return 24.0
    if estimated_value <= 1000000:
        return 18.0
    if estimated_value <= 5000000:
        return 15.0
    return 12.0


def score_adjustment(score: float) -> float:
    if score >= 85:
        return 4.0
    if score >= 70:
        return 2.0
    if score >= 55:
        return 0.0
    if score >= 40:
        return -2.0
    return -4.0


def rule_matches(opportunity: Opportunity, rule: MarkupRule, score: float) -> bool:
    if not rule.is_active:
        return False

    if rule.min_score is not None and score < rule.min_score:
        return False
    if rule.max_score is not None and score > rule.max_score:
        return False

    value = opportunity.estimated_value
    if rule.min_estimated_value is not None:
        if value is None or value < rule.min_estimated_value:
            return False
    if rule.max_estimated_value is not None:
        if value is None or value > rule.max_estimated_value:
            return False

    if rule.province:
        if _clean_phrase(opportunity.province) != _clean_phrase(rule.province):
            return False

    if rule.buyer_name_contains:
        if _clean_phrase(rule.buyer_name_contains) not in _clean_phrase(opportunity.buyer_name):
            return False

    if rule.category_contains:
        haystack = _text(opportunity.category, opportunity.title, opportunity.description)
        if _clean_phrase(rule.category_contains) not in haystack:
            return False

    return True


def resolve_markup(session: Session, opportunity: Opportunity, score: float) -> float:
    rules = (
        session.query(MarkupRule)
        .filter(MarkupRule.is_active == True)  # noqa: E712
        .order_by(MarkupRule.priority.asc(), MarkupRule.id.asc())
        .all()
    )

    for rule in rules:
        if rule_matches(opportunity, rule, score):
            return round(rule.markup_pct, 2)

    base_markup = default_markup_for_value(opportunity.estimated_value)
    adjusted = base_markup + score_adjustment(score)
    adjusted = max(8.0, min(35.0, adjusted))
    return round(adjusted, 2)


def compute_quote_values(base_cost: float, markup_pct: float, vat_pct: float = DEFAULT_VAT_PCT) -> Dict[str, float]:
    sell_price_ex_vat = round(base_cost * (1 + (markup_pct / 100.0)), 2)
    vat_amount = round(sell_price_ex_vat * (vat_pct / 100.0), 2)
    total_price_inc_vat = round(sell_price_ex_vat + vat_amount, 2)

    return {
        "base_cost": round(base_cost, 2),
        "markup_pct": round(markup_pct, 2),
        "vat_pct": round(vat_pct, 2),
        "sell_price_ex_vat": sell_price_ex_vat,
        "vat_amount": vat_amount,
        "total_price_inc_vat": total_price_inc_vat,
    }


def recommend_quote_strategy(score: float) -> str:
    if score >= 80:
        return "HIGH_PRIORITY"
    if score >= 60:
        return "STANDARD"
    if score >= 45:
        return "SELECTIVE"
    return "LOW_PRIORITY"


def recommended_validity_days(opportunity: Opportunity) -> int:
    if opportunity.closing_at:
        days_left = (opportunity.closing_at - datetime.utcnow()).days
        if days_left <= 7:
            return 7
        if days_left <= 21:
            return 14
    return 30


def recommended_delivery_days(opportunity: Opportunity) -> int:
    full_text = opportunity_full_text(opportunity)

    if "urgent" in full_text or "emergency" in full_text:
        return 3
    if "stock" in full_text or "readily available" in full_text:
        return 5
    if "delivery" in full_text:
        return 7
    return 14


def build_opportunity_summary(opportunity: Opportunity) -> Dict[str, object]:
    score, breakdown = score_opportunity(opportunity)

    return {
        "opportunity_id": getattr(opportunity, "id", None),
        "title": opportunity.title,
        "buyer_name": opportunity.buyer_name,
        "province": opportunity.province,
        "category": opportunity.category,
        "estimated_value": opportunity.estimated_value,
        "closing_at": opportunity.closing_at.isoformat() if opportunity.closing_at else None,
        "score": score,
        "breakdown": breakdown,
        "markup_pct_default": default_markup_for_value(opportunity.estimated_value),
        "recommended_strategy": recommend_quote_strategy(score),
        "recommended_validity_days": recommended_validity_days(opportunity),
        "recommended_delivery_days": recommended_delivery_days(opportunity),
        "matched_keywords": extract_matching_keywords(opportunity),
        "supply_delivery_like": is_supply_delivery_like(opportunity),
    }


def build_default_quote_notes(opportunity: Opportunity) -> str:
    delivery_days = recommended_delivery_days(opportunity)
    validity_days = recommended_validity_days(opportunity)

    lines = [
        "Quoted strictly subject to final specification, quantities, and client confirmation.",
        f"Estimated delivery period: {delivery_days} working days from receipt of official order, subject to stock availability.",
        f"This quotation remains valid for {validity_days} calendar days unless otherwise withdrawn or revised in writing.",
        "Pricing is based on currently available market information and may be adjusted where client scope changes.",
    ]

    return "\n".join(lines)


def build_default_quote_terms(opportunity: Opportunity) -> str:
    validity_days = recommended_validity_days(opportunity)

    lines = [
        f"This quotation is valid for {validity_days} calendar days from date of issue.",
        "Prices are quoted in South African Rand (ZAR).",
        "VAT is charged at the prevailing statutory rate where applicable.",
        "Delivery periods are subject to stock availability, supplier lead times, and final client confirmation.",
        "Any variation in quantity, specification, delivery point, or scope may result in a revised quotation.",
        "Official order or appointment must be issued before supply or delivery can commence.",
        "Payment terms are subject to agreed client terms or official bid conditions.",
    ]

    if is_supply_delivery_like(opportunity):
        lines.append("Supply and delivery will be executed in accordance with the tender or RFQ requirements where applicable.")

    return "\n".join(lines)


def build_quote_title(opportunity: Opportunity) -> str:
    title = (opportunity.title or "").strip()
    if title:
        return title

    category = (opportunity.category or "").strip()
    buyer = (opportunity.buyer_name or "").strip()

    if category and buyer:
        return f"{category} - {buyer}"
    if category:
        return category
    if buyer:
        return f"Quotation for {buyer}"

    return "Quotation"


def estimate_base_cost_from_opportunity(opportunity: Opportunity) -> float:
    value = opportunity.estimated_value
    if value is None:
        return 0.0

    if value <= 50000:
        return round(value * 0.72, 2)
    if value <= 250000:
        return round(value * 0.78, 2)
    if value <= 1000000:
        return round(value * 0.84, 2)
    if value <= 5000000:
        return round(value * 0.87, 2)
    return round(value * 0.90, 2)
