"""
LMCP Backend Intelligence Layer
Version: V49_BACKEND_INTELLIGENCE_LAYER

Purpose:
- Clean noisy RFQ/opportunity records before they reach the frontend.
- Reject tenders that LMCP should not quote.
- Score supply-and-delivery opportunities.
- Estimate margin/profit readiness.
- Produce clean Mission Control radar cards.

This file is self-contained and safe to add without replacing existing harvester,
pipeline, quote engine, or submission services.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
import re


SERVICE_VERSION = "V49_BACKEND_INTELLIGENCE_LAYER"


EXCLUDED_KEYWORDS = {
    "medical": [
        "medical", "medicine", "pharmaceutical", "pharmacy", "clinic", "hospital",
        "syringe", "bandage", "surgical", "gloves", "glucose", "consumable", "consumables",
        "laboratory", "pathology", "patient", "nurse", "doctor"
    ],
    "it_equipment": [
        "laptop", "computer", "desktop", "server", "printer", "scanner", "router",
        "switch", "network", "software", "licence", "license", "tablet", "monitor",
        "ups", "firewall", "ict", "toner cartridge"
    ],
    "fuel": [
        "petrol", "diesel", "fuel", "paraffin", "lubricant", "oil supply"
    ],
    "catering": [
        "catering", "cater", "food", "meals", "refreshments", "beverages", "lunch",
        "breakfast", "dinner", "snacks"
    ],
    "briefing": [
        "compulsory briefing", "mandatory briefing", "site briefing", "site meeting",
        "compulsory site", "mandatory site", "briefing session is compulsory"
    ],
    "construction_heavy": [
        "construction", "building works", "civil works", "refurbishment", "renovation",
        "electrical works", "mechanical works", "plumbing works", "repairs and maintenance",
        "installation of machinery", "repair and installation"
    ],
    "consulting_services": [
        "consulting", "consultancy", "professional services", "training services",
        "security services", "cleaning services", "audit services", "legal services"
    ],
}

POSITIVE_SUPPLY_KEYWORDS = [
    "supply", "delivery", "supply and delivery", "rfq", "quotation", "provide",
    "stationery", "office furniture", "furniture", "uniform", "ppe", "tools",
    "cleaning materials", "consumables excluding medical", "corporate gifts",
    "promotional items", "toner", "cartridge", "paper", "chairs", "desks",
    "appliances", "materials", "equipment", "goods"
]

JUNK_KEYWORDS = [
    "harvester error", "untitled rfq", "buyer not shown", "procurement plan",
    "request for information", "rfi", "meeting invitation", "published through open tender platforms",
    "etenders@treasury.gov.za"
]


@dataclass
class IntelligenceDecision:
    accepted: bool
    quote_ready: bool
    score: int
    risk_level: str
    rejection_reason: Optional[str]
    category: str
    estimated_profit: float
    estimated_margin_percent: float
    confidence: float
    flags: List[str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return str(value)
    return str(value)


def _lower_blob(item: Dict[str, Any]) -> str:
    keys = [
        "title", "description", "bid_description", "buyer_name", "department",
        "organisation", "organization", "province", "submission_method", "briefing",
        "briefing_details", "notes", "category", "source_name"
    ]
    return " ".join(_safe_text(item.get(k)) for k in keys).lower()


def _first_non_empty(*values: Any, default: str = "") -> str:
    for value in values:
        text = _safe_text(value).strip()
        if text:
            return text
    return default


def _contains_any(text: str, words: Iterable[str]) -> Optional[str]:
    for word in words:
        if word and word.lower() in text:
            return word
    return None


def _clean_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", _safe_text(text)).strip()
    if len(cleaned) > 170:
        cleaned = cleaned[:167].rstrip() + "..."
    return cleaned


def classify_category(blob: str) -> Tuple[str, Optional[str]]:
    for category, words in EXCLUDED_KEYWORDS.items():
        matched = _contains_any(blob, words)
        if matched:
            return category, matched

    positive = _contains_any(blob, POSITIVE_SUPPLY_KEYWORDS)
    if positive:
        return "supply_delivery", positive

    return "unknown", None


def estimate_profit(item: Dict[str, Any], score: int) -> Tuple[float, float]:
    pricing = item.get("pricing_summary") or item.get("pricing") or {}
    raw_profit = (
        item.get("estimated_profit")
        or item.get("total_profit")
        or pricing.get("total_profit")
        or pricing.get("estimated_profit")
        or 0
    )

    try:
        profit = float(raw_profit)
    except Exception:
        profit = 0.0

    if profit <= 0:
        if score >= 85:
            profit = 45000.0
        elif score >= 70:
            profit = 30000.0
        elif score >= 55:
            profit = 18000.0
        else:
            profit = 0.0

    margin = (
        item.get("estimated_margin_percent")
        or item.get("margin_percent")
        or pricing.get("achieved_margin_percent")
        or pricing.get("minimum_margin_percent")
        or 25.0
    )

    try:
        margin_float = float(margin)
    except Exception:
        margin_float = 25.0

    return round(profit, 2), round(margin_float, 2)


def detect_junk(item: Dict[str, Any], blob: str) -> Optional[str]:
    title = _first_non_empty(item.get("title"), item.get("description"), item.get("bid_description"))
    if not title.strip():
        return "missing_title"

    matched = _contains_any(blob, JUNK_KEYWORDS)
    if matched:
        return f"junk_keyword:{matched}"

    if title.strip().lower() in {"untitled", "untitled rfq", "harvester error"}:
        return "junk_title"

    return None


def score_opportunity(item: Dict[str, Any]) -> IntelligenceDecision:
    blob = _lower_blob(item)
    flags: List[str] = []

    junk_reason = detect_junk(item, blob)
    if junk_reason:
        return IntelligenceDecision(
            accepted=False,
            quote_ready=False,
            score=0,
            risk_level="rejected",
            rejection_reason=junk_reason,
            category="junk",
            estimated_profit=0.0,
            estimated_margin_percent=0.0,
            confidence=0.0,
            flags=["junk_record"],
        )

    category, matched_keyword = classify_category(blob)

    if category != "supply_delivery" and category != "unknown":
        return IntelligenceDecision(
            accepted=False,
            quote_ready=False,
            score=0,
            risk_level="rejected",
            rejection_reason=f"excluded_category:{category}:{matched_keyword}",
            category=category,
            estimated_profit=0.0,
            estimated_margin_percent=0.0,
            confidence=0.0,
            flags=[f"excluded:{category}"],
        )

    score = 45

    if "supply and delivery" in blob:
        score += 28
        flags.append("supply_and_delivery")
    elif "supply" in blob:
        score += 18
        flags.append("supply")
    if "delivery" in blob:
        score += 14
        flags.append("delivery")
    if "rfq" in blob or "quotation" in blob:
        score += 8
        flags.append("rfq")
    if "email" in blob:
        score += 4
        flags.append("email_submission")
    if "briefing" not in blob:
        score += 5
        flags.append("no_briefing_detected")

    soft_negative_terms = [
        "service", "repair", "installation", "maintenance", "consult", "meeting",
        "information session", "expression of interest"
    ]
    for term in soft_negative_terms:
        if term in blob:
            score -= 10
            flags.append(f"soft_negative:{term}")

    if item.get("briefing_required") is True:
        score -= 55
        flags.append("briefing_required_true")

    score = max(0, min(100, score))
    estimated_profit, estimated_margin = estimate_profit(item, score)

    quote_ready = (
        score >= 68
        and estimated_profit >= 30000
        and estimated_margin >= 25
        and item.get("briefing_required") is not True
    )

    if score >= 80:
        risk = "low"
    elif score >= 60:
        risk = "medium"
    else:
        risk = "high"

    accepted = score >= 50
    confidence = round(score / 100.0, 2)

    return IntelligenceDecision(
        accepted=accepted,
        quote_ready=quote_ready,
        score=score,
        risk_level=risk,
        rejection_reason=None if accepted else "score_below_threshold",
        category="supply_delivery" if score >= 60 else category,
        estimated_profit=estimated_profit,
        estimated_margin_percent=estimated_margin,
        confidence=confidence,
        flags=flags,
    )


def normalize_opportunity(item: Dict[str, Any], decision: IntelligenceDecision) -> Dict[str, Any]:
    title = _clean_title(
        _first_non_empty(
            item.get("title"),
            item.get("description"),
            item.get("bid_description"),
            default="Untitled RFQ"
        )
    )

    buyer = _clean_title(
        _first_non_empty(
            item.get("buyer_name"),
            item.get("department"),
            item.get("organisation"),
            item.get("organization"),
            item.get("source_name"),
            default="Buyer not shown"
        )
    )

    rfq = _clean_title(
        _first_non_empty(
            item.get("buyer_rfq_number"),
            item.get("rfq_number"),
            item.get("reference_number"),
            item.get("tender_number"),
            default="RFQ-NO-ID"
        )
    )

    province = _clean_title(_first_non_empty(item.get("province"), item.get("location"), item.get("region"), default="SA"))

    normalized = dict(item)
    normalized.update(
        {
            "title": title,
            "buyer_name": buyer,
            "buyer_rfq_number": rfq,
            "province": province,
            "score": decision.score,
            "confidence": decision.confidence,
            "risk_level": decision.risk_level,
            "category": decision.category,
            "quote_ready": decision.quote_ready,
            "eligible": decision.accepted,
            "estimated_profit": decision.estimated_profit,
            "estimated_margin_percent": decision.estimated_margin_percent,
            "intelligence_flags": decision.flags,
            "intelligence_version": SERVICE_VERSION,
            "intelligence_updated_at": utc_now_iso(),
        }
    )
    return normalized


def intelligent_filter_opportunities(
    opportunities: Iterable[Dict[str, Any]],
    *,
    limit: int = 50,
    include_rejected: bool = False,
) -> Dict[str, Any]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for raw in opportunities or []:
        if not isinstance(raw, dict):
            continue

        decision = score_opportunity(raw)
        record = normalize_opportunity(raw, decision)
        record["intelligence_decision"] = asdict(decision)

        if decision.accepted:
            accepted.append(record)
        else:
            rejected.append(record)

    accepted.sort(
        key=lambda x: (
            int(x.get("quote_ready") is True),
            float(x.get("score") or 0),
            float(x.get("estimated_profit") or 0),
        ),
        reverse=True,
    )

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "updated_at": utc_now_iso(),
        "total_input": len(list(opportunities or [])) if not isinstance(opportunities, list) else len(opportunities),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "quote_ready_count": sum(1 for item in accepted if item.get("quote_ready") is True),
        "estimated_profit_total": round(sum(float(item.get("estimated_profit") or 0) for item in accepted), 2),
        "opportunities": accepted[: max(1, int(limit or 50))],
    }

    if include_rejected:
        result["rejected"] = rejected[:100]

    return result


def analyze_single_opportunity(item: Dict[str, Any]) -> Dict[str, Any]:
    decision = score_opportunity(item or {})
    normalized = normalize_opportunity(item or {}, decision)
    normalized["intelligence_decision"] = asdict(decision)

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "updated_at": utc_now_iso(),
        "opportunity": normalized,
    }


def build_demo_records() -> List[Dict[str, Any]]:
    return [
        {
            "title": "Supply and delivery of stationery for municipal offices",
            "buyer_name": "Example Municipality",
            "buyer_rfq_number": "RFQ-DEMO-001",
            "province": "Free State",
            "submission_method": "email",
        },
        {
            "title": "Compulsory briefing for repair and installation of machinery",
            "buyer_name": "Example SOE",
            "buyer_rfq_number": "RFQ-DEMO-002",
            "province": "Gauteng",
        },
        {
            "title": "Supply and delivery of office furniture",
            "buyer_name": "Example Department",
            "buyer_rfq_number": "RFQ-DEMO-003",
            "province": "KwaZulu-Natal",
            "estimated_profit": 52000,
        },
    ]
