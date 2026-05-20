from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from ._shared import now_iso


def _flatten(prefix: str, payload: Any, rows: List[Dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten(next_prefix, value, rows)
        return
    if isinstance(payload, list):
        rows.append({"key": prefix, "value": json.dumps(payload, ensure_ascii=False, default=str)})
        return
    rows.append({"key": prefix, "value": payload})


def build_csv_export(report: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    _flatten("", report, rows)
    csv_lines = ["key,value"] + [f"{row['key']},{json.dumps(row['value'], ensure_ascii=False, default=str)}" for row in rows]
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": report.get("data_source", "fallback"),
        "filename": "strategic_report.csv",
        "csv": "\n".join(csv_lines),
        "row_count": len(rows),
    }

