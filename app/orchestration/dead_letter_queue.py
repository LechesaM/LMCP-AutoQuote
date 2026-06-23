from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from ._durable_queue_store import append_dlq_record, find_dlq_item, list_active_dlq_items, load_dlq_state, save_dlq_state


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_item(job_or_record: Dict[str, Any], reason: str) -> Dict[str, Any]:
    source_job_id = str(job_or_record.get("job_id") or job_or_record.get("source_job_id") or "")
    return {
        "dlq_id": str(job_or_record.get("dlq_id") or f"dlq-{uuid4()}"),
        "job_id": source_job_id,
        "source_job_id": source_job_id,
        "tender_id": str(job_or_record.get("tender_id") or ""),
        "job_type": str(job_or_record.get("job_type") or ""),
        "payload": dict(job_or_record.get("payload") or {}),
        "reason": str(reason or job_or_record.get("reason") or "unknown"),
        "created_at": str(job_or_record.get("created_at") or _utc_now_iso()),
        "updated_at": _utc_now_iso(),
        "archived": bool(job_or_record.get("archived", False)),
        "retried": bool(job_or_record.get("retried", False)),
        "retried_at": job_or_record.get("retried_at"),
        "archived_at": job_or_record.get("archived_at"),
    }


def move_to_dlq(job_or_record: Dict[str, Any], reason: str) -> Dict[str, Any]:
    record = _normalise_item(job_or_record, reason)
    append_dlq_record(record)
    return dict(record)


def list_dlq() -> Dict[str, Any]:
    items = list_active_dlq_items()
    return {"count": len(items), "items": items}


def retry_from_dlq(dlq_id: str) -> Dict[str, Any]:
    state = load_dlq_state()
    items = state.setdefault("items", [])
    for item in items:
        if str(item.get("dlq_id")) == str(dlq_id):
            item["retried"] = True
            item["retried_at"] = _utc_now_iso()
            item["updated_at"] = _utc_now_iso()
            save_dlq_state(state)
            return {"retried": True, "dlq_id": dlq_id, "job_id": item.get("job_id"), "item": dict(item)}
    return {"retried": False, "dlq_id": dlq_id}


def archive_dlq_item(dlq_id: str) -> Dict[str, Any]:
    state = load_dlq_state()
    items = state.setdefault("items", [])
    for item in items:
        if str(item.get("dlq_id")) == str(dlq_id):
            item["archived"] = True
            item["archived_at"] = _utc_now_iso()
            item["updated_at"] = _utc_now_iso()
            save_dlq_state(state)
            return {"archived": True, "dlq_id": dlq_id, "item": dict(item)}
    return {"archived": False, "dlq_id": dlq_id}

