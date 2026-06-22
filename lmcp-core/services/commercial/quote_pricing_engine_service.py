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


def _pricing_override_for_row(
    row: Dict[str, Any],
    *,
    pricing_overrides: Optional[Dict[str, Any]] = None,
    description_price_lookup: Optional[Dict[str, Any]] = None,
    default_unit_price: Optional[float] = None,
) -> Optional[float]:
    pricing_overrides = pricing_overrides or {}
    description_price_lookup = description_price_lookup or {}

    source_item_number = row.get("source_item_number")
    buyer_item_number = row.get("buyer_item_number")
    description = _clean(row.get("description")).lower()
    source_description = _clean(row.get("source_description")).lower()

    for candidate in (source_item_number, buyer_item_number):
        if candidate is None:
            continue
        if str(candidate) in pricing_overrides:
            return _coerce_float(pricing_overrides.get(str(candidate)))
        if candidate in pricing_overrides:
            return _coerce_float(pricing_overrides.get(candidate))

    for lookup_key, price in description_price_lookup.items():
        needle = _clean(lookup_key).lower()
        if needle and (needle in description or needle in source_description):
            return _coerce_float(price)

    return _coerce_float(default_unit_price)


def price_buyer_schedule_rows(
    buyer_schedule_rows: List[Dict[str, Any]],
    *,
    pricing_overrides: Optional[Dict[str, Any]] = None,
    description_price_lookup: Optional[Dict[str, Any]] = None,
    default_unit_price: Optional[float] = None,
    vat_rate: Optional[float] = None,
) -> Dict[str, Any]:
    priced_rows: List[Dict[str, Any]] = []

    priced_count = 0
    pending_count = 0
    total_priced_value = 0.0
    priced_item_numbers: List[int] = []
    pending_item_numbers: List[int] = []

    for row in buyer_schedule_rows or []:
        working = deepcopy(row)

        qty = _coerce_float(working.get("estimated_quantity") or working.get("quantity"))
        existing_unit_price = _coerce_float(working.get("unit_price"))
        selected_unit_price = existing_unit_price

        if selected_unit_price is None:
            selected_unit_price = _pricing_override_for_row(
                working,
                pricing_overrides=pricing_overrides,
                description_price_lookup=description_price_lookup,
                default_unit_price=default_unit_price,
            )

        line_total = None
        pricing_status = "pending_price"
        pricing_source = "none"

        if existing_unit_price is not None:
            pricing_source = "existing_row_unit_price"
        elif selected_unit_price is not None and pricing_overrides:
            src_item = working.get("source_item_number")
            buyer_item = working.get("buyer_item_number")
            if str(src_item) in pricing_overrides or src_item in pricing_overrides:
                pricing_source = "item_override"
            elif str(buyer_item) in pricing_overrides or buyer_item in pricing_overrides:
                pricing_source = "item_override"
        if pricing_source == "none" and selected_unit_price is not None and description_price_lookup:
            pricing_source = "description_lookup"
        if pricing_source == "none" and selected_unit_price is not None:
            pricing_source = "default_unit_price"

        if qty is not None and selected_unit_price is not None:
            line_total = round(qty * selected_unit_price, 2)
            pricing_status = "priced"
            priced_count += 1
            total_priced_value += line_total
            if working.get("source_item_number") is not None:
                priced_item_numbers.append(int(working["source_item_number"]))
        else:
            pending_count += 1
            if working.get("source_item_number") is not None:
                pending_item_numbers.append(int(working["source_item_number"]))

        working["unit_price"] = selected_unit_price
        working["total_price"] = line_total
        working["line_total"] = line_total
        working["pricing_status"] = pricing_status
        working["pricing_source"] = pricing_source
        working["vat_rate"] = _coerce_float(vat_rate) if vat_rate is not None else None

        priced_rows.append(working)

    return {
        "rows": priced_rows,
        "stats": {
            "input_rows": len(buyer_schedule_rows or []),
            "priced_rows": priced_count,
            "pending_rows": pending_count,
            "total_priced_value": round(total_priced_value, 2),
            "priced_item_numbers": priced_item_numbers,
            "pending_item_numbers": pending_item_numbers,
        },
    }


def attach_quote_pricing_to_record(
    record: Dict[str, Any],
    *,
    buyer_schedule_rows_key: str = "buyer_pricing_schedule_rows",
    metadata_key: str = "metadata",
) -> Dict[str, Any]:
    working = deepcopy(record or {})
    metadata = working.get(metadata_key) or {}
    buyer_schedule_rows = working.get(buyer_schedule_rows_key) or []

    pricing_result = price_buyer_schedule_rows(
        buyer_schedule_rows,
        pricing_overrides=metadata.get("pricing_overrides"),
        description_price_lookup=metadata.get("description_price_lookup"),
        default_unit_price=_coerce_float(metadata.get("default_unit_price")),
        vat_rate=_coerce_float(metadata.get("vat_rate")),
    )

    priced_rows = pricing_result.get("rows", [])
    stats = pricing_result.get("stats", {})

    working["quote_pricing_engine"] = stats
    working["priced_buyer_schedule_rows"] = priced_rows
    working["priced_buyer_schedule_count"] = len(priced_rows)
    working["pricing_pending_count"] = int(stats.get("pending_rows", 0) or 0)
    working["priced_buyer_schedule_items"] = [
        {
            "item_number": row.get("buyer_item_number") or row.get("source_item_number"),
            "description": row.get("description"),
            "unit": row.get("unit"),
            "quantity": row.get("estimated_quantity") if row.get("estimated_quantity") is not None else row.get("quantity"),
            "unit_price": row.get("unit_price"),
            "line_total": row.get("total_price") if row.get("total_price") is not None else row.get("line_total"),
            "pricing_status": row.get("pricing_status"),
            "pricing_source": row.get("pricing_source"),
        }
        for row in priced_rows
    ]
    return working

