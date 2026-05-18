from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


DESCRIPTION_KEYS = (
    "description",
    "item_description",
    "details",
    "work_description",
    "activity",
    "service_description",
)

SPEC_KEYS = (
    "specification",
    "item_specification",
    "spec",
    "details_spec",
)

ITEM_NO_KEYS = ("item_no", "item", "no", "line_no", "item_number")
UNIT_KEYS = ("unit", "uom", "measure")
QTY_KEYS = ("qty", "quantity", "estimated_quantity")
PRICE_KEYS = ("unit_price", "rate", "price", "amount", "line_total", "total")

KNOWN_UNIT_PATTERNS = [
    r"each",
    r"box of \d+",
    r"pack of \d+",
    r"pkt of \d+[a-z]*",
    r"ream of \d+",
    r"set of \d+",
    r"pair",
    r"roll",
    r"tube",
    r"bottle",
    r"tin",
    r"carton",
    r"dozen",
]

UNIT_REGEX = re.compile(
    r"(?i)\b("
    + "|".join(KNOWN_UNIT_PATTERNS)
    + r")\b"
)

TRAILING_UNIT_QTY_REGEX = re.compile(
    r"(?is)^(?P<body>.*?)(?:\s+|\n+)(?P<unit>"
    + "|".join(KNOWN_UNIT_PATTERNS)
    + r")\s+(?P<qty>\d+(?:\.\d+)?)$"
)

TRAILING_QTY_ONLY_REGEX = re.compile(
    r"(?is)^(?P<body>.*?)(?:\s+|\n+)(?P<qty>\d+(?:\.\d+)?)$"
)

UNIT_INSIDE_TEXT_REGEX = re.compile(
    r"(?is)^(?P<body>.*?)(?:\s+|\n+)(?P<unit>"
    + "|".join(KNOWN_UNIT_PATTERNS)
    + r")$"
)

PRICE_NUMBER_REGEX = re.compile(r"^\d+(?:[ ,]\d{3})*(?:\.\d+)?$")


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _collapse(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean(value)).strip()


def _is_blank(value: Any) -> bool:
    return _collapse(value) == ""


def _parse_float(value: Any) -> Optional[float]:
    text = _collapse(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _first_key(row: Dict[str, Any], candidates: Tuple[str, ...]) -> Optional[str]:
    for key in candidates:
        if key in row:
            return key
    return None


def _get_desc_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, DESCRIPTION_KEYS)


def _get_spec_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, SPEC_KEYS)


def _get_unit_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, UNIT_KEYS)


def _get_qty_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, QTY_KEYS)


def _get_item_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, ITEM_NO_KEYS)


def _ensure_key(row: Dict[str, Any], candidates: Tuple[str, ...], default_key: str) -> str:
    key = _first_key(row, candidates)
    if key:
        return key
    row.setdefault(default_key, "")
    return default_key


def _join_text(a: Any, b: Any) -> str:
    a_text = _collapse(a)
    b_text = _collapse(b)
    if a_text and b_text:
        if b_text.lower() in a_text.lower():
            return a_text
        return f"{a_text} {b_text}".strip()
    return a_text or b_text


def _looks_like_unit(text: str) -> bool:
    return bool(UNIT_REGEX.search(_collapse(text)))


def _looks_like_qty(text: str) -> bool:
    return _parse_float(text) is not None


def _present_text(row: Dict[str, Any]) -> str:
    return " | ".join(_collapse(v) for v in row.values() if not _is_blank(v))


def _split_trailing_unit_qty(text: str) -> Tuple[str, Optional[str], Optional[float]]:
    raw = _collapse(text)
    if not raw:
        return "", None, None

    m = TRAILING_UNIT_QTY_REGEX.match(raw)
    if m:
        body = _collapse(m.group("body"))
        unit = _collapse(m.group("unit"))
        qty = _parse_float(m.group("qty"))
        return body, unit, qty

    return raw, None, None


def _split_trailing_unit_only(text: str) -> Tuple[str, Optional[str]]:
    raw = _collapse(text)
    if not raw:
        return "", None

    m = UNIT_INSIDE_TEXT_REGEX.match(raw)
    if m:
        body = _collapse(m.group("body"))
        unit = _collapse(m.group("unit"))
        return body, unit

    return raw, None


def _split_trailing_qty_only(text: str) -> Tuple[str, Optional[float]]:
    raw = _collapse(text)
    if not raw:
        return "", None

    m = TRAILING_QTY_ONLY_REGEX.match(raw)
    if not m:
        return raw, None

    body = _collapse(m.group("body"))
    qty = _parse_float(m.group("qty"))

    if qty is None:
        return raw, None

    # guard against eating dimensions/spec numbers like "297mm X 210mm"
    if re.search(r"(?i)\b(mm|cm|m|gsm|ml|l|kg|g)\b", body[-15:]):
        return raw, None

    # avoid splitting if the full text is just a small code fragment
    if len(body) < 3:
        return raw, None

    return body, qty


def _extract_unit_qty_from_text(text: str) -> Tuple[str, Optional[str], Optional[float]]:
    """
    Tries, in order:
    1. body + unit + qty
    2. body + unit
    3. body + qty
    """
    body, unit, qty = _split_trailing_unit_qty(text)
    if unit is not None or qty is not None:
        return body, unit, qty

    body2, unit2 = _split_trailing_unit_only(text)
    if unit2 is not None:
        return body2, unit2, None

    body3, qty3 = _split_trailing_qty_only(text)
    if qty3 is not None:
        return body3, None, qty3

    return _collapse(text), None, None


def _move_unit_qty_from_text_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(row)

    desc_key = _ensure_key(updated, DESCRIPTION_KEYS, "description")
    spec_key = _ensure_key(updated, SPEC_KEYS, "specification")
    unit_key = _ensure_key(updated, UNIT_KEYS, "unit")
    qty_key = _ensure_key(updated, QTY_KEYS, "quantity")

    desc_text = _collapse(updated.get(desc_key, ""))
    spec_text = _collapse(updated.get(spec_key, ""))
    current_unit = _collapse(updated.get(unit_key, ""))
    current_qty = _parse_float(updated.get(qty_key))

    changed = False

    # First try specification field because unit/qty often land there
    if spec_text and (not current_unit or current_qty is None):
        new_spec, found_unit, found_qty = _extract_unit_qty_from_text(spec_text)
        if found_unit and not current_unit:
            updated[unit_key] = found_unit
            current_unit = found_unit
            changed = True
        if found_qty is not None and current_qty is None:
            updated[qty_key] = found_qty
            current_qty = found_qty
            changed = True
        if new_spec != spec_text:
            updated[spec_key] = new_spec
            changed = True

    # Then try description field
    desc_text = _collapse(updated.get(desc_key, ""))
    if desc_text and (not current_unit or current_qty is None):
        new_desc, found_unit, found_qty = _extract_unit_qty_from_text(desc_text)
        if found_unit and not current_unit:
            updated[unit_key] = found_unit
            current_unit = found_unit
            changed = True
        if found_qty is not None and current_qty is None:
            updated[qty_key] = found_qty
            current_qty = found_qty
            changed = True
        if new_desc != desc_text:
            updated[desc_key] = new_desc
            changed = True

    # If spec is empty and description is too long, split a likely spec continuation
    desc_text = _collapse(updated.get(desc_key, ""))
    spec_text = _collapse(updated.get(spec_key, ""))

    if desc_text and not spec_text and len(desc_text) > 70:
        split_markers = [
            " uses ",
            " size ",
            " metal ",
            " printed ",
            " colour ",
            " color ",
            " hard cover ",
            " soft-feel ",
            " removable ",
            " adjustable ",
            " assorted ",
            " capacity ",
            " staples ",
            " punches ",
            " quarter bound ",
            " feint ruled ",
            " indexed ",
            " transparent ",
        ]
        lower_desc = f" {desc_text.lower()} "
        split_at = None
        for marker in split_markers:
            idx = lower_desc.find(marker)
            if idx > 12:
                split_at = idx - 1
                break

        if split_at:
            left = _collapse(desc_text[:split_at])
            right = _collapse(desc_text[split_at:])
            if left and right:
                updated[desc_key] = left
                updated[spec_key] = right
                changed = True

    return updated


def _promote_spec_to_desc_if_missing_desc(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(row)

    desc_key = _ensure_key(updated, DESCRIPTION_KEYS, "description")
    spec_key = _ensure_key(updated, SPEC_KEYS, "specification")

    desc_text = _collapse(updated.get(desc_key, ""))
    spec_text = _collapse(updated.get(spec_key, ""))

    if not desc_text and spec_text:
        updated[desc_key] = spec_text
        updated[spec_key] = ""
    return updated


def _repair_unit_qty_swaps(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(row)

    unit_key = _ensure_key(updated, UNIT_KEYS, "unit")
    qty_key = _ensure_key(updated, QTY_KEYS, "quantity")

    unit_text = _collapse(updated.get(unit_key, ""))
    qty_text = _collapse(updated.get(qty_key, ""))

    # quantity accidentally stored in unit
    if unit_text and _looks_like_qty(unit_text) and (not qty_text or not _looks_like_qty(qty_text)):
        updated[qty_key] = _parse_float(unit_text)
        updated[unit_key] = ""

    # unit accidentally stored in quantity field
    unit_text = _collapse(updated.get(unit_key, ""))
    qty_text = _collapse(updated.get(qty_key, ""))
    if qty_text and _looks_like_unit(qty_text) and not unit_text:
        updated[unit_key] = qty_text
        updated[qty_key] = ""

    return updated


def _normalize_numeric_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(row)

    for key in QTY_KEYS + PRICE_KEYS:
        if key in updated:
            parsed = _parse_float(updated.get(key))
            if parsed is not None:
                updated[key] = parsed

    return updated


def _realign_single_row(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(row)
    updated = _promote_spec_to_desc_if_missing_desc(updated)
    updated = _move_unit_qty_from_text_fields(updated)
    updated = _repair_unit_qty_swaps(updated)
    updated = _normalize_numeric_fields(updated)
    return updated


def realign_columns(
    rows: List[Dict[str, Any]],
    *,
    attach_debug: bool = False,
) -> Dict[str, Any]:
    repaired_rows: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []
    changed_rows = 0

    for idx, row in enumerate(rows):
        before = deepcopy(row)
        after = _realign_single_row(row)

        if before != after:
            changed_rows += 1
            if attach_debug:
                debug.append(
                    {
                        "row_index": idx,
                        "before": before,
                        "after": after,
                    }
                )

        repaired_rows.append(after)

    return {
        "rows": repaired_rows,
        "stats": {
            "input_rows": len(rows),
            "output_rows": len(repaired_rows),
            "changed_rows": changed_rows,
        },
        "debug": debug if attach_debug else [],
    }


def realign_columns_for_table(
    table_payload: Dict[str, Any],
    *,
    rows_key: str = "rows",
    attach_debug: bool = False,
) -> Dict[str, Any]:
    payload = deepcopy(table_payload or {})
    rows = payload.get(rows_key, [])
    result = realign_columns(rows, attach_debug=attach_debug)
    payload[rows_key] = result["rows"]
    payload["column_realignment"] = result["stats"]
    if attach_debug:
        payload["column_realignment_debug"] = result["debug"]
    return payload


if __name__ == "__main__":
    from pprint import pprint

    rows = [
        {
            "item_number": 36,
            "description": "Board Lever Arch File A4 – 350mm X 280mm 80mm spine No rado Box of 10 10",
            "specification": "",
            "unit": "",
            "quantity": None,
        },
        {
            "item_number": 41,
            "description": "Create a Cover Files 2D-ring 25mm • Clear pocket front & spine • Three-piece cover construction • Transparent, anti-reflective pockets on the front cover and spine Each 25",
            "specification": "",
            "unit": "",
            "quantity": None,
        },
        {
            "item_number": 48,
            "description": "Suspension File Coated Metal Rails Colour Tabs Included Mylar Protection Strip top & bottom Foolscap Various colours – pack of 25 per colour Pack of 25 (per colour) 5",
            "specification": "",
            "unit": "",
            "quantity": None,
        },
    ]

    result = realign_columns(rows, attach_debug=True)
    pprint(result["rows"])
    pprint(result["stats"])
