from __future__ import annotations

"""
LMCP V31 Smart RFQ Detection Service

Drop-in:
    app/services/smart_rfq_detection_service.py

Purpose:
    Remove portal noise and classify real RFQ opportunities before expensive quote/submission work.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

SERVICE_VERSION = "V31_SMART_RFQ_DETECTION_ENGINE"

MIN_TITLE_LENGTH = int(str(os.getenv("V31_MIN_TITLE_LENGTH", "15")).strip() or "15")
MIN_RFQ_SCORE = int(str(os.getenv("V31_MIN_RFQ_SCORE", "55")).strip() or "55")
AUTO_PROMOTE_SCORE = int(str(os.getenv("V31_AUTO_PROMOTE_SCORE", "72")).strip() or "72")

EXCLUDED_KEYWORDS = {
    "medical",
    "biomedical",
    "pharmaceutical",
    "medicine",
    "surgical",
    "clinic",
    "hospital consumables",
    "laptop",
    "computer",
    "server",
    "software",
    "printer",
    "ict",
    "it equipment",
    "fuel",
    "diesel",
    "petrol",
    "catering",
    "construction",
    "civil works",
    "repair and installation",
    "consulting",
    "training",
}

SUPPLY_KEYWORDS = {
    "supply",
    "delivery",
    "supply and delivery",
    "goods",
    "materials",
    "equipment",
    "stationery",
    "furniture",
    "uniform",
    "ppe",
    "tools",
    "corporate gifts",
    "gift packs",
    "consumables",
}

RFQ_KEYWORDS = {
    "rfq",
    "quotation",
    "quote",
    "request for quotation",
    "bid",
    "tender",
    "download",
    "closing date",
    "compulsory briefing",
    "non-compulsory briefing",
    "submission",
    "enquiries",
}

NOISE_EXACT_TITLES = {
    "tenders",
    "tender",
    "request for bid",
    "request for bid (open-tender)",
    "open tender",
    "rfq",
    "rfqs",
    "download",
    "downloads",
    "click here",
    "home",
    "opportunities",
    "etenders",
    "transnet port terminals rfq/tenders",
}

NOISE_FRAGMENTS = {
    "welcome to",
    "login",
    "register",
    "forgot password",
    "privacy policy",
    "terms and conditions",
    "contact us",
    "site map",
    "request for information specification meeting invitation",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _combined_text(item: Dict[str, Any]) -> str:
    parts = [
        item.get("title"),
        item.get("description"),
        item.get("raw_text"),
        item.get("category"),
        item.get("classification"),
        item.get("buyer_name"),
        item.get("source_name"),
    ]
    return " ".join(_clean(p) for p in parts if _clean(p)).lower()


def is_noise_title(title: Any) -> bool:
    title_text = _clean(title)
    title_lower = title_text.lower().strip()

    if not title_lower:
        return True

    if len(title_lower) < MIN_TITLE_LENGTH:
        return True

    if title_lower in NOISE_EXACT_TITLES:
        return True

    if "@" in title_lower and len(title_lower.split()) <= 2:
        return True

    return any(fragment in title_lower for fragment in NOISE_FRAGMENTS)


def classify_rfq(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "status": "rejected",
            "decision": "reject",
            "score": 0,
            "reason": "invalid_item",
            "service_version": SERVICE_VERSION,
            "checked_at": _now(),
        }

    title = _clean(item.get("title"))
    text = _combined_text(item)

    reasons: List[str] = []
    score = 0

    if is_noise_title(title):
        reasons.append("source_noise_or_generic_title")
        score -= 40

    excluded_hits = sorted([kw for kw in EXCLUDED_KEYWORDS if kw in text])
    if excluded_hits:
        reasons.append("excluded_keywords:" + ",".join(excluded_hits[:5]))
        score -= 60

    supply_hits = sorted([kw for kw in SUPPLY_KEYWORDS if kw in text])
    rfq_hits = sorted([kw for kw in RFQ_KEYWORDS if kw in text])

    score += min(len(supply_hits) * 15, 45)
    score += min(len(rfq_hits) * 8, 30)

    if _clean(item.get("closing_date") or item.get("closing_at")):
        score += 10

    if _clean(item.get("document_url") or item.get("download_url") or item.get("source_url")):
        score += 8

    if _clean(item.get("recipient_email") or item.get("buyer_email") or item.get("submission_email")):
        score += 7

    if item.get("briefing_required") is True:
        reasons.append("briefing_required")
        score -= 50

    score = max(0, min(100, int(score)))

    if excluded_hits:
        decision = "reject"
        status = "blocked"
    elif score >= AUTO_PROMOTE_SCORE:
        decision = "auto_promote"
        status = "accepted"
    elif score >= MIN_RFQ_SCORE:
        decision = "review"
        status = "review"
    else:
        decision = "reject"
        status = "rejected"
        if not reasons:
            reasons.append("score_below_threshold")

    return {
        "status": status,
        "decision": decision,
        "score": score,
        "reason": ";".join(reasons) if reasons else "accepted",
        "supply_keyword_hits": supply_hits[:10],
        "rfq_keyword_hits": rfq_hits[:10],
        "excluded_keyword_hits": excluded_hits[:10],
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
    }


def apply_smart_rfq_detection(item: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(item or {})
    classification = classify_rfq(item)
    item["smart_rfq_detection"] = classification

    decision = classification.get("decision")
    reason = classification.get("reason")
    score = classification.get("score", 0)

    if decision == "auto_promote":
        item["eligible"] = True
        item["quote_ready"] = True
        item["pipeline_status"] = item.get("pipeline_status") or "smart_rfq_accepted"
        item["eligibility_reason"] = f"V31 accepted RFQ with score {score}"
        item["exclusion_reason"] = ""
    elif decision == "review":
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "manual_review_required"
        item["submission_status"] = "manual_review_required"
        item["eligibility_reason"] = f"V31 review required with score {score}"
        item["exclusion_reason"] = reason
    else:
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "smart_rfq_rejected"
        item["submission_status"] = "skipped"
        item["eligibility_reason"] = f"V31 rejected RFQ with score {score}"
        item["exclusion_reason"] = reason

    item["updated_at"] = _now()
    return item


def filter_smart_rfqs(items: Any) -> Dict[str, Any]:
    if not isinstance(items, list):
        items = []

    processed: List[Dict[str, Any]] = []
    accepted: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for raw in items:
        if not isinstance(raw, dict):
            continue

        item = apply_smart_rfq_detection(raw)
        processed.append(item)

        decision = item.get("smart_rfq_detection", {}).get("decision")
        if decision == "auto_promote":
            accepted.append(item)
        elif decision == "review":
            review.append(item)
        else:
            rejected.append(item)

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "total": len(processed),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len(rejected),
        "items": processed,
        "accepted_items": accepted,
        "review_items": review,
        "rejected_items": rejected,
    }
