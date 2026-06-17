from __future__ import annotations

from typing import Any, Dict


def assess_pricing_schedule_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing_fields = []
    rows = payload.get("rows") or []
    if not rows:
        missing_fields.append("rows")
    else:
        for row in rows:
            if not isinstance(row, dict):
                missing_fields.append("rows")
                break
            if row.get("unit_price") in {None, ""}:
                missing_fields.append("unit_price")
            if row.get("total") in {None, ""}:
                missing_fields.append("total")
            if row.get("vat_applicable") is None:
                missing_fields.append("vat_applicable")
        if not missing_fields and any((row.get("unit_price") in {0, 0.0} or row.get("total") in {0, 0.0}) for row in rows if isinstance(row, dict)):
            missing_fields.append("pricing_incomplete")
    return {
        "completion_score": max(0.0, 1.0 - (0.25 * len(missing_fields))),
        "missing_fields": missing_fields,
        "warnings": missing_fields[:],
        "buyer_pricing_schedule_completion": {"completed": not missing_fields},
    }
