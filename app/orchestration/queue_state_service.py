from __future__ import annotations

from typing import Any, Dict

from ._durable_queue_store import load_queue_state, load_snapshot, queue_snapshot, save_snapshot, snapshot_path


def capture_queue_state(limit: int = 20) -> Dict[str, Any]:
    state = load_queue_state()
    snapshot = queue_snapshot(state, limit=limit)
    path = save_snapshot({"snapshot": snapshot, "snapshot_path": str(snapshot_path())})
    return {"snapshot": snapshot, "snapshot_path": str(path)}


def load_queue_state_snapshot() -> Dict[str, Any]:
    payload = load_snapshot()
    if "snapshot" not in payload:
        payload = {"snapshot": {"jobs": [], "dlq_items": [], "counts": {}, "depth": 0}, "snapshot_path": str(snapshot_path())}
    return payload


def build_queue_restart_recovery_report(limit: int = 20) -> Dict[str, Any]:
    snapshot_payload = capture_queue_state(limit=limit)
    snapshot = snapshot_payload.get("snapshot") or {}
    queued_jobs = int((snapshot.get("counts") or {}).get("queued", 0))
    running_jobs = int((snapshot.get("counts") or {}).get("running", 0))
    dlq_items = int(len(snapshot.get("dlq_items") or []))
    status = "degraded" if queued_jobs or running_jobs or dlq_items else "healthy"
    return {
        "status": status,
        "snapshot_path": snapshot_payload.get("snapshot_path"),
        "queued_jobs": queued_jobs,
        "running_jobs": running_jobs,
        "dlq_items": dlq_items,
        "snapshot": snapshot,
    }

