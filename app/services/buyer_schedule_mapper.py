from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return default

    try:
        return float(text)
    except (ValueError, TypeError):
        return default


def _safe_decimal(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    text = str(value).strip().replace(",", "")
    if not text:
        return default

    try:
        return Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return default


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _first_non_empty(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        if isinstance(value, dict) and len(value) == 0:
            continue
        return value
    return default


def _extract_buyer_schedule_candidates(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Looks in multiple possible RFQ/result locations for buyer schedule rows.
    """
    candidates = [
        result.get("buyer_pricing_schedule"),
        result.get("pricing_schedule"),
        result.get("buyer_schedule"),
        (result.get("submission_pack") or {}).get("buyer_pricing_schedule"),
        (result.get("submission_pack") or {}).get("pricing_schedule"),
        (result.get("rfq") or {}).get("buyer_pricing_schedule"),
        (result.get("rfq") or {}).get("pricing_schedule"),
        (result.get("rfq_data") or {}).get("buyer_pricing_schedule"),
        (result.get("rfq_data") or {}).get("pricing_schedule"),
        (result.get("parsed_rfq") or {}).get("buyer_pricing_schedule"),
        (result.get("parsed_rfq") or {}).get("pricing_schedule"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return deepcopy(candidate)

    return []


def _extract_quote_items(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Looks for generated LMCP quote items / supplier-priced items as fallback source.
    """
    candidates = [
        result.get("quoted_items"),
        result.get("quote_items"),
        result.get("line_items"),
        (result.get("quote") or {}).get("items"),
        (result.get("quotation") or {}).get("items"),
        (result.get("comparison") or {}).get("recommended_items"),
        (result.get("submission_pack") or {}).get("quote_items"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return deepcopy(candidate)

    return []


def _normalize_schedule_row(
    row: Dict[str, Any],
    index: int,
    fallback_quote_item: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fallback_quote_item = fallback_quote_item or {}

    item_no = _first_non_empty(
        row.get("item_no"),
        row.get("item_number"),
        row.get("item"),
        row.get("line_no"),
        row.get("line_number"),
        fallback_quote_item.get("item_no"),
        fallback_quote_item.get("item_number"),
        default=str(index + 1),
    )

    description = _first_non_empty(
        row.get("description"),
        row.get("item_description"),
        row.get("specification"),
        row.get("name"),
        row.get("title"),
        fallback_quote_item.get("description"),
        fallback_quote_item.get("item_description"),
        fallback_quote_item.get("name"),
        default=f"Item {index + 1}",
    )

    unit = _first_non_empty(
        row.get("unit"),
        row.get("uom"),
        row.get("measure"),
        fallback_quote_item.get("unit"),
        fallback_quote_item.get("uom"),
        default="Item",
    )

    quantity = _safe_float(
        _first_non_empty(
            row.get("quantity"),
            row.get("qty"),
            row.get("estimated_quantity"),
            fallback_quote_item.get("quantity"),
            fallback_quote_item.get("qty"),
            default=1,
        ),
        default=1.0,
    )

    unit_price = _safe_decimal(
        _first_non_empty(
            row.get("unit_price"),
            row.get("rate"),
            row.get("price"),
            row.get("quoted_rate"),
            fallback_quote_item.get("unit_price"),
            fallback_quote_item.get("rate"),
            fallback_quote_item.get("price"),
            default="0.00",
        )
    )

    total_price = _safe_decimal(
        _first_non_empty(
            row.get("total_price"),
            row.get("amount"),
            row.get("total"),
            row.get("extended_total"),
            fallback_quote_item.get("total_price"),
            fallback_quote_item.get("amount"),
            fallback_quote_item.get("total"),
            default=None,
        ),
        default=_round_money(unit_price * Decimal(str(quantity))),
    )

    return {
        "item_no": _safe_str(item_no, str(index + 1)),
        "description": _safe_str(description, f"Item {index + 1}"),
        "unit": _safe_str(unit, "Item"),
        "quantity": quantity,
        "unit_price": float(_round_money(unit_price)),
        "total_price": float(_round_money(total_price)),
        "buyer_row": deepcopy(row),
    }


def _build_fallback_schedule_from_quote_items(
    quote_items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for index, item in enumerate(quote_items):
        normalized.append(_normalize_schedule_row({}, index, fallback_quote_item=item))

    return normalized


def map_and_normalize_buyer_schedule(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point.

    Returns a dict with:
    - used_buyer_format: bool
    - buyer_pricing_schedule: list
    - pricing_schedule: list
    - pricing_schedule_source: str
    """
    buyer_rows = _extract_buyer_schedule_candidates(result)
    quote_items = _extract_quote_items(result)

    normalized_rows: List[Dict[str, Any]] = []

    if buyer_rows:
        for index, buyer_row in enumerate(buyer_rows):
            fallback_item = quote_items[index] if index < len(quote_items) else {}
            normalized_rows.append(
                _normalize_schedule_row(
                    row=buyer_row,
                    index=index,
                    fallback_quote_item=fallback_item,
                )
            )

        return {
            "used_buyer_format": True,
            "buyer_pricing_schedule": normalized_rows,
            "pricing_schedule": normalized_rows,
            "pricing_schedule_source": "buyer_format",
        }

    if quote_items:
        fallback_rows = _build_fallback_schedule_from_quote_items(quote_items)
        return {
            "used_buyer_format": False,
            "buyer_pricing_schedule": [],
            "pricing_schedule": fallback_rows,
            "pricing_schedule_source": "lmcp_generated",
        }

    return {
        "used_buyer_format": False,
        "buyer_pricing_schedule": [],
        "pricing_schedule": [],
        "pricing_schedule_source": "none",
    }
