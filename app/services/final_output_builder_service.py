from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = _clean(value).replace(',', '')
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _safe_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(v) for v in value if isinstance(v, dict)]


def build_final_output_payload(
    final_schedule_items: List[Dict[str, Any]],
    *,
    review_rows: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    schedule_items = _safe_items(final_schedule_items)
    held_review_rows = _safe_items(review_rows)
    metadata = deepcopy(metadata or {})

    output_rows: List[Dict[str, Any]] = []
    priced_rows = 0
    pending_rows = 0
    total_value = 0.0
    subtotal_value = 0.0
    margin_value = 0.0
    vat_rate = _coerce_float(metadata.get('vat_rate')) or 0.0
    includes_vat = bool(metadata.get('prices_include_vat', True))

    priced_item_numbers: List[int] = []
    pending_item_numbers: List[int] = []

    for idx, item in enumerate(schedule_items, start=1):
        item_number = item.get('item_number')
        description = _clean(item.get('description'))
        specification = _clean(item.get('specification'))
        unit = _clean(item.get('unit'))
        quantity = _coerce_float(item.get('quantity'))
        unit_price = _coerce_float(item.get('unit_price'))
        line_total = _coerce_float(item.get('line_total'))
        pricing_status = _clean(item.get('pricing_status')) or 'pending_price'
        pricing_source = _clean(item.get('pricing_source'))
        schedule_fill_status = _clean(item.get('schedule_fill_status')) or ('filled' if pricing_status == 'priced' else 'pending_price')
        supplier_name = _clean(item.get('supplier_name'))
        supplier_quote_ref = _clean(item.get('supplier_quote_ref'))
        row_margin_percent = _coerce_float(item.get('margin_percent'))

        if pricing_status == 'priced' and line_total is not None:
            priced_rows += 1
            total_value += line_total
            if row_margin_percent is not None:
                margin_value += round(line_total * (row_margin_percent / 100.0), 2)
            try:
                if item_number is not None:
                    priced_item_numbers.append(int(item_number))
            except Exception:
                pass
        else:
            pending_rows += 1
            try:
                if item_number is not None:
                    pending_item_numbers.append(int(item_number))
            except Exception:
                pass

        output_rows.append({
            'output_row_number': idx,
            'item_number': item_number,
            'description': description,
            'specification': specification,
            'unit': unit,
            'quantity': quantity,
            'unit_price': unit_price,
            'line_total': line_total,
            'pricing_status': pricing_status,
            'pricing_source': pricing_source,
            'schedule_fill_status': schedule_fill_status,
            'supplier_name': supplier_name,
            'supplier_quote_ref': supplier_quote_ref,
            'margin_percent': row_margin_percent,
        })

    if includes_vat and vat_rate > 0:
        vat_amount = round(total_value * vat_rate / (100.0 + vat_rate), 2)
        subtotal_value = round(total_value - vat_amount, 2)
    else:
        subtotal_value = round(total_value, 2)
        vat_amount = round(total_value * vat_rate / 100.0, 2) if vat_rate > 0 else 0.0

    grand_total = round(total_value if includes_vat else subtotal_value + vat_amount, 2)
    margin_percent = round((margin_value / subtotal_value * 100.0) if subtotal_value > 0 else 0.0, 2)

    quote_summary = {
        'currency': _clean(metadata.get('currency')) or 'ZAR',
        'prices_include_vat': includes_vat,
        'vat_rate': vat_rate,
        'subtotal': round(subtotal_value, 2),
        'vat_amount': round(vat_amount, 2),
        'grand_total': grand_total,
        'margin_value': round(margin_value, 2),
        'margin_percent': margin_percent,
        'priced_rows': priced_rows,
        'pending_rows': pending_rows,
        'review_rows_held_back': len(held_review_rows),
    }

    final_output = {
        'quote_reference': _clean(metadata.get('quote_reference')),
        'buyer_name': _clean(metadata.get('buyer_name')),
        'rfq_number': _clean(metadata.get('buyer_rfq_number') or metadata.get('rfq_number')),
        'document_title': _clean(metadata.get('title')),
        'items': output_rows,
        'summary': quote_summary,
        'review_rows_held_back': held_review_rows,
    }

    return {
        'rows': output_rows,
        'final_output': final_output,
        'stats': {
            'input_rows': len(schedule_items),
            'output_rows': len(output_rows),
            'priced_rows': priced_rows,
            'pending_rows': pending_rows,
            'review_rows_held_back': len(held_review_rows),
            'total_schedule_value': round(total_value, 2),
            'priced_item_numbers': priced_item_numbers,
            'pending_item_numbers': pending_item_numbers,
            'output_columns': [
                'item_number',
                'description',
                'specification',
                'unit',
                'quantity',
                'unit_price',
                'line_total',
            ],
        },
    }


def attach_final_output_builder_to_record(
    record: Dict[str, Any],
    *,
    final_schedule_items_key: str = 'final_buyer_schedule_items',
    review_rows_key: str = 'review_rows',
    metadata_key: str = 'metadata',
) -> Dict[str, Any]:
    working = deepcopy(record or {})
    final_schedule_items = working.get(final_schedule_items_key) or []
    review_rows = working.get(review_rows_key) or []
    metadata = working.get(metadata_key) or {}

    builder_result = build_final_output_payload(
        final_schedule_items,
        review_rows=review_rows,
        metadata=metadata,
    )

    output_rows = builder_result.get('rows', [])
    stats = builder_result.get('stats', {})
    final_output = builder_result.get('final_output', {})

    working['final_output_builder'] = stats
    working['final_output_rows'] = output_rows
    working['final_output_row_count'] = len(output_rows)
    working['final_output_pending_count'] = int(stats.get('pending_rows', 0) or 0)
    working['quote_pack_payload'] = final_output
    working['quote_pack_summary'] = final_output.get('summary', {})
    working['quote_pack_total'] = final_output.get('summary', {}).get('grand_total')
    return working


if __name__ == '__main__':
    from pprint import pprint

    sample_items = [
        {
            'item_number': 1,
            'description': 'Stapler for office use | Uses 26/6 staples',
            'specification': 'Uses 26/6 staples',
            'unit': 'Each',
            'quantity': 100.0,
            'unit_price': 32.5,
            'line_total': 3250.0,
            'schedule_fill_status': 'filled',
            'pricing_status': 'priced',
            'pricing_source': 'item_override',
        },
        {
            'item_number': 2,
            'description': 'Plier stapler | Metal',
            'specification': 'Metal',
            'unit': 'Each',
            'quantity': 15.0,
            'unit_price': None,
            'line_total': None,
            'schedule_fill_status': 'pending_price',
            'pricing_status': 'pending_price',
            'pricing_source': 'none',
        },
    ]

    result = build_final_output_payload(
        sample_items,
        review_rows=[{'item_number': 35}],
        metadata={'vat_rate': 15.0, 'currency': 'ZAR', 'prices_include_vat': True},
    )
    pprint(result['rows'])
    pprint(result['final_output'])
    pprint(result['stats'])

