from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.operations.structured_logging import log_worker_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _heartbeat_file() -> Path:
    return get_runtime_paths().health_dir / "worker_heartbeats.jsonl"


def _parse_iso(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _read() -> List[Dict[str, Any]]:
    path = _heartbeat_file()
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


def _write(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _heartbeat_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
    return payload


def record_worker_heartbeat(
    worker_id: str,
    *,
    status: str = "healthy",
    queue_name: str = "",
    task_id: str = "",
    task_name: str = "",
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = {
        "worker_id": str(worker_id or "").strip(),
        "status": str(status or "healthy").strip(),
        "queue_name": str(queue_name or "").strip(),
        "task_id": str(task_id or "").strip(),
        "task_name": str(task_name or "").strip(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "created_at": _utc_now_iso(),
        "details": details or {},
    }
    log_worker_event("heartbeat", "Worker heartbeat recorded", **payload)
    return _write(payload)


def detect_stale_workers(stale_after_minutes: int = 5) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(stale_after_minutes or 5)))
    latest: Dict[str, Dict[str, Any]] = {}
    for row in _read():
        worker_id = str(row.get("worker_id") or "").strip()
        if not worker_id:
            continue
        current = latest.get(worker_id)
        current_time = _parse_iso(row.get("created_at") or row.get("heartbeat_at"))
        if current is None:
            latest[worker_id] = row
            continue
        current_time = current_time or datetime.min.replace(tzinfo=timezone.utc)
        previous_time = _parse_iso(current.get("created_at") or current.get("heartbeat_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if current_time > previous_time:
            latest[worker_id] = row
    stale: List[Dict[str, Any]] = []
    for worker_id, row in latest.items():
        timestamp = _parse_iso(row.get("created_at") or row.get("heartbeat_at"))
        if timestamp is None or timestamp < cutoff or str(row.get("status") or "").lower() not in {"healthy", "alive", "busy"}:
            stale.append(
                {
                    "worker_id": worker_id,
                    "created_at": row.get("created_at") or row.get("heartbeat_at"),
                    "status": row.get("status"),
                    "queue_name": row.get("queue_name", ""),
                    "task_name": row.get("task_name", ""),
                    "task_id": row.get("task_id", ""),
                }
            )
    return stale
