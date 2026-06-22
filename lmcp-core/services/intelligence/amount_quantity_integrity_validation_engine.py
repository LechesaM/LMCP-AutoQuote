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

ITEM_KEYS = ("item_no", "item", "no", "line_no", "item_number")
UNIT_KEYS = ("unit", "uom", "measure")
QTY_KEYS = ("qty", "quantity", "estimated_quantity")
PRICE_KEYS = ("unit_price", "rate", "price")
TOTAL_KEYS = ("line_total", "amount", "total")

UNIT_PATTERN = re.compile(
    r"(?i)\b(each|box of \d+|pack of \d+|pkt of \d+[a-z]*|ream of \d+|set of \d+|pair|roll|tube|bottle|tin|carton|dozen)\b"
)

DIMENSION_TAIL_PATTERN = re.compile(
    r"(?i)(\d+(?:\.\d+)?)\s*(mm|cm|m|gsm|ml|l|kg|g|m2|m3)\b"
)

TRAILING_NUMBER_PATTERN = re.compile(r"(?is)\b(\d+(?:\.\d+)?)\s*$")

TRAILING_UNIT_QTY_PATTERN = re.compile(
    r"(?is)\b"
    r"(each|box of \d+|pack of \d+|pkt of \d+[a-z]*|ream of \d+|set of \d+|pair|roll|tube|bottle|tin|carton|dozen)"
    r"(?:\s*\([^)]*\))?"
    r"\s+(\d+(?:\.\d+)?)\s*$"
)


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


def _ensure_key(row: Dict[str, Any], candidates: Tuple[str, ...], default_key: str) -> str:
    key = _first_key(row, candidates)
    if key:
        return key
    row.setdefault(default_key, "")
    return default_key


def _desc_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, DESCRIPTION_KEYS, "description")


def _spec_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, SPEC_KEYS, "specification")


def _unit_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, UNIT_KEYS, "unit")


def _qty_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, QTY_KEYS, "quantity")


def _price_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, PRICE_KEYS, "unit_price")


def _total_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, TOTAL_KEYS, "line_total")


def _item_key(row: Dict[str, Any]) -> str:
    return _ensure_key(row, ITEM_KEYS, "item_number")


def _looks_like_unit(text: str) -> bool:
    return bool(UNIT_PATTERN.search(_collapse(text)))


def _has_dimension_tail(text: str) -> bool:
    return bool(DIMENSION_TAIL_PATTERN.search(_collapse(text)))


def _extract_trailing_number(text: str) -> Optional[float]:
    raw = _collapse(text)
    if not raw:
        return None
    m = TRAILING_NUMBER_PATTERN.search(raw)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _has_trailing_unit_qty(text: str) -> bool:
    return bool(TRAILING_UNIT_QTY_PATTERN.search(_collapse(text)))


def _contains_unit_pattern(text: str) -> bool:
    return bool(UNIT_PATTERN.search(_collapse(text)))


def _safe_multiply(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    try:
        return round(float(a) * float(b), 2)
    except Exception:
        return None


def _approx_equal(a: Optional[float], b: Optional[float], tolerance: float = 0.05) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


def _build_issue(code: str, severity: str, message: str) -> Dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
    }


def _validate_single_row(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(row)

    item_key = _item_key(updated)
    desc_key = _desc_key(updated)
    spec_key = _spec_key(updated)
    unit_key = _unit_key(updated)
    qty_key = _qty_key(updated)
    price_key = _price_key(updated)
    total_key = _total_key(updated)

    desc = _collapse(updated.get(desc_key))
    spec = _collapse(updated.get(spec_key))
    unit = _collapse(updated.get(unit_key))
    qty = _parse_float(updated.get(qty_key))
    unit_price = _parse_float(updated.get(price_key))
    line_total = _parse_float(updated.get(total_key))

    issues: List[Dict[str, str]] = []
    flags: List[str] = []

    if not desc:
        issues.append(_build_issue("missing_description", "error", "Row has no description."))
        flags.append("missing_description")

    if unit and not _looks_like_unit(unit):
        issues.append(_build_issue("unknown_unit_pattern", "warning", f"Unit does not match expected patterns: {unit}"))
        flags.append("unknown_unit_pattern")

    if unit and qty is None:
        issues.append(_build_issue("unit_without_quantity", "warning", "Row has a unit but no quantity."))
        flags.append("unit_without_quantity")

    if not unit and qty is not None:
        issues.append(_build_issue("quantity_without_unit", "warning", "Row has a quantity but no unit."))
        flags.append("quantity_without_unit")

    if qty is not None and qty <= 0:
        issues.append(_build_issue("non_positive_quantity", "error", "Quantity must be greater than zero."))
        flags.append("non_positive_quantity")

    if unit_price is not None and unit_price < 0:
        issues.append(_build_issue("negative_unit_price", "error", "Unit price cannot be negative."))
        flags.append("negative_unit_price")

    if line_total is not None and line_total < 0:
        issues.append(_build_issue("negative_line_total", "error", "Line total cannot be negative."))
        flags.append("negative_line_total")

    if qty is not None and unit_price is not None and line_total is not None:
        expected_total = _safe_multiply(qty, unit_price)
        if expected_total is not None and not _approx_equal(expected_total, line_total, tolerance=0.1):
            issues.append(
                _build_issue(
                    "line_total_mismatch",
                    "warning",
                    f"Line total does not match quantity × unit price. Expected about {expected_total}, got {line_total}.",
                )
            )
            flags.append("line_total_mismatch")

    if desc:
        trailing_number = _extract_trailing_number(desc)
        if trailing_number is not None and qty is not None:
            if not _has_dimension_tail(desc) and not _approx_equal(trailing_number, qty, tolerance=0.0001):
                issues.append(
                    _build_issue(
                        "possible_qty_still_in_description",
                        "warning",
                        "Description still ends with a numeric value that may be a misplaced quantity.",
                    )
                )
                flags.append("possible_qty_still_in_description")

    if spec:
        trailing_number = _extract_trailing_number(spec)
        if trailing_number is not None and qty is not None:
            if not _has_dimension_tail(spec) and not _approx_equal(trailing_number, qty, tolerance=0.0001):
                issues.append(
                    _build_issue(
                        "possible_qty_still_in_specification",
                        "warning",
                        "Specification still ends with a numeric value that may be a misplaced quantity.",
                    )
                )
                flags.append("possible_qty_still_in_specification")

    if desc and _has_trailing_unit_qty(desc):
        issues.append(
            _build_issue(
                "unit_qty_still_in_description",
                "warning",
                "Description appears to still contain trailing unit/quantity text.",
            )
        )
        flags.append("unit_qty_still_in_description")

    if spec and _has_trailing_unit_qty(spec):
        issues.append(
            _build_issue(
                "unit_qty_still_in_specification",
                "warning",
                "Specification appears to still contain trailing unit/quantity text.",
            )
        )
        flags.append("unit_qty_still_in_specification")

    if not unit and qty is None and spec and _contains_unit_pattern(spec):
        issues.append(
            _build_issue(
                "possible_unit_qty_still_buried_in_specification",
                "warning",
                "Specification still contains a unit-like pattern while unit/quantity fields are empty.",
            )
        )
        flags.append("possible_unit_qty_still_buried_in_specification")

    if not unit and qty is None and desc and _contains_unit_pattern(desc):
        issues.append(
            _build_issue(
                "possible_unit_qty_still_buried_in_description",
                "warning",
                "Description still contains a unit-like pattern while unit/quantity fields are empty.",
            )
        )
        flags.append("possible_unit_qty_still_buried_in_description")

    if not desc and spec:
        issues.append(
            _build_issue(
                "spec_without_description",
                "warning",
                "Specification exists but description is empty.",
            )
        )
        flags.append("spec_without_description")

    if unit and qty is not None and desc:
        if desc.lower() in {"pages", "page", "copies", "copy"}:
            issues.append(
                _build_issue(
                    "description_too_thin",
                    "warning",
                    "Description looks too thin and may still be partially misaligned.",
                )
            )
            flags.append("description_too_thin")

    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    if error_count > 0:
        integrity_status = "error"
    elif warning_count > 0:
        integrity_status = "warning"
    else:
        integrity_status = "valid"

    updated["integrity_validation"] = {
        "status": integrity_status,
        "error_count": error_count,
        "warning_count": warning_count,
        "flags": sorted(set(flags)),
        "issues": issues,
    }

    return updated


def validate_amount_quantity_integrity(
    rows: List[Dict[str, Any]],
    *,
    attach_debug: bool = False,
) -> Dict[str, Any]:
    validated_rows: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []

    valid_rows = 0
    warning_rows = 0
    error_rows = 0

    for idx, row in enumerate(rows):
        before = deepcopy(row)
        after = _validate_single_row(row)

        status = after.get("integrity_validation", {}).get("status", "warning")
        if status == "valid":
            valid_rows += 1
        elif status == "warning":
            warning_rows += 1
        else:
            error_rows += 1

        if attach_debug:
            debug.append(
                {
                    "row_index": idx,
                    "before": before,
                    "after": after,
                }
            )

        validated_rows.append(after)

    return {
        "rows": validated_rows,
        "stats": {
            "input_rows": len(rows),
            "output_rows": len(validated_rows),
            "valid_rows": valid_rows,
            "warning_rows": warning_rows,
            "error_rows": error_rows,
        },
        "debug": debug if attach_debug else [],
    }


def validate_amount_quantity_integrity_for_table(
    table_payload: Dict[str, Any],
    *,
    rows_key: str = "rows",
    attach_debug: bool = False,
) -> Dict[str, Any]:
    payload = deepcopy(table_payload or {})
    rows = payload.get(rows_key, [])
    result = validate_amount_quantity_integrity(rows, attach_debug=attach_debug)
    payload[rows_key] = result["rows"]
    payload["amount_quantity_integrity_validation"] = result["stats"]
    if attach_debug:
        payload["amount_quantity_integrity_validation_debug"] = result["debug"]
    return payload


if __name__ == "__main__":
    from pprint import pprint

    rows = [
        {
            "item_number": 36,
            "description": "Board Lever Arch File A4 – 350mm X 280mm 80mm spine No rado",
            "specification": "",
            "unit": "Box of 10",
            "quantity": 10.0,
            "unit_price": 25.0,
            "line_total": 250.0,
        },
        {
            "item_number": 41,
            "description": "Create a Cover Files 2D-ring 25mm Clear pocket front & spine Each 25",
            "specification": "",
            "unit": "",
            "quantity": None,
            "unit_price": None,
            "line_total": None,
        },
        {
            "item_number": 48,
            "description": "Suspension File Coated Metal Rails Colour Tabs Included",
            "specification": "Pack of 25 (per colour) 5",
            "unit": "",
            "quantity": None,
            "unit_price": None,
            "line_total": None,
        },
    ]

    result = validate_amount_quantity_integrity(rows, attach_debug=True)
    pprint(result["rows"])
    pprint(result["stats"])
