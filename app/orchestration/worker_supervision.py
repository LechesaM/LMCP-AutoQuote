from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from app.core.runtime_paths import get_runtime_paths
from app.orchestration.durable_queue import get_queue_health


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _path() -> Path:
    return get_runtime_paths().manual_production_file("worker_heartbeats.jsonl")


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


def record_worker_heartbeat(worker_id: str, *, status: str = "healthy", details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    record = {
        "heartbeat_id": f"hb-{uuid4().hex}",
        "worker_id": str(worker_id or ""),
        "status": str(status or "healthy"),
        "details": details or {},
        "created_at": _now_iso(),
    }
    return _append(record)


def detect_stale_workers(stale_after_minutes: int = 5) -> List[Dict[str, Any]]:
    cutoff = _now() - timedelta(minutes=max(1, int(stale_after_minutes)))
    latest: Dict[str, Dict[str, Any]] = {}
    for record in _read():
        worker_id = str(record.get("worker_id") or "")
        if worker_id:
            latest[worker_id] = record
    stale = []
    for worker_id, record in latest.items():
        created_at = str(record.get("created_at") or "")
        try:
            seen = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            seen = cutoff - timedelta(minutes=1)
        if seen < cutoff:
            stale.append(record)
    return stale


def get_worker_supervision_report(stale_after_minutes: int = 5) -> Dict[str, Any]:
    workers = _read()
    stale = detect_stale_workers(stale_after_minutes=stale_after_minutes)
    queue_health = get_queue_health()
    return {
        "status": "degraded" if stale else "healthy",
        "generated_at": _now_iso(),
        "data_source": "runtime" if workers else "fallback",
        "worker_count": len({item.get("worker_id") for item in workers if item.get("worker_id")}),
        "stale_worker_count": len(stale),
        "stale_workers": stale,
        "queue_lag_minutes": queue_health.get("depth", 0) * 5,
        "queue_health": queue_health,
    }

