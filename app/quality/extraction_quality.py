from __future__ import annotations

from typing import Any, Dict


def assess_rfq_extraction_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    warnings = []
    if not payload.get("buyer_name"):
        warnings.append("missing buyer")
    if not payload.get("closing_date"):
        warnings.append("missing closing date")
    if not payload.get("line_items"):
        warnings.append("missing line items")
    if not payload.get("category"):
        warnings.append("ambiguous category")
    excluded = []
    searchable = " ".join(
        str(part or "").lower()
        for part in (
            payload.get("title"),
            payload.get("category"),
            payload.get("notes"),
            " ".join(str(item.get("notes") or "") for item in (payload.get("line_items") or []) if isinstance(item, dict)),
        )
    )
    if "briefing" in searchable:
        warnings.append("possible briefing requirement")
        excluded.append("compulsory briefing sessions")
    return {
        "extraction_quality_score": 1.0 - (0.2 * len(warnings)),
        "warnings": warnings,
        "detected_exclusions": excluded,
        "exclusion_confidence": 0.5 if excluded else 0.0,
    }
