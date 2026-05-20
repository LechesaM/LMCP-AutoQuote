from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    return get_runtime_paths().manual_production_file("dead_letter_queue.jsonl")


def _read() -> List[Dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(payload)
    except Exception:
        return []
    return items


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def move_to_dlq(job: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    record = {
        "dlq_id": f"dlq-{datetime.now(timezone.utc).timestamp()}",
        "job_id": str(job.get("job_id") or ""),
        "tender_id": str(job.get("tender_id") or ""),
        "job_type": str(job.get("job_type") or ""),
        "reason": reason,
        "payload": dict(job or {}),
        "created_at": _now_iso(),
        "archived": False,
    }
    return _append(record)


def list_dlq() -> Dict[str, Any]:
    items = _read()
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "items": items,
        "count": len(items),
    }


def retry_from_dlq(dlq_id: str) -> Dict[str, Any]:
    items = _read()
    match = next((item for item in items if str(item.get("dlq_id") or "") == str(dlq_id)), None)
    if not match:
        raise ValueError(f"Unknown DLQ item: {dlq_id}")
    job = dict(match.get("payload") or {})
    if not job:
        raise ValueError("DLQ payload missing")
    job["status"] = "queued"
    job["updated_at"] = _now_iso()
    from app.orchestration.durable_queue import enqueue_job

    enqueue_job(tender_id=str(job.get("tender_id") or ""), job_type=str(job.get("job_type") or ""), actor=str(job.get("actor") or ""), operator=str(job.get("operator") or ""), workflow_stage=str(job.get("workflow_stage") or ""), payload=job.get("payload") or {}, max_attempts=int(job.get("max_attempts") or 3))
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime", "dlq_id": dlq_id, "retried": True}


def archive_dlq_item(dlq_id: str) -> Dict[str, Any]:
    items = _read()
    updated = []
    archived = None
    for item in items:
        if str(item.get("dlq_id") or "") == str(dlq_id):
            item = dict(item)
            item["archived"] = True
            item["archived_at"] = _now_iso()
            archived = item
        updated.append(item)
    if archived is None:
        raise ValueError(f"Unknown DLQ item: {dlq_id}")
    path = _path()
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in updated) + "\n", encoding="utf-8")
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime", "dlq_id": dlq_id, "archived": True}
