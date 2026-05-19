from __future__ import annotations

from typing import Any, Dict, List

from app.domain.quote import BuyerPricingScheduleCompletion

REQUIRED_ROW_FIELDS = ("item_description", "description", "quantity", "unit", "unit_price", "total")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("rows", "items", "line_items", "schedule_rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _missing_row_fields(row: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if not _text(row.get("item_description") or row.get("description")):
        missing.append("item description")
    if row.get("quantity") in (None, "", 0, 0.0):
        missing.append("quantity")
    if not _text(row.get("unit")):
        missing.append("unit")
    if row.get("unit_price") in (None, "", 0, 0.0):
        missing.append("unit price")
    if row.get("total") in (None, "", 0, 0.0):
        missing.append("total")
    if row.get("vat_applicable") and row.get("vat_amount") in (None, "", 0, 0.0):
        missing.append("vat")
    if row.get("delivery_applicable") and row.get("delivery_cost") in (None, "", 0, 0.0):
        missing.append("delivery")
    return missing


def assess_pricing_schedule_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = _rows(payload)
    row_results: List[Dict[str, Any]] = []
    total_missing = 0
    for row in rows:
        missing = _missing_row_fields(row)
        total_missing += len(missing)
        warnings = []
        if missing:
            warnings.append(f"incomplete schedule row: {', '.join(missing)}")
        row_results.append(
            {
                "description": row.get("item_description") or row.get("description") or "",
                "missing_fields": missing,
                "warnings": warnings,
                "complete": not bool(missing),
            }
        )
    total_possible = max(len(rows) * 5, 1)
    completion_score = max(0.0, min(1.0, 1.0 - (total_missing / total_possible)))
    missing_fields = sorted({field for result in row_results for field in result["missing_fields"]})
    warnings = [item for result in row_results for item in result["warnings"]]
    completed = bool(rows) and not missing_fields
    completion = BuyerPricingScheduleCompletion.validate_payload(
        {
            "completed_buyer_schedule_path": payload.get("completed_buyer_schedule_path", ""),
            "completed": completed,
            "missing_fields": missing_fields,
            "completion_score": round(completion_score, 4),
            "warnings": warnings,
        }
    ).to_jsonable_dict()
    return {
        "buyer_pricing_schedule_completion": completion,
        "rows_checked": len(rows),
        "row_results": row_results,
        "missing_fields": missing_fields,
        "warnings": warnings,
        "completed": completed,
        "completion_score": round(completion_score, 4),
        "status": "healthy" if completion_score >= 0.8 else "degraded",
    }


def build_pricing_schedule_quality_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    return assess_pricing_schedule_quality(payload)
