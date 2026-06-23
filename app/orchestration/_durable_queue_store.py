from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Mapping
from uuid import uuid4

from app.core.runtime_paths import get_runtime_paths


_LOCK = RLock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manual_dir() -> Path:
    return get_runtime_paths().manual_production_dir


def queue_state_path() -> Path:
    return _manual_dir() / "durable_queue_state.json"


def queue_shadow_path() -> Path:
    return _manual_dir() / "durable_queue.jsonl"


def dlq_state_path() -> Path:
    return _manual_dir() / "dead_letter_queue_state.json"


def dlq_shadow_path() -> Path:
    return _manual_dir() / "dead_letter_queue.jsonl"


def snapshot_path() -> Path:
    return _manual_dir() / "queue_state_snapshot.json"


def _default_queue_state() -> Dict[str, Any]:
    return {"jobs": [], "idempotency_index": {}, "updated_at": _utc_now_iso()}


def _default_dlq_state() -> Dict[str, Any]:
    return {"items": [], "updated_at": _utc_now_iso()}


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")


def normalize_job_type(job_type: Any) -> str:
    return str(getattr(job_type, "value", job_type) or "").strip().lower()


def load_queue_state() -> Dict[str, Any]:
    with _LOCK:
        state = _read_json(queue_state_path(), _default_queue_state())
        state.setdefault("jobs", [])
        state.setdefault("idempotency_index", {})
        if not isinstance(state["jobs"], list):
            state["jobs"] = []
        if not isinstance(state["idempotency_index"], dict):
            state["idempotency_index"] = {}
        return state


def save_queue_state(state: Dict[str, Any]) -> None:
    with _LOCK:
        payload = dict(state or {})
        payload.setdefault("jobs", [])
        payload.setdefault("idempotency_index", {})
        payload["updated_at"] = _utc_now_iso()
        _write_json(queue_state_path(), payload)
        _append_jsonl(queue_shadow_path(), {"event": "queue_state", "generated_at": payload["updated_at"], "snapshot": payload})


def load_dlq_state() -> Dict[str, Any]:
    with _LOCK:
        state = _read_json(dlq_state_path(), _default_dlq_state())
        state.setdefault("items", [])
        if not isinstance(state["items"], list):
            state["items"] = []
        return state


def save_dlq_state(state: Dict[str, Any]) -> None:
    with _LOCK:
        payload = dict(state or {})
        payload.setdefault("items", [])
        payload["updated_at"] = _utc_now_iso()
        _write_json(dlq_state_path(), payload)
        _append_jsonl(dlq_shadow_path(), {"event": "dlq_state", "generated_at": payload["updated_at"], "snapshot": payload})


def next_job_id() -> str:
    return f"job-{uuid4()}"


def next_dlq_id() -> str:
    return f"dlq-{uuid4()}"


def find_job(state: Mapping[str, Any], job_id: str) -> Dict[str, Any] | None:
    for job in state.get("jobs", []):
        if str(job.get("job_id")) == str(job_id):
            return job
    return None


def select_queued_job(state: Mapping[str, Any]) -> Dict[str, Any] | None:
    jobs = [job for job in state.get("jobs", []) if str(job.get("status") or "").lower() in {"pending", "retry_pending"}]
    if not jobs:
        return None
    jobs.sort(key=lambda job: str(job.get("created_at") or job.get("updated_at") or ""))
    return jobs[0]


def update_job(state: Dict[str, Any], job: Dict[str, Any]) -> None:
    jobs = state.setdefault("jobs", [])
    for index, existing in enumerate(jobs):
        if str(existing.get("job_id")) == str(job.get("job_id")):
            jobs[index] = job
            return
    jobs.append(job)


def queue_counts(state: Mapping[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {"queued": 0, "running": 0, "retry_pending": 0, "failed": 0, "completed": 0, "blocked": 0}
    for job in state.get("jobs", []):
        status = str(job.get("status") or "").lower()
        if status == "pending":
            counts["queued"] += 1
        elif status in counts:
            counts[status] += 1
        else:
            counts.setdefault(status, 0)
            counts[status] += 1
    return counts


def queue_depth(state: Mapping[str, Any]) -> int:
    counts = queue_counts(state)
    return counts.get("queued", 0) + counts.get("running", 0) + counts.get("retry_pending", 0) + counts.get("failed", 0) + counts.get("blocked", 0)


def queue_snapshot(state: Mapping[str, Any], *, limit: int = 20) -> Dict[str, Any]:
    jobs = list(state.get("jobs", []))[: max(0, int(limit))]
    dlq_state = load_dlq_state()
    return {
        "jobs": jobs,
        "dlq_items": list(dlq_state.get("items", []))[: max(0, int(limit))],
        "counts": queue_counts(state),
        "depth": queue_depth(state),
        "generated_at": _utc_now_iso(),
    }


def save_snapshot(snapshot: Dict[str, Any]) -> Path:
    path = snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    return path


def load_snapshot() -> Dict[str, Any]:
    path = snapshot_path()
    if not path.exists():
        return {"snapshot": {"jobs": [], "dlq_items": [], "counts": {}, "depth": 0}, "snapshot_path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"snapshot": {"jobs": [], "dlq_items": [], "counts": {}, "depth": 0}, "snapshot_path": str(path)}
    return payload if isinstance(payload, dict) else {"snapshot": {"jobs": [], "dlq_items": [], "counts": {}, "depth": 0}, "snapshot_path": str(path)}


def append_dlq_record(record: Dict[str, Any]) -> Dict[str, Any]:
    state = load_dlq_state()
    items = state.setdefault("items", [])
    existing = None
    for item in items:
        if str(item.get("dlq_id")) == str(record.get("dlq_id")):
            existing = item
            break
    if existing is None:
        items.append(record)
    else:
        existing.update(record)
    save_dlq_state(state)
    return record


def list_active_dlq_items() -> List[Dict[str, Any]]:
    state = load_dlq_state()
    return [dict(item) for item in state.get("items", []) if not bool(item.get("archived"))]


def find_dlq_item(dlq_id: str) -> Dict[str, Any] | None:
    for item in load_dlq_state().get("items", []):
        if str(item.get("dlq_id")) == str(dlq_id):
            return item
    return None

