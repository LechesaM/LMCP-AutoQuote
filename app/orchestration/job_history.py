from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.runtime_paths import get_runtime_paths
from app.persistence.repositories import QueueFailureRepository, QueueHistoryRepository, QueueRetryRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _history_path() -> Path:
    return get_runtime_paths().manual_production_file("queue_history.jsonl")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def append_history_event(event_type: str, record: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(record or {})
    payload.setdefault("event_type", event_type)
    payload.setdefault("created_at", _now_iso())
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    try:
        repo = QueueHistoryRepository(jsonl_path=path)
        repo.append_history(payload)
    except Exception:
        pass
    return payload


def get_job_history(job_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    records = _read_jsonl(_history_path())
    return [item for item in records if str(item.get("job_id") or "") == str(job_id)][: max(1, int(limit or 200))]


def append_retry_history(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = append_history_event("retry", record)
    try:
        repo = QueueRetryRepository()
        repo.append_retry(payload)
    except Exception:
        pass
    return payload


def append_failure_history(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = append_history_event("failure", record)
    try:
        repo = QueueFailureRepository()
        repo.append_failure(payload)
    except Exception:
        pass
    return payload
