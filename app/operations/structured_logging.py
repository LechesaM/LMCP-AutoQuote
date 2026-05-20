from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_path() -> Path:
    return get_runtime_paths().manual_production_file("operations_logs.jsonl")


def log_operation_event(
    category: str,
    message: str,
    *,
    severity: str = "info",
    request_id: str = "",
    operator_id: str = "",
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = {
        "event_id": f"oplog-{datetime.now(timezone.utc).timestamp()}",
        "category": str(category or "runtime"),
        "message": str(message or ""),
        "severity": str(severity or "info"),
        "request_id": str(request_id or ""),
        "operator_id": str(operator_id or ""),
        "details": details or {},
        "created_at": _now_iso(),
    }
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    return payload

