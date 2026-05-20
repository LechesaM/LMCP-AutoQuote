from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.workflow_monitor import get_workflow_summary
from app.orchestration.queue_monitor import get_queue_summary
from app.harvest.source_health import get_source_health_summary
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.persistence.repositories import get_persistence_health


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_path() -> Path:
    return get_runtime_paths().manual_production_file("health_snapshots.jsonl")


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _read(limit: int = 100) -> List[Dict[str, Any]]:
    path = _snapshot_path()
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
    return items[-max(1, int(limit or 100)) :]


def capture_health_snapshot(limit: int = 100) -> Dict[str, Any]:
    payload = {
        "system_health": get_system_health(),
        "metrics": get_metrics_snapshot(),
        "workflow_summary": get_workflow_summary(limit=limit),
        "queue_summary": get_queue_summary(limit=limit),
        "source_summary": get_source_health_summary(limit=limit),
        "operator_capacity": get_operator_capacity_snapshot(),
        "persistence": get_persistence_health(),
        "generated_at": _now_iso(),
        "data_source": "runtime",
    }
    return _append({"snapshot_id": f"health-{datetime.now(timezone.utc).timestamp()}", **payload})


def get_health_snapshots(limit: int = 100) -> Dict[str, Any]:
    items = _read(limit=limit)
    if not items:
        items = [capture_health_snapshot(limit=limit)]
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "snapshots": items,
        "total": len(items),
    }

