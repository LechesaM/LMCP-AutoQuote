from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.monitoring.health_service import get_system_health
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence.repositories import get_persistence_health

from .runtime_metrics import get_metrics_snapshot
from .structured_logging import log_runtime_diagnostic


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_file() -> Path:
    return get_runtime_paths().health_dir / "health_snapshots.jsonl"


def _read_snapshots(path: Path | None = None) -> List[Dict[str, Any]]:
    file_path = path or _snapshot_file()
    if not file_path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _write_snapshot(snapshot: Dict[str, Any], path: Path | None = None) -> Dict[str, Any]:
    file_path = path or _snapshot_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(snapshot or {})
    payload.setdefault("generated_at", _utc_now_iso())
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
    return payload


def capture_health_snapshot() -> Dict[str, Any]:
    system_health = get_system_health()
    workflow_summary = get_workflow_summary(limit=50)
    metrics = get_metrics_snapshot()
    persistence = get_persistence_health()

    status = "ok"
    if str(system_health.get("status") or "").lower() not in {"ok", "healthy"}:
        status = "degraded"
    if str(persistence.get("status") or "").lower() not in {"ok", "healthy"}:
        status = "degraded"
    if str(workflow_summary.get("status") or "").lower() in {"failed", "unhealthy"}:
        status = "degraded"

    snapshot = {
        "status": status,
        "generated_at": _utc_now_iso(),
        "data_source": "runtime",
        "system_health": system_health,
        "workflow_summary": workflow_summary,
        "metrics": metrics,
        "persistence": persistence,
    }
    log_runtime_diagnostic("health_snapshot", "Captured runtime health snapshot", snapshot=snapshot)
    return _write_snapshot(snapshot)


def get_health_snapshots(limit: int = 25) -> Dict[str, Any]:
    records = _read_snapshots()
    limit = max(1, int(limit or 25))
    recent = list(reversed(records[-limit:]))
    return {
        "status": "ok" if recent else "fallback",
        "items": recent,
        "total": len(records),
        "log_file": str(_snapshot_file()),
        "updated_at": recent[0].get("generated_at") if recent else _utc_now_iso(),
    }
