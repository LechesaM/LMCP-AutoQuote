from __future__ import annotations

"""
LMCP V32 Real RFQ Extractor

Drop-in:
    app/services/real_rfq_extractor_v32_service.py

Purpose:
    Convert noisy portal harvest output into cleaner real RFQ candidates by enforcing:
      - meaningful title
      - document/link signal
      - closing date/submission signal
      - RFQ/tender language
      - LMCP exclusion rules
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

SERVICE_VERSION = "V32_REAL_RFQ_EXTRACTOR"

EXCLUDED = [
    "medical", "biomedical", "pharmaceutical", "medicine", "surgical",
    "clinic", "hospital", "manikin", "manikins", "ict", "it equipment",
    "computer", "laptop", "server", "software", "printer", "fuel",
    "diesel", "petrol", "catering", "repair and installation",
    "construction", "civil works", "consulting", "training",
]

SUPPLY = [
    "supply", "delivery", "supply and delivery", "goods", "materials",
    "equipment", "stationery", "furniture", "uniform", "ppe", "tools",
    "corporate gifts", "gift packs", "consumables",
]

RFQ_SIGNALS = [
    "rfq", "request for quotation", "quotation", "quote", "bid", "tender",
    "closing date", "closing time", "submission", "download", "enquiries",
    "compulsory briefing", "non-compulsory briefing",
]

NOISE_TITLES = {
    "tenders", "tender", "request for bid", "request for bid (open-tender)",
    "open tender", "opportunities", "home", "download", "downloads",
    "click here", "etenders", "rfq", "rfqs",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _text(item: Dict[str, Any]) -> str:
    return " ".join(
        _clean(item.get(k))
        for k in [
            "title", "description", "raw_text", "buyer_name", "source_name",
            "category", "classification", "document_url", "source_url", "detail_url",
        ]
        if _clean(item.get(k))
    ).lower()


def _has_date_signal(item: Dict[str, Any]) -> bool:
    if _clean(item.get("closing_date") or item.get("closing_at") or item.get("published_date")):
        return True
    text = _text(item)
    return bool(re.search(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b", text))


def _has_document_signal(item: Dict[str, Any]) -> bool:
    for key in ["document_url", "download_url", "attachment_url", "detail_url", "source_url"]:
        value = _lower(item.get(key))
        if value.startswith("http") and not value.endswith("/Home/opportunities".lower()):
            return True
    text = _text(item)
    return any(x in text for x in [".pdf", ".xlsx", ".docx", "download"])


def _is_noise_title(title: Any) -> bool:
    title = _lower(title)
    if not title:
        return True
    if title in NOISE_TITLES:
        return True
    if len(title) < 15:
        return True
    if "@" in title and len(title.split()) <= 2:
        return True
    return False


def extract_real_rfq_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(item or {})
    text = _text(item)
    title = _clean(item.get("title"))

    excluded_hits = [x for x in EXCLUDED if x in text]
    supply_hits = [x for x in SUPPLY if x in text]
    rfq_hits = [x for x in RFQ_SIGNALS if x in text]

    score = 0
    reasons: List[str] = []

    if _is_noise_title(title):
        score -= 50
        reasons.append("noise_title")

    if excluded_hits:
        score -= 80
        reasons.append("excluded:" + ",".join(excluded_hits[:5]))

    if supply_hits:
        score += min(45, 15 * len(supply_hits))
    else:
        reasons.append("no_supply_signal")

    if rfq_hits:
        score += min(30, 8 * len(rfq_hits))
    else:
        reasons.append("no_rfq_signal")

    if _has_document_signal(item):
        score += 15
    else:
        reasons.append("no_document_signal")

    if _has_date_signal(item):
        score += 10
    else:
        reasons.append("no_date_signal")

    score = max(0, min(100, score))

    accepted = score >= 65 and not excluded_hits and not _is_noise_title(title)
    review = 45 <= score < 65 and not excluded_hits and not _is_noise_title(title)

    if accepted:
        decision = "accept"
        pipeline_status = "v32_real_rfq_accepted"
    elif review:
        decision = "review"
        pipeline_status = "v32_real_rfq_review"
    else:
        decision = "reject"
        pipeline_status = "v32_real_rfq_rejected"

    item["v32_real_rfq"] = {
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "decision": decision,
        "score": score,
        "reasons": reasons,
        "supply_hits": supply_hits[:10],
        "rfq_hits": rfq_hits[:10],
        "excluded_hits": excluded_hits[:10],
        "has_document_signal": _has_document_signal(item),
        "has_date_signal": _has_date_signal(item),
    }

    if decision == "accept":
        item["eligible"] = True
        item["quote_ready"] = True
        item["pipeline_status"] = pipeline_status
        item["eligibility_reason"] = f"V32 real RFQ accepted with score {score}"
        item["exclusion_reason"] = ""
    elif decision == "review":
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = pipeline_status
        item["submission_status"] = "manual_review_required"
        item["eligibility_reason"] = f"V32 review required with score {score}"
        item["exclusion_reason"] = ";".join(reasons)
    else:
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = pipeline_status
        item["submission_status"] = "skipped"
        item["eligibility_reason"] = f"V32 rejected with score {score}"
        item["exclusion_reason"] = ";".join(reasons)

    item["updated_at"] = _now()
    return item


def extract_real_rfqs(items: Any) -> Dict[str, Any]:
    if not isinstance(items, list):
        items = []

    processed = []
    accepted = []
    review = []
    rejected = []

    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = extract_real_rfq_candidate(raw)
        processed.append(item)
        decision = item.get("v32_real_rfq", {}).get("decision")
        if decision == "accept":
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
