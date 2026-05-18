from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


DESCRIPTION_KEYS = (
    "description",
    "item_description",
    "specification",
    "details",
    "work_description",
    "activity",
    "service_description",
)

ITEM_NO_KEYS = ("item_no", "item", "no", "line_no", "item_number")
UNIT_KEYS = ("unit", "uom", "measure")
QTY_KEYS = ("qty", "quantity", "estimated_quantity")
PRICE_KEYS = ("unit_price", "rate", "price", "amount", "line_total", "total")

HEADER_WORDS = {
    "item",
    "number",
    "description",
    "specification",
    "unit",
    "measurement",
    "quantity",
    "price",
    "amount",
    "total",
    "vat",
}

CONTINUATION_HINTS = (
    "continued",
    "cont.",
    "cont",
    "carry forward",
    "carried forward",
    "brought forward",
    "from previous page",
    "continued on next page",
)

TOTAL_HINTS = (
    "subtotal",
    "sub-total",
    "total",
    "grand total",
    "vat",
    "carried forward",
    "brought forward",
    "sum carried forward",
    "page total",
)

SPEC_FRAGMENT_STARTS = (
    "pages",
    "page",
    "copies",
    "copy",
    "bound",
    "printed",
    "design",
    "layout",
    "size",
    "part",
    "dispatch",
    "finishing",
    "pre-press",
    "paper",
)

UNIT_PATTERNS = (
    "each",
    "box of",
    "pack of",
    "pkt of",
    "ream",
    "set",
    "pair",
    "roll",
    "tube",
    "bottle",
)

NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
INTEGER_RE = re.compile(r"^\d+$")


@dataclass
class MergeDecision:
    should_merge: bool
    score: int
    reason: str


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _collapse(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean(value)).strip()


def _lower(value: Any) -> str:
    return _collapse(value).lower()


def _is_blank(value: Any) -> bool:
    return _collapse(value) == ""


def _first_key(row: Dict[str, Any], candidates: Tuple[str, ...]) -> Optional[str]:
    for key in candidates:
        if key in row:
            return key
    return None


def _get_item_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, ITEM_NO_KEYS)


def _get_desc_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, DESCRIPTION_KEYS)


def _get_unit_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, UNIT_KEYS)


def _get_qty_key(row: Dict[str, Any]) -> Optional[str]:
    return _first_key(row, QTY_KEYS)


def _present_values(row: Dict[str, Any]) -> List[str]:
    return [_collapse(v) for v in row.values() if not _is_blank(v)]


def _row_text(row: Dict[str, Any]) -> str:
    return " | ".join(_present_values(row))


def _row_numeric_count(row: Dict[str, Any]) -> int:
    count = 0
    for v in row.values():
        text = _collapse(v).replace(",", "")
        if NUMBER_RE.match(text):
            count += 1
    return count


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
    if INTEGER_RE.match(text):
        try:
            return int(text)
        except Exception:
            return None
    return None


def _safe_item_no(row: Dict[str, Any]) -> Optional[int]:
    item_key = _get_item_key(row)
    if not item_key:
        return None
    return _parse_int(row.get(item_key))


def _desc_text(row: Dict[str, Any]) -> str:
    desc_key = _get_desc_key(row)
    return _collapse(row.get(desc_key, "")) if desc_key else ""


def _unit_text(row: Dict[str, Any]) -> str:
    unit_key = _get_unit_key(row)
    return _collapse(row.get(unit_key, "")) if unit_key else ""


def _qty_value(row: Dict[str, Any]) -> Optional[float]:
    qty_key = _get_qty_key(row)
    if not qty_key:
        return None
    return _parse_float(row.get(qty_key))


def _is_header_like(row: Dict[str, Any]) -> bool:
    tokens = []
    for val in _present_values(row):
        tokens.extend(re.findall(r"[A-Za-z]+", val.lower()))
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in HEADER_WORDS)
    return hits >= 3 and hits >= len(tokens) // 2


def _is_total_like(row: Dict[str, Any]) -> bool:
    text = _lower(_row_text(row))
    return any(h in text for h in TOTAL_HINTS)


def _has_continuation_hint(row: Dict[str, Any]) -> bool:
    text = _lower(_row_text(row))
    return any(h in text for h in CONTINUATION_HINTS)


def _looks_like_unit(text: str) -> bool:
    t = _lower(text)
    return any(t == p or t.startswith(p + " ") for p in UNIT_PATTERNS)


def _looks_like_quantity_only_row(row: Dict[str, Any]) -> bool:
    desc = _desc_text(row)
    unit = _unit_text(row)
    qty = _qty_value(row)
    item_no = _safe_item_no(row)

    if qty is None:
        return False

    if not unit or not _looks_like_unit(unit):
        return False

    desc_l = desc.lower()
    if re.fullmatch(r"\d+\s+pages?", desc_l):
        return True
    if re.fullmatch(r"\d+\s+copies?", desc_l):
        return True

    if item_no is not None and desc_l in {"pages", "page", "copies", "copy"}:
        return True

    return False


def _looks_like_spec_fragment_row(row: Dict[str, Any]) -> bool:
    item_no = _safe_item_no(row)
    desc = _desc_text(row).lower()
    unit = _unit_text(row).lower()
    qty = _qty_value(row)

    if _is_total_like(row) or _is_header_like(row):
        return False

    if item_no is None and desc and _row_numeric_count(row) <= 1:
        return True

    if item_no is not None:
        if desc in {"pages", "page", "copies", "copy"}:
            return True
        if any(desc.startswith(prefix) for prefix in SPEC_FRAGMENT_STARTS):
            return True
        if unit and _looks_like_unit(unit) and qty is not None and item_no >= 100:
            return True

    return False


def _is_probable_new_real_item(prev_row: Dict[str, Any], curr_row: Dict[str, Any]) -> bool:
    prev_item = _safe_item_no(prev_row)
    curr_item = _safe_item_no(curr_row)
    curr_desc = _desc_text(curr_row)
    curr_unit = _unit_text(curr_row)
    curr_qty = _qty_value(curr_row)

    if curr_item is None:
        return False

    if curr_desc and len(curr_desc) >= 4:
        if curr_desc.lower() in {"pages", "page", "copies", "copy"}:
            return False
        if any(curr_desc.lower().startswith(prefix) for prefix in SPEC_FRAGMENT_STARTS):
            return False

        if prev_item is not None and 1 <= curr_item - prev_item <= 5:
            return True

        if curr_item < 100 and (curr_unit or curr_qty is not None):
            return True

    return False


def _normalize_continuation_text(row: Dict[str, Any]) -> str:
    """
    Rebuild text for fake split rows like:
        item_number=192, description="Pages"
    into:
        "192 Pages"
    """
    item_no = _safe_item_no(row)
    desc = _desc_text(row)

    if item_no is not None and _looks_like_spec_fragment_row(row):
        if desc:
            return f"{item_no} {desc}".strip()
        return str(item_no)

    return desc


def _join_text(a: Any, b: Any) -> str:
    a_text = _collapse(a)
    b_text = _collapse(b)
    if a_text and b_text:
        if b_text.lower() in a_text.lower():
            return a_text
        return f"{a_text} {b_text}".strip()
    return a_text or b_text


def _best_value(prev_val: Any, curr_val: Any) -> Any:
    p = _collapse(prev_val)
    c = _collapse(curr_val)
    if not p:
        return curr_val
    if not c:
        return prev_val
    if p.lower() == c.lower():
        return prev_val
    return curr_val if len(c) > len(p) else prev_val


def _merge_rows(prev_row: Dict[str, Any], curr_row: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(prev_row)
    all_keys = list(dict.fromkeys(list(prev_row.keys()) + list(curr_row.keys())))

    normalized_curr_desc = _normalize_continuation_text(curr_row)

    for key in all_keys:
        p = prev_row.get(key, "")
        c = curr_row.get(key, "")

        if key in DESCRIPTION_KEYS:
            merged[key] = _join_text(p, normalized_curr_desc if key == _get_desc_key(curr_row) else c)
            continue

        if key in ITEM_NO_KEYS:
            merged[key] = p if not _is_blank(p) else c
            continue

        if key in UNIT_KEYS:
            merged[key] = p if not _is_blank(p) else c
            continue

        if key in QTY_KEYS or key in PRICE_KEYS:
            merged[key] = p if not _is_blank(p) else c
            continue

        if _is_blank(p):
            merged[key] = c
        elif _is_blank(c):
            merged[key] = p
        else:
            merged[key] = _best_value(p, c)

    return merged


def _continuation_merge_decision(prev_row: Dict[str, Any], curr_row: Dict[str, Any]) -> MergeDecision:
    if not prev_row or not curr_row:
        return MergeDecision(False, 0, "missing-row")

    if _is_header_like(curr_row):
        return MergeDecision(False, -100, "header-row")

    if _is_total_like(curr_row) or _is_total_like(prev_row):
        return MergeDecision(False, -100, "total-row")

    score = 0
    reasons: List[str] = []

    if _looks_like_quantity_only_row(curr_row):
        score += 90
        reasons.append("quantity-only-fragment")

    if _looks_like_spec_fragment_row(curr_row):
        score += 60
        reasons.append("spec-fragment")

    if _has_continuation_hint(curr_row):
        score += 35
        reasons.append("continuation-hint")

    curr_item = _safe_item_no(curr_row)
    prev_item = _safe_item_no(prev_row)

    if _is_probable_new_real_item(prev_row, curr_row):
        score -= 120
        reasons.append("real-new-item")

    if curr_item is not None and prev_item is not None:
        if curr_item > prev_item + 20 and _looks_like_spec_fragment_row(curr_row):
            score += 40
            reasons.append("suspicious-item-jump")

    prev_desc = _desc_text(prev_row)
    curr_desc = _desc_text(curr_row)

    if prev_desc and curr_desc and len(curr_desc) < 220:
        score += 10
        reasons.append("desc-carryover")

    if _row_numeric_count(curr_row) <= 1:
        score += 10
        reasons.append("weak-numeric-structure")

    return MergeDecision(score >= 40, score, ",".join(reasons) if reasons else "no-signal")


def repair_continuation_merges(
    rows: List[Dict[str, Any]],
    *,
    max_passes: int = 4,
    attach_debug: bool = False,
) -> Dict[str, Any]:
    working = [deepcopy(r) for r in rows if isinstance(r, dict)]
    debug: List[Dict[str, Any]] = []
    merged_count = 0
    removed_headers = 0

    filtered = []
    for row in working:
        if _is_header_like(row):
            removed_headers += 1
            continue
        filtered.append(row)
    working = filtered

    for pass_no in range(1, max_passes + 1):
        if len(working) <= 1:
            break

        changed = False
        repaired: List[Dict[str, Any]] = []

        for row in working:
            if not repaired:
                repaired.append(row)
                continue

            prev = repaired[-1]
            decision = _continuation_merge_decision(prev, row)

            if decision.should_merge:
                merged = _merge_rows(prev, row)
                repaired[-1] = merged
                merged_count += 1
                changed = True
                if attach_debug:
                    debug.append(
                        {
                            "pass": pass_no,
                            "action": "merge",
                            "score": decision.score,
                            "reason": decision.reason,
                            "prev_before": prev,
                            "curr_before": row,
                            "merged_after": merged,
                        }
                    )
            else:
                repaired.append(row)
                if attach_debug:
                    debug.append(
                        {
                            "pass": pass_no,
                            "action": "keep",
                            "score": decision.score,
                            "reason": decision.reason,
                            "row": row,
                        }
                    )

        working = repaired

        if not changed:
            break

    return {
        "rows": working,
        "stats": {
            "input_rows": len(rows),
            "merged_rows": merged_count,
            "output_rows": len(working),
            "passes": max_passes,
            "removed_header_rows": removed_headers,
        },
        "debug": debug if attach_debug else [],
    }


def repair_continuation_merges_for_table(
    table_payload: Dict[str, Any],
    *,
    rows_key: str = "rows",
    attach_debug: bool = False,
) -> Dict[str, Any]:
    payload = deepcopy(table_payload or {})
    rows = payload.get(rows_key, [])
    result = repair_continuation_merges(rows, attach_debug=attach_debug)
    payload[rows_key] = result["rows"]
    payload["continuation_merge_repair"] = result["stats"]
    if attach_debug:
        payload["continuation_merge_repair_debug"] = result["debug"]
    return payload


if __name__ == "__main__":
    from pprint import pprint

    rows = [
        {"item_number": 30, "description": "Visitors Book Printed full bound A4 297mm X 210mm", "unit": "", "quantity": None},
        {"item_number": 192, "description": "Pages", "unit": "Each", "quantity": 20},
        {"item_number": 31, "description": "Telephone Message Book 24mm X 333mm", "unit": "", "quantity": None},
        {"item_number": 150, "description": "pages", "unit": "Each", "quantity": 5},
    ]

    result = repair_continuation_merges(rows, attach_debug=True)
    pprint(result["rows"])
    pprint(result["stats"])
