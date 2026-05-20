from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    return get_runtime_paths().manual_production_file("runtime_incidents.jsonl")


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _read(limit: int = 100) -> List[Dict[str, Any]]:
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
    return items[-max(1, int(limit or 100)) :]


def record_incident(
    incident_type: str,
    title: str,
    *,
    severity: str = "warning",
    status: str = "active",
    operator_id: str = "",
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    record = {
        "incident_id": f"incident-{datetime.now(timezone.utc).timestamp()}",
        "incident_type": str(incident_type or "runtime"),
        "title": str(title or ""),
        "severity": str(severity or "warning"),
        "status": str(status or "active"),
        "operator_id": str(operator_id or ""),
        "details": details or {},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "acknowledged_at": "",
        "acknowledged_by": "",
    }
    return _append(record)


def get_incident_summary(limit: int = 100) -> Dict[str, Any]:
    incidents = _read(limit=limit)
    severity_counts: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    for incident in incidents:
        severity_counts[str(incident.get("severity") or "warning")] = severity_counts.get(str(incident.get("severity") or "warning"), 0) + 1
        status_counts[str(incident.get("status") or "active")] = status_counts.get(str(incident.get("status") or "active"), 0) + 1
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if incidents else "fallback",
        "total_incidents": len(incidents),
        "severity_counts": severity_counts,
        "status_counts": status_counts,
        "active_critical_incidents": len([item for item in incidents if item.get("severity") == "critical" and item.get("status") == "active"]),
        "incidents": incidents,
        "history": dict((item.get("incident_id"), item) for item in incidents if item.get("incident_id")),
        "recovery_events": len([item for item in incidents if "recovery" in str(item.get("incident_type") or "")]),
    }

