from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def build_final_buyer_pricing_schedule(
    priced_buyer_schedule_rows: List[Dict[str, Any]],
    *,
    include_source_meta: bool = False,
) -> Dict[str, Any]:
    final_rows: List[Dict[str, Any]] = []
    filled_rows = 0
    unpriced_rows = 0
    total_schedule_value = 0.0
    filled_item_numbers: List[int] = []
    unpriced_item_numbers: List[int] = []

    for idx, row in enumerate(priced_buyer_schedule_rows or [], start=1):
        working = deepcopy(row)

        buyer_item_number = working.get("buyer_item_number")
        source_item_number = working.get("source_item_number")
        description = _clean(working.get("description"))
        specification = _clean(working.get("specification"))
        unit = _clean(working.get("unit"))
        quantity = _coerce_float(working.get("estimated_quantity"))
        if quantity is None:
            quantity = _coerce_float(working.get("quantity"))
        unit_price = _coerce_float(working.get("unit_price"))
        total_price = _coerce_float(working.get("total_price"))
        if total_price is None:
            total_price = _coerce_float(working.get("line_total"))
        pricing_status = _clean(working.get("pricing_status")) or "pending_price"

        if pricing_status == "priced" and unit_price is not None and total_price is not None:
            filled_rows += 1
            total_schedule_value += total_price
            if source_item_number is not None:
                try:
                    filled_item_numbers.append(int(source_item_number))
                except Exception:
                    pass
        else:
            unpriced_rows += 1
            if source_item_number is not None:
                try:
                    unpriced_item_numbers.append(int(source_item_number))
                except Exception:
                    pass

        final_row: Dict[str, Any] = {
            "schedule_row_number": idx,
            "buyer_item_number": buyer_item_number,
            "source_item_number": source_item_number,
            "description": description,
            "specification": specification,
            "unit": unit,
            "estimated_quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "pricing_status": pricing_status,
            "pricing_source": _clean(working.get("pricing_source")),
            "integrity_status": _clean(working.get("integrity_status")),
            "mapping_status": _clean(working.get("mapping_status")),
            "schedule_fill_status": "filled" if pricing_status == "priced" and unit_price is not None and total_price is not None else "pending_price",
        }

        if include_source_meta:
            final_row["source_meta"] = {
                "confidence": working.get("confidence"),
                "source_line": working.get("source_line"),
                "routing_row_index": working.get("routing_row_index"),
                "source_row_ready_status": working.get("source_row_ready_status"),
                "integrity_flags": working.get("integrity_flags") or [],
            }

        final_rows.append(final_row)

    return {
        "rows": final_rows,
        "stats": {
            "input_rows": len(priced_buyer_schedule_rows or []),
            "filled_rows": filled_rows,
            "pending_price_rows": unpriced_rows,
            "total_schedule_value": round(total_schedule_value, 2),
            "filled_item_numbers": filled_item_numbers,
            "pending_price_item_numbers": unpriced_item_numbers,
            "schedule_columns": [
                "buyer_item_number",
                "description",
                "specification",
                "unit",
                "estimated_quantity",
                "unit_price",
                "total_price",
            ],
        },
    }


def attach_buyer_pricing_schedule_filler_to_record(
    record: Dict[str, Any],
    *,
    priced_rows_key: str = "priced_buyer_schedule_rows",
    include_source_meta: bool = False,
) -> Dict[str, Any]:
    working = deepcopy(record or {})
    priced_rows = working.get(priced_rows_key) or []

    filler_result = build_final_buyer_pricing_schedule(
        priced_rows,
        include_source_meta=include_source_meta,
    )
    final_rows = filler_result.get("rows", [])
    stats = filler_result.get("stats", {})

    working["buyer_pricing_schedule_filler"] = stats
    working["final_buyer_pricing_schedule_rows"] = final_rows
    working["final_buyer_pricing_schedule_count"] = len(final_rows)
    working["buyer_schedule_fill_pending_count"] = int(stats.get("pending_price_rows", 0) or 0)
    working["final_buyer_schedule_items"] = [
        {
            "item_number": row.get("buyer_item_number") or row.get("source_item_number"),
            "description": row.get("description"),
            "specification": row.get("specification"),
            "unit": row.get("unit"),
            "quantity": row.get("estimated_quantity"),
            "unit_price": row.get("unit_price"),
            "line_total": row.get("total_price"),
            "schedule_fill_status": row.get("schedule_fill_status"),
            "pricing_status": row.get("pricing_status"),
            "pricing_source": row.get("pricing_source"),
        }
        for row in final_rows
    ]
    return working


if __name__ == "__main__":
    from pprint import pprint

    rows = [
        {
            "buyer_row_number": 1,
            "buyer_item_number": 1,
            "source_item_number": 1,
            "description": "Stapler for office use | Uses 26/6 staples",
            "specification": "Uses 26/6 staples",
            "unit": "Each",
            "estimated_quantity": 100.0,
            "unit_price": 32.5,
            "total_price": 3250.0,
            "pricing_status": "priced",
            "pricing_source": "item_override",
            "mapping_status": "mapped",
            "integrity_status": "valid",
        },
        {
            "buyer_row_number": 2,
            "buyer_item_number": 2,
            "source_item_number": 2,
            "description": "Plier stapler | Metal",
            "specification": "Metal",
            "unit": "Each",
            "estimated_quantity": 15.0,
            "unit_price": None,
            "total_price": None,
            "pricing_status": "pending_price",
            "pricing_source": "none",
            "mapping_status": "mapped",
            "integrity_status": "valid",
        },
    ]

    result = build_final_buyer_pricing_schedule(rows, include_source_meta=True)
    pprint(result["rows"])
    pprint(result["stats"])


