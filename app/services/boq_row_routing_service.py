from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


READY_STATUS_READY = "ready"
READY_STATUS_NEEDS_REVIEW = "needs_review"
READY_STATUS_UNUSABLE = "unusable"


def _safe_rows(rows: Any) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [deepcopy(r) for r in rows if isinstance(r, dict)]


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _clean_flags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_row(row: Dict[str, Any], row_index: int) -> Dict[str, Any]:
    normalized = deepcopy(row)
    normalized.setdefault("item_number", None)
    normalized.setdefault("description", "")
    normalized.setdefault("specification", "")
    normalized.setdefault("unit", "")
    normalized.setdefault("quantity", None)
    normalized.setdefault("unit_price", None)
    normalized.setdefault("line_total", None)
    normalized.setdefault("confidence", "medium")
    normalized.setdefault("integrity_status", "warning")
    normalized.setdefault("integrity_error_count", 0)
    normalized.setdefault("integrity_warning_count", 0)
    normalized.setdefault("integrity_flags", [])
    normalized.setdefault("row_ready_status", READY_STATUS_NEEDS_REVIEW)
    normalized.setdefault("source_line", "")

    normalized["quantity"] = _safe_float(normalized.get("quantity"))
    normalized["unit_price"] = _safe_float(normalized.get("unit_price"))
    normalized["line_total"] = _safe_float(normalized.get("line_total"))
    normalized["integrity_flags"] = _clean_flags(normalized.get("integrity_flags"))
    normalized["routing_row_index"] = row_index
    return normalized


def route_boq_rows_for_pricing(
    rows: List[Dict[str, Any]],
    *,
    include_review_payload: bool = True,
) -> Dict[str, Any]:
    """
    Splits normalized BOQ rows into three production buckets:

    1. pricing_ready_rows
       Safe for buyer schedule mapping and pricing.

    2. review_rows
       Need fallback parsing, retry isolation, or manual review.

    3. unusable_rows
       Too broken to proceed without intervention.

    Input rows are expected to already be normalized by:
      - run_boq_cleanup_pipeline(...)
      or
      - normalize_boq_rows(...)
    """
    safe_rows = _safe_rows(rows)

    pricing_ready_rows: List[Dict[str, Any]] = []
    review_rows: List[Dict[str, Any]] = []
    unusable_rows: List[Dict[str, Any]] = []

    for idx, row in enumerate(safe_rows):
        normalized = _normalize_row(row, idx)
        status = str(normalized.get("row_ready_status") or READY_STATUS_NEEDS_REVIEW).strip().lower()

        if status == READY_STATUS_READY:
            pricing_ready_rows.append(normalized)
        elif status == READY_STATUS_UNUSABLE:
            unusable_rows.append(normalized)
        else:
            review_payload = normalized if include_review_payload else {
                "item_number": normalized.get("item_number"),
                "description": normalized.get("description"),
                "specification": normalized.get("specification"),
                "integrity_status": normalized.get("integrity_status"),
                "integrity_flags": normalized.get("integrity_flags"),
                "routing_row_index": normalized.get("routing_row_index"),
            }
            review_rows.append(review_payload)

    pricing_ready_item_numbers = [
        row.get("item_number") for row in pricing_ready_rows if row.get("item_number") is not None
    ]
    review_item_numbers = [
        row.get("item_number") for row in review_rows if row.get("item_number") is not None
    ]
    unusable_item_numbers = [
        row.get("item_number") for row in unusable_rows if row.get("item_number") is not None
    ]

    return {
        "pricing_ready_rows": pricing_ready_rows,
        "review_rows": review_rows,
        "unusable_rows": unusable_rows,
        "stats": {
            "input_rows": len(safe_rows),
            "pricing_ready_rows": len(pricing_ready_rows),
            "review_rows": len(review_rows),
            "unusable_rows": len(unusable_rows),
            "pricing_ready_item_numbers": pricing_ready_item_numbers,
            "review_item_numbers": review_item_numbers,
            "unusable_item_numbers": unusable_item_numbers,
        },
    }


def attach_boq_routing_to_record(
    record: Dict[str, Any],
    *,
    items_key: str = "items",
    include_review_payload: bool = True,
) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    rows = payload.get(items_key, [])

    routing_result = route_boq_rows_for_pricing(
        rows,
        include_review_payload=include_review_payload,
    )

    payload["boq_row_routing"] = routing_result.get("stats", {})
    payload["pricing_ready_rows"] = routing_result.get("pricing_ready_rows", [])
    payload["review_rows"] = routing_result.get("review_rows", [])
    payload["unusable_rows"] = routing_result.get("unusable_rows", [])
    payload["pricing_ready_count"] = len(payload["pricing_ready_rows"])
    payload["review_rows_count"] = len(payload["review_rows"])
    payload["unusable_rows_count"] = len(payload["unusable_rows"])
    return payload


if __name__ == "__main__":
    from pprint import pprint

    rows = [
        {
            "item_number": 1,
            "description": "Stapler for office use",
            "specification": "Uses 26/6 staples",
            "unit": "Each",
            "quantity": 100.0,
            "unit_price": None,
            "line_total": None,
            "confidence": "medium",
            "integrity_status": "valid",
            "integrity_error_count": 0,
            "integrity_warning_count": 0,
            "integrity_flags": [],
            "row_ready_status": "ready",
            "source_line": "1 Stapler for office use ... Each 100",
        },
        {
            "item_number": 48,
            "description": "Suspension File Coated Metal Rails Colour Tabs Included",
            "specification": "Pack of 25 (per colour) 5",
            "unit": "",
            "quantity": None,
            "unit_price": None,
            "line_total": None,
            "confidence": "low",
            "integrity_status": "warning",
            "integrity_error_count": 0,
            "integrity_warning_count": 2,
            "integrity_flags": [
                "possible_unit_qty_still_buried_in_specification",
                "unit_qty_still_in_specification",
            ],
            "row_ready_status": "needs_review",
            "source_line": "48 ... Pack of 25 (per colour) 5",
        },
    ]

    result = route_boq_rows_for_pricing(rows)
    pprint(result["stats"])
    pprint(result["pricing_ready_rows"])
    pprint(result["review_rows"])


