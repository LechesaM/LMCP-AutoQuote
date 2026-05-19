from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from app.domain.rfq import RFQRecord

EXCLUSION_KEYWORDS = {
    "medical consumables": "medical consumables",
    "it equipment": "it equipment",
    "petrol": "petrol",
    "diesel": "diesel",
    "catering": "catering",
    "compulsory briefing": "compulsory briefing sessions",
    "briefing session": "compulsory briefing sessions",
    "site briefing": "compulsory briefing sessions",
}

REQUIRED_FIELDS = {
    "buyer_name": "missing buyer",
    "closing_date": "missing closing date",
    "line_items": "missing line items",
    "title": "missing title",
    "category": "ambiguous category",
}

AMBIGUOUS_CATEGORIES = {
    "",
    "general",
    "general services",
    "other",
    "misc",
    "miscellaneous",
    "unspecified",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower_blob(*values: Any) -> str:
    return " ".join(_text(value).lower() for value in values if _text(value))


def _line_items(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _exclusion_hits(blob: str) -> List[str]:
    hits: List[str] = []
    for keyword, label in EXCLUSION_KEYWORDS.items():
        if keyword in blob and label not in hits:
            hits.append(label)
    return hits


def _missing_required_fields(payload: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for field_name, label in REQUIRED_FIELDS.items():
        if field_name == "line_items":
            if not _line_items(payload.get(field_name)):
                missing.append(label)
        elif not payload.get(field_name):
            missing.append(label)
    return missing


def _warning_reasons(payload: Dict[str, Any], missing: List[str], blob: str) -> List[str]:
    warnings = list(missing)
    category = _text(payload.get("category")).lower()
    if "category" in missing or category in AMBIGUOUS_CATEGORIES:
        warnings.append("ambiguous category")
    if not payload.get("buyer_name"):
        warnings.append("missing buyer")
    if not payload.get("closing_date"):
        warnings.append("missing closing date")
    if not _line_items(payload.get("line_items")):
        warnings.append("missing line items")
    if "briefing" in blob and "compulsory briefing sessions" not in warnings:
        warnings.append("possible briefing requirement")
    return list(dict.fromkeys(warnings))


def _rfq_schema_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = payload.get("rfq_record") if isinstance(payload.get("rfq_record"), dict) else payload.get("rfq")
    base = base if isinstance(base, dict) else payload
    return {
        "tender_id": _text(base.get("tender_id")),
        "source_url": _text(base.get("source_url")),
        "source_path": _text(base.get("source_path")),
        "buyer_name": _text(base.get("buyer_name")),
        "title": _text(base.get("title")),
        "description": _text(base.get("description")),
        "province": _text(base.get("province")),
        "category": _text(base.get("category")),
        "closing_date": base.get("closing_date") or None,
        "compulsory_briefing_required": bool(base.get("compulsory_briefing_required", False)),
        "briefing_date": base.get("briefing_date") or None,
        "documents": base.get("documents") if isinstance(base.get("documents"), list) else [],
        "line_items": _line_items(base.get("line_items")),
        "detected_exclusions": base.get("detected_exclusions") if isinstance(base.get("detected_exclusions"), list) else [],
        "eligible_for_quoting": bool(base.get("eligible_for_quoting", True)),
        "extraction_confidence": float(base.get("extraction_confidence") or 0.0),
        "extraction_notes": base.get("extraction_notes") if isinstance(base.get("extraction_notes"), list) else [],
        "extraction_quality_score": float(base.get("extraction_quality_score") or 0.0),
        "extraction_quality_notes": base.get("extraction_quality_notes") if isinstance(base.get("extraction_quality_notes"), list) else [],
    }


def assess_rfq_extraction_quality(rfq: RFQRecord | Dict[str, Any]) -> Dict[str, Any]:
    payload = rfq.to_jsonable_dict() if isinstance(rfq, RFQRecord) else dict(rfq or {})
    blob = _lower_blob(
        payload.get("title"),
        payload.get("description"),
        payload.get("category"),
        payload.get("buyer_name"),
        payload.get("documents"),
    )
    missing = _missing_required_fields(payload)
    category = _text(payload.get("category")).lower()
    if category in AMBIGUOUS_CATEGORIES and "ambiguous category" not in missing:
        missing.append("ambiguous category")
    exclusions = _exclusion_hits(blob)
    required_present = max(0, len(REQUIRED_FIELDS) - len(missing))
    completeness_score = required_present / max(len(REQUIRED_FIELDS), 1)
    exclusion_confidence = 1.0 if exclusions else (0.4 if "briefing" in blob else 0.0)
    extraction_confidence = round(min(1.0, (completeness_score * 0.7) + (exclusion_confidence * 0.3)), 4)
    notes = _warning_reasons(payload, missing, blob)
    rfq_record = RFQRecord.validate_payload(
        _rfq_schema_payload(
            {
                **payload,
                "detected_exclusions": exclusions,
                "eligible_for_quoting": not bool(exclusions or missing),
                "extraction_confidence": extraction_confidence,
                "extraction_notes": notes,
                "extraction_quality_score": round(completeness_score, 4),
                "extraction_quality_notes": notes,
            }
        )
    ).to_jsonable_dict()
    return {
        "rfq_record": rfq_record,
        "missing_fields": missing,
        "detected_exclusions": exclusions,
        "eligible_for_quoting": not bool(exclusions or missing),
        "exclusion_confidence": round(exclusion_confidence, 4),
        "extraction_confidence": extraction_confidence,
        "extraction_quality_score": round(completeness_score, 4),
        "warnings": notes,
    }


def build_rfq_extraction_quality_report(rfq: RFQRecord | Dict[str, Any]) -> Dict[str, Any]:
    report = assess_rfq_extraction_quality(rfq)
    report["status"] = "healthy" if report["extraction_confidence"] >= 0.6 else "degraded"
    return report
