from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths
from app.harvest.source_models import SourceHealthRecord


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _health_path() -> Path:
    try:
        get_runtime_paths.cache_clear()
    except Exception:
        pass
    return get_runtime_paths().manual_production_file("harvest_source_health.jsonl")


def _load_latest() -> Dict[str, Dict[str, Any]]:
    path = _health_path()
    if not path.exists():
        return {}
    latest: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue
        if isinstance(record, dict) and record.get("source_id"):
            latest[str(record["source_id"])] = record
    return latest


def _append(record: Dict[str, Any]) -> None:
    path = _health_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _coerce(source_id: str) -> SourceHealthRecord:
    latest = _load_latest()
    record = latest.get(str(source_id))
    if record:
        return SourceHealthRecord.validate_payload(record)
    return SourceHealthRecord.validate_payload({"source_id": str(source_id)})


def _derive_status(record: SourceHealthRecord) -> str:
    if record.disabled_reason:
        return "disabled"
    if record.consecutive_failures >= 5 or record.failure_count >= 10 or record.parser_failure_rate >= 0.75:
        return "failing"
    if record.consecutive_failures >= 2 or record.failure_count >= 3 or record.parser_failure_rate >= 0.35:
        return "degraded"
    return "healthy"


def record_success(source_id: str, response_time_seconds: float = 0.0, parser_failure: bool = False, metadata: Dict[str, Any] | None = None) -> SourceHealthRecord:
    record = _coerce(source_id)
    attempts = record.attempt_count + 1
    total_response_time = record.average_response_time * record.attempt_count + max(0.0, float(response_time_seconds))
    parser_failure_count = record.parser_failure_count + (1 if parser_failure else 0)
    updated = record.model_copy(update={
        "status": "healthy",
        "last_success": _now(),
        "consecutive_failures": 0,
        "attempt_count": attempts,
        "average_response_time": round(total_response_time / attempts, 4) if attempts else 0.0,
        "parser_failure_count": parser_failure_count,
        "parser_failure_rate": round(parser_failure_count / attempts, 4) if attempts else 0.0,
        "metadata_json": {**record.metadata_json, **(metadata or {})},
        "updated_at": _now(),
    })
    _append(updated.to_jsonable_dict())
    return updated


def record_failure(source_id: str, parser_failure: bool = False, metadata: Dict[str, Any] | None = None) -> SourceHealthRecord:
    record = _coerce(source_id)
    attempts = record.attempt_count + 1
    parser_failure_count = record.parser_failure_count + (1 if parser_failure else 0)
    failure_count = record.failure_count + 1
    consecutive_failures = record.consecutive_failures + 1
    updated = record.model_copy(update={
        "status": _derive_status(record.model_copy(update={
            "attempt_count": attempts,
            "failure_count": failure_count,
            "consecutive_failures": consecutive_failures,
            "parser_failure_count": parser_failure_count,
            "parser_failure_rate": round(parser_failure_count / attempts, 4) if attempts else 0.0,
        })),
        "last_failure": _now(),
        "failure_count": failure_count,
        "consecutive_failures": consecutive_failures,
        "attempt_count": attempts,
        "parser_failure_count": parser_failure_count,
        "parser_failure_rate": round(parser_failure_count / attempts, 4) if attempts else 0.0,
        "metadata_json": {**record.metadata_json, **(metadata or {})},
        "updated_at": _now(),
    })
    _append(updated.to_jsonable_dict())
    return updated


def get_source_health(source_id: str) -> SourceHealthRecord:
    return _coerce(source_id)


def should_disable_source(source_id: str) -> bool:
    record = _coerce(source_id)
    return record.status == "failing" and (record.consecutive_failures >= 5 or record.failure_count >= 10)
