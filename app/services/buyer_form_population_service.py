from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).replace(",", "").strip())
        except Exception:
            return None


def build_buyer_form_population(
    final_output_rows: List[Dict[str, Any]],
    *,
    metadata: Optional[Dict[str, Any]] = None,
    review_rows_held_back: int = 0,
    quote_pack_payload: Optional[Dict[str, Any]] = None,
    quote_pack_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = _safe_dict(metadata)
    quote_pack_payload = _safe_dict(quote_pack_payload)
    quote_pack_summary = _safe_dict(quote_pack_summary)

    populated_rows: List[Dict[str, Any]] = []
    ready_count = 0
    pending_count = 0
    filled_item_numbers: List[int] = []
    pending_item_numbers: List[int] = []

    for idx, row in enumerate(_safe_list(final_output_rows), start=1):
        source = _safe_dict(row)

        item_number = source.get("item_number")
        unit_price = _coerce_float(source.get("unit_price"))
        line_total = _coerce_float(source.get("line_total"))
        quantity = _coerce_float(source.get("quantity"))
        pricing_status = _clean(source.get("pricing_status")).lower() or "pending"
        schedule_fill_status = _clean(source.get("schedule_fill_status")).lower() or "pending"

        form_status = "ready_for_pdf" if (
            pricing_status == "priced"
            and schedule_fill_status == "filled"
            and quantity is not None
            and unit_price is not None
            and line_total is not None
        ) else "pending_review"

        if form_status == "ready_for_pdf":
            ready_count += 1
            if isinstance(item_number, int):
                filled_item_numbers.append(item_number)
        else:
            pending_count += 1
            if isinstance(item_number, int):
                pending_item_numbers.append(item_number)

        populated_rows.append(
            {
                "form_row_number": idx,
                "buyer_item_number": source.get("item_number"),
                "description": _clean(source.get("description")),
                "specification": _clean(source.get("specification")),
                "unit": _clean(source.get("unit")),
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "pricing_status": pricing_status,
                "schedule_fill_status": schedule_fill_status,
                "form_population_status": form_status,
            }
        )

    buyer_name = _clean(
        quote_pack_payload.get("buyer_name")
        or metadata.get("buyer_name")
    )
    rfq_number = _clean(
        quote_pack_payload.get("rfq_number")
        or metadata.get("buyer_rfq_number")
        or metadata.get("rfq_number")
    )
    document_title = _clean(
        quote_pack_payload.get("document_title")
        or metadata.get("title")
    )
    quote_reference = _clean(
        quote_pack_payload.get("quote_reference")
        or metadata.get("quote_reference")
        or rfq_number
    )

    buyer_form_payload = {
        "buyer_name": buyer_name,
        "rfq_number": rfq_number,
        "document_title": document_title,
        "quote_reference": quote_reference,
        "currency": _clean(quote_pack_summary.get("currency") or metadata.get("currency") or "ZAR"),
        "prices_include_vat": bool(
            quote_pack_summary.get("prices_include_vat", metadata.get("prices_include_vat", True))
        ),
        "vat_rate": _coerce_float(quote_pack_summary.get("vat_rate", metadata.get("vat_rate"))) or 0.0,
        "summary": {
            "subtotal": _coerce_float(quote_pack_summary.get("subtotal")) or 0.0,
            "vat_amount": _coerce_float(quote_pack_summary.get("vat_amount")) or 0.0,
            "grand_total": _coerce_float(quote_pack_summary.get("grand_total")) or 0.0,
            "priced_rows": int(quote_pack_summary.get("priced_rows") or 0),
            "pending_rows": int(quote_pack_summary.get("pending_rows") or 0),
            "review_rows_held_back": int(review_rows_held_back),
        },
        "items": populated_rows,
    }

    return {
        "buyer_form_population": {
            "input_rows": len(_safe_list(final_output_rows)),
            "ready_rows": ready_count,
            "pending_rows": pending_count,
            "review_rows_held_back": int(review_rows_held_back),
            "filled_item_numbers": filled_item_numbers,
            "pending_item_numbers": pending_item_numbers,
            "form_columns": [
                "buyer_item_number",
                "description",
                "specification",
                "unit",
                "quantity",
                "unit_price",
                "line_total",
            ],
        },
        "populated_form_rows": populated_rows,
        "buyer_form_payload": buyer_form_payload,
        "buyer_form_population_ready_count": ready_count,
        "buyer_form_population_pending_count": pending_count,
        "buyer_form_items": [
            {
                "item_number": row.get("buyer_item_number"),
                "description": row.get("description"),
                "specification": row.get("specification"),
                "unit": row.get("unit"),
                "quantity": row.get("quantity"),
                "unit_price": row.get("unit_price"),
                "line_total": row.get("line_total"),
                "form_population_status": row.get("form_population_status"),
            }
            for row in populated_rows
        ],
    }


def attach_buyer_form_population_to_record(
    record: Dict[str, Any],
    *,
    final_output_rows_key: str = "final_output_rows",
    metadata_key: str = "metadata",
    quote_pack_payload_key: str = "quote_pack_payload",
    quote_pack_summary_key: str = "quote_pack_summary",
    review_rows_key: str = "review_rows",
) -> Dict[str, Any]:
    payload = deepcopy(record or {})
    final_output_rows = _safe_list(payload.get(final_output_rows_key))
    metadata = _safe_dict(payload.get(metadata_key))
    quote_pack_payload = _safe_dict(payload.get(quote_pack_payload_key))
    quote_pack_summary = _safe_dict(payload.get(quote_pack_summary_key))
    review_rows = _safe_list(payload.get(review_rows_key))

    result = build_buyer_form_population(
        final_output_rows,
        metadata=metadata,
        review_rows_held_back=len(review_rows),
        quote_pack_payload=quote_pack_payload,
        quote_pack_summary=quote_pack_summary,
    )

    payload.update(result)
    return payload


if __name__ == "__main__":
    from pprint import pprint

    sample_rows = [
        {
            "item_number": 1,
            "description": "Stapler for office use | Uses 26/6 staples",
            "specification": "Uses 26/6 staples",
            "unit": "Each",
            "quantity": 100.0,
            "unit_price": 32.5,
            "line_total": 3250.0,
            "pricing_status": "priced",
            "schedule_fill_status": "filled",
        }
    ]

    result = build_buyer_form_population(
        sample_rows,
        metadata={
            "buyer_name": "STELLENBOSCH MUNICIPALITY",
            "buyer_rfq_number": "B/SM 110/26",
            "title": "SUPPLY AND DELIVERY OF STATIONERY",
            "currency": "ZAR",
            "vat_rate": 15.0,
            "prices_include_vat": True,
        },
        review_rows_held_back=58,
        quote_pack_summary={
            "subtotal": 210800.0,
            "vat_amount": 31620.0,
            "grand_total": 242420.0,
            "priced_rows": 208,
            "pending_rows": 0,
            "currency": "ZAR",
            "prices_include_vat": True,
            "vat_rate": 15.0,
        },
    )
    pprint(result)


