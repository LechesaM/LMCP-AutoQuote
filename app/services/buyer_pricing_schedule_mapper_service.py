from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


DEFAULT_COLUMNS = [
    "item_number",
    "description",
    "specification",
    "unit",
    "estimated_quantity",
    "unit_price",
    "total_price",
]


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



def _clean_text(value: Any) -> str:
    return str(value or "").strip()



def _normalize_mapper_row(row: Dict[str, Any], sequence_number: int) -> Dict[str, Any]:
    item_number = row.get("item_number")
    description = _clean_text(row.get("description"))
    specification = _clean_text(row.get("specification"))
    unit = _clean_text(row.get("unit"))
    quantity = _safe_float(row.get("quantity"))
    unit_price = _safe_float(row.get("unit_price"))
    total_price = _safe_float(row.get("line_total"))
    integrity_status = _clean_text(row.get("integrity_status")) or "warning"
    integrity_flags = row.get("integrity_flags") if isinstance(row.get("integrity_flags"), list) else []
    confidence = _clean_text(row.get("confidence")) or "medium"

    source_description = description
    buyer_description = description
    if specification:
        buyer_description = f"{description} | {specification}" if description else specification

    mapping_status = "mapped"
    mapping_confidence = "high" if integrity_status == "valid" else "medium"

    return {
        "buyer_row_number": sequence_number,
        "buyer_item_number": item_number,
        "source_item_number": item_number,
        "description": buyer_description,
        "source_description": source_description,
        "specification": specification,
        "unit": unit,
        "estimated_quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "source_row_ready_status": row.get("row_ready_status", "needs_review"),
        "integrity_status": integrity_status,
        "integrity_flags": integrity_flags,
        "confidence": confidence,
        "mapping_status": mapping_status,
        "mapping_confidence": mapping_confidence,
        "source_line": _clean_text(row.get("source_line")),
        "routing_row_index": row.get("routing_row_index"),
    }



def map_pricing_ready_rows_to_buyer_schedule(
    pricing_ready_rows: List[Dict[str, Any]],
    *,
    review_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    ready_rows = _safe_rows(pricing_ready_rows)
    review_rows_safe = _safe_rows(review_rows)

    mapped_rows: List[Dict[str, Any]] = []
    buyer_schedule_items: List[Dict[str, Any]] = []

    for idx, row in enumerate(ready_rows, start=1):
        mapped = _normalize_mapper_row(row, idx)
        mapped_rows.append(mapped)
        buyer_schedule_items.append(
            {
                "item_number": mapped["buyer_item_number"],
                "description": mapped["description"],
                "unit": mapped["unit"],
                "quantity": mapped["estimated_quantity"],
                "unit_price": mapped["unit_price"],
                "line_total": mapped["total_price"],
            }
        )

    review_item_numbers = [r.get("item_number") for r in review_rows_safe if r.get("item_number") is not None]
    mapped_item_numbers = [r.get("buyer_item_number") for r in mapped_rows if r.get("buyer_item_number") is not None]

    return {
        "mapped_rows": mapped_rows,
        "buyer_schedule_items": buyer_schedule_items,
        "stats": {
            "input_pricing_ready_rows": len(ready_rows),
            "input_review_rows": len(review_rows_safe),
            "mapped_rows": len(mapped_rows),
            "review_rows_held_back": len(review_rows_safe),
            "mapped_item_numbers": mapped_item_numbers,
            "review_item_numbers": review_item_numbers,
            "buyer_schedule_columns": DEFAULT_COLUMNS,
        },
    }



def attach_buyer_pricing_schedule_mapping_to_record(
    record: Dict[str, Any],
    *,
    pricing_ready_rows_key: str = "pricing_ready_rows",
    review_rows_key: str = "review_rows",
) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    pricing_ready_rows = payload.get(pricing_ready_rows_key, [])
    review_rows = payload.get(review_rows_key, [])

    mapping_result = map_pricing_ready_rows_to_buyer_schedule(
        pricing_ready_rows,
        review_rows=review_rows,
    )

    payload["buyer_pricing_schedule_mapper"] = mapping_result.get("stats", {})
    payload["buyer_pricing_schedule_rows"] = mapping_result.get("mapped_rows", [])
    payload["buyer_schedule_items"] = mapping_result.get("buyer_schedule_items", [])
    payload["buyer_schedule_mapped_count"] = len(payload["buyer_pricing_schedule_rows"])
    payload["buyer_schedule_review_held_back_count"] = len(review_rows) if isinstance(review_rows, list) else 0
    return payload


if __name__ == "__main__":
    from pprint import pprint

    pricing_ready_rows = [
        {
            "item_number": 1,
            "description": "Stapler for office use",
            "specification": "Uses 26/6 staples",
            "unit": "Each",
            "quantity": 100.0,
            "unit_price": None,
            "line_total": None,
            "integrity_status": "valid",
            "integrity_flags": [],
            "row_ready_status": "ready",
            "confidence": "medium",
            "source_line": "1 Stapler for office use ... Each 100",
            "routing_row_index": 0,
        }
    ]

    review_rows = [
        {
            "item_number": 35,
            "description": "Goods Received Notebooks Size:",
            "specification": "420mm x 245mm",
            "row_ready_status": "needs_review",
        }
    ]

    result = map_pricing_ready_rows_to_buyer_schedule(
        pricing_ready_rows,
        review_rows=review_rows,
    )
    pprint(result["mapped_rows"])
    pprint(result["stats"])


