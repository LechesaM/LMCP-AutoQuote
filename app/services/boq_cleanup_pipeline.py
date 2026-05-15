from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from app.services.amount_quantity_integrity_validation_engine import (
    validate_amount_quantity_integrity,
)
from app.services.column_realignment_engine import realign_columns
from app.services.continuation_merge_repair_engine import repair_continuation_merges
from app.services.final_boq_row_normalization_engine import normalize_boq_rows


def _safe_rows(rows: Any) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [deepcopy(r) for r in rows if isinstance(r, dict)]


def run_boq_cleanup_pipeline(
    rows: List[Dict[str, Any]],
    *,
    attach_debug: bool = False,
    include_debug_meta: bool = False,
    drop_empty_rows: bool = True,
) -> Dict[str, Any]:
    working_rows = _safe_rows(rows)

    merge_result = repair_continuation_merges(
        working_rows,
        attach_debug=attach_debug,
    )
    merged_rows = merge_result.get("rows", [])

    realign_result = realign_columns(
        merged_rows,
        attach_debug=attach_debug,
    )
    realigned_rows = realign_result.get("rows", [])

    validation_result = validate_amount_quantity_integrity(
        realigned_rows,
        attach_debug=attach_debug,
    )
    validated_rows = validation_result.get("rows", [])

    normalization_result = normalize_boq_rows(
        validated_rows,
        include_debug_meta=include_debug_meta,
        drop_empty_rows=drop_empty_rows,
    )
    normalized_rows = normalization_result.get("rows", [])

    result: Dict[str, Any] = {
        "rows": normalized_rows,
        "stats": {
            "input_rows": len(working_rows),
            "continuation_merge": merge_result.get("stats", {}),
            "column_realignment": realign_result.get("stats", {}),
            "integrity_validation": validation_result.get("stats", {}),
            "final_normalization": normalization_result.get("stats", {}),
            "output_rows": len(normalized_rows),
        },
    }

    if attach_debug:
        result["debug"] = {
            "continuation_merge": merge_result.get("debug", []),
            "column_realignment": realign_result.get("debug", []),
            "integrity_validation": validation_result.get("debug", []),
        }

    return result


def run_boq_cleanup_pipeline_for_table(
    table_payload: Dict[str, Any],
    *,
    rows_key: str = "rows",
    attach_debug: bool = False,
    include_debug_meta: bool = False,
    drop_empty_rows: bool = True,
) -> Dict[str, Any]:
    payload = deepcopy(table_payload or {})
    rows = payload.get(rows_key, [])

    result = run_boq_cleanup_pipeline(
        rows,
        attach_debug=attach_debug,
        include_debug_meta=include_debug_meta,
        drop_empty_rows=drop_empty_rows,
    )

    payload[rows_key] = result["rows"]
    payload["boq_cleanup_pipeline"] = result["stats"]

    if attach_debug:
        payload["boq_cleanup_pipeline_debug"] = result.get("debug", {})

    return payload


