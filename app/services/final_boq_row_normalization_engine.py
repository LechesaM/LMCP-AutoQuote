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
SOURCE_LINE_KEYS = ("source_line", "raw_line", "raw_text", "source_text")
CONFIDENCE_KEYS = ("confidence",)
VALIDATION_KEYS = ("integrity_validation",)

VALID_STATUSES = {"valid", "warning", "error"}


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


def _parse_int(value: Any) -> Optional[int]:
    text = _collapse(value)
    if re.fullmatch(r"\d+", text):
        try:
            return int(text)
        except Exception:
            return None
    return None


def _first_existing_key(row: Dict[str, Any], candidates: Tuple[str, ...]) -> Optional[str]:
    for key in candidates:
        if key in row:
            return key
    return None


def _pick_text(row: Dict[str, Any], candidates: Tuple[str, ...]) -> str:
    key = _first_existing_key(row, candidates)
    if not key:
        return ""
    return _collapse(row.get(key, ""))


def _pick_float(row: Dict[str, Any], candidates: Tuple[str, ...]) -> Optional[float]:
    key = _first_existing_key(row, candidates)
    if not key:
        return None
    return _parse_float(row.get(key))


def _pick_item_number(row: Dict[str, Any], candidates: Tuple[str, ...]) -> Optional[int]:
    key = _first_existing_key(row, candidates)
    if not key:
        return None
    raw = row.get(key)
    parsed_int = _parse_int(raw)
    if parsed_int is not None:
        return parsed_int

    text = _collapse(raw)
    m = re.match(r"^(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _compact_text_fields(description: str, specification: str) -> Tuple[str, str]:
    """
    Remove duplication between description and specification.
    """
    desc = _collapse(description)
    spec = _collapse(specification)

    if desc and spec:
        if spec.lower() in desc.lower():
            spec = ""
        elif desc.lower() in spec.lower() and len(spec) > len(desc):
            # keep longer text as specification only when description is too duplicated
            pass

    return desc, spec


def _normalize_confidence(value: Any) -> str:
    text = _collapse(value).lower()
    if text in {"high", "medium", "low"}:
        return text
    if not text:
        return "medium"
    return text


def _normalize_validation(validation: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(validation)

    status = _collapse(payload.get("status", "warning")).lower()
    if status not in VALID_STATUSES:
        status = "warning"

    flags = sorted({str(x).strip() for x in _safe_list(payload.get("flags", [])) if str(x).strip()})

    issues = []
    for issue in _safe_list(payload.get("issues", [])):
        item = _safe_dict(issue)
        code = _collapse(item.get("code"))
        severity = _collapse(item.get("severity")).lower() or "warning"
        message = _collapse(item.get("message"))
        if not code and not message:
            continue
        issues.append(
            {
                "code": code,
                "severity": severity if severity in {"warning", "error", "info"} else "warning",
                "message": message,
            }
        )

    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    # fallback to provided counts if issues absent
    if not issues:
        provided_error_count = payload.get("error_count")
        provided_warning_count = payload.get("warning_count")
        try:
            error_count = int(provided_error_count or 0)
        except Exception:
            error_count = 0
        try:
            warning_count = int(provided_warning_count or 0)
        except Exception:
            warning_count = 0

    if error_count > 0:
        status = "error"
    elif warning_count > 0 and status == "valid":
        status = "warning"

    return {
        "status": status,
        "error_count": error_count,
        "warning_count": warning_count,
        "flags": flags,
        "issues": issues,
    }


def _compute_row_readiness(
    *,
    description: str,
    unit: str,
    quantity: Optional[float],
    validation_status: str,
) -> str:
    """
    Ready states:
    - ready: row can be priced/filled now
    - needs_review: row exists but needs human or further repair
    - unusable: row is too incomplete/broken
    """
    if validation_status == "error":
        return "unusable"

    if not description:
        return "unusable"

    if unit and quantity is not None and validation_status == "valid":
        return "ready"

    if validation_status == "warning":
        return "needs_review"

    if unit and quantity is not None:
        return "ready"

    return "needs_review"


def _normalize_single_row(
    row: Dict[str, Any],
    *,
    include_debug_meta: bool = False,
    row_index: Optional[int] = None,
) -> Dict[str, Any]:
    source = deepcopy(row)

    item_number = _pick_item_number(source, ITEM_KEYS)
    description = _pick_text(source, DESCRIPTION_KEYS)
    specification = _pick_text(source, SPEC_KEYS)
    unit = _pick_text(source, UNIT_KEYS)
    quantity = _pick_float(source, QTY_KEYS)
    unit_price = _pick_float(source, PRICE_KEYS)
    line_total = _pick_float(source, TOTAL_KEYS)
    source_line = _pick_text(source, SOURCE_LINE_KEYS)
    confidence = _normalize_confidence(_pick_text(source, CONFIDENCE_KEYS))

    validation = _normalize_validation(source.get("integrity_validation", {}))
    description, specification = _compact_text_fields(description, specification)

    row_ready_status = _compute_row_readiness(
        description=description,
        unit=unit,
        quantity=quantity,
        validation_status=validation["status"],
    )

    normalized: Dict[str, Any] = {
        "item_number": item_number,
        "description": description,
        "specification": specification,
        "unit": unit,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": line_total,
        "confidence": confidence,
        "integrity_status": validation["status"],
        "integrity_error_count": validation["error_count"],
        "integrity_warning_count": validation["warning_count"],
        "integrity_flags": validation["flags"],
        "row_ready_status": row_ready_status,
        "source_line": source_line,
    }

    if include_debug_meta:
        normalized["meta"] = {
            "row_index": row_index,
            "integrity_issues": validation["issues"],
            "source_keys": sorted(list(source.keys())),
            "original_row": source,
        }

    return normalized


def normalize_boq_rows(
    rows: List[Dict[str, Any]],
    *,
    include_debug_meta: bool = False,
    drop_empty_rows: bool = True,
) -> Dict[str, Any]:
    normalized_rows: List[Dict[str, Any]] = []

    ready_rows = 0
    needs_review_rows = 0
    unusable_rows = 0
    dropped_rows = 0

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            dropped_rows += 1
            continue

        normalized = _normalize_single_row(
            row,
            include_debug_meta=include_debug_meta,
            row_index=idx,
        )

        has_any_content = any(
            [
                normalized.get("item_number") is not None,
                bool(normalized.get("description")),
                bool(normalized.get("specification")),
                bool(normalized.get("unit")),
                normalized.get("quantity") is not None,
                normalized.get("unit_price") is not None,
                normalized.get("line_total") is not None,
            ]
        )

        if drop_empty_rows and not has_any_content:
            dropped_rows += 1
            continue

        status = normalized.get("row_ready_status")
        if status == "ready":
            ready_rows += 1
        elif status == "needs_review":
            needs_review_rows += 1
        else:
            unusable_rows += 1

        normalized_rows.append(normalized)

    return {
        "rows": normalized_rows,
        "stats": {
            "input_rows": len(rows),
            "output_rows": len(normalized_rows),
            "ready_rows": ready_rows,
            "needs_review_rows": needs_review_rows,
            "unusable_rows": unusable_rows,
            "dropped_rows": dropped_rows,
        },
    }


def normalize_boq_rows_for_table(
    table_payload: Dict[str, Any],
    *,
    rows_key: str = "rows",
    include_debug_meta: bool = False,
    drop_empty_rows: bool = True,
) -> Dict[str, Any]:
    payload = deepcopy(table_payload or {})
    rows = payload.get(rows_key, [])

    result = normalize_boq_rows(
        rows,
        include_debug_meta=include_debug_meta,
        drop_empty_rows=drop_empty_rows,
    )

    payload[rows_key] = result["rows"]
    payload["final_boq_row_normalization"] = result["stats"]
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
            "confidence": "medium",
            "integrity_validation": {
                "status": "valid",
                "error_count": 0,
                "warning_count": 0,
                "flags": [],
                "issues": [],
            },
        },
        {
            "item_number": 41,
            "description": "Create a Cover Files 2D-ring 25mm Clear pocket front & spine Each 25",
            "specification": "",
            "unit": "",
            "quantity": None,
            "unit_price": None,
            "line_total": None,
            "confidence": "medium",
            "integrity_validation": {
                "status": "warning",
                "error_count": 0,
                "warning_count": 1,
                "flags": ["unit_qty_still_in_description"],
                "issues": [
                    {
                        "code": "unit_qty_still_in_description",
                        "severity": "warning",
                        "message": "Description appears to still contain trailing unit/quantity text.",
                    }
                ],
            },
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
            "integrity_validation": {
                "status": "warning",
                "error_count": 0,
                "warning_count": 2,
                "flags": [
                    "possible_unit_qty_still_buried_in_specification",
                    "unit_qty_still_in_specification",
                ],
                "issues": [
                    {
                        "code": "possible_unit_qty_still_buried_in_specification",
                        "severity": "warning",
                        "message": "Specification still contains a unit-like pattern while unit/quantity fields are empty.",
                    },
                    {
                        "code": "unit_qty_still_in_specification",
                        "severity": "warning",
                        "message": "Specification appears to still contain trailing unit/quantity text.",
                    },
                ],
            },
        },
        {
            "item_number": 99,
            "description": "",
            "specification": "",
            "unit": "",
            "quantity": None,
            "unit_price": None,
            "line_total": None,
            "confidence": "",
            "integrity_validation": {
                "status": "error",
                "error_count": 1,
                "warning_count": 0,
                "flags": ["missing_description"],
                "issues": [
                    {
                        "code": "missing_description",
                        "severity": "error",
                        "message": "Row has no description.",
                    }
                ],
            },
        },
    ]

    result = normalize_boq_rows(rows, include_debug_meta=True)
    pprint(result["rows"])
    pprint(result["stats"])
