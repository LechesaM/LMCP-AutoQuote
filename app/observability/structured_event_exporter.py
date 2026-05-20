from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.operations.incident_tracker import get_incident_summary
from app.operations.runtime_alerts import get_runtime_alerts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
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
    return items[-max(1, int(limit or 200)) :]


def build_structured_event_export(limit: int = 200) -> Dict[str, Any]:
    paths = get_runtime_paths()
    operations_logs = _read_jsonl(paths.manual_production_file("operations_logs.jsonl"), limit=limit)
    incidents = get_incident_summary(limit=limit)
    alerts = get_runtime_alerts(limit=limit)
    events: List[Dict[str, Any]] = []
    events.extend({"event_type": "operation", **item} for item in operations_logs)
    events.extend({"event_type": "incident", **item} for item in incidents.get("incidents", []))
    events.extend({"event_type": "alert", **item} for item in alerts.get("alerts", []))
    return {
        "status": "ok" if events else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if events else "fallback",
        "events": events[: max(1, int(limit or 200))],
        "counts": {
            "operation_events": len(operations_logs),
            "incident_events": len(incidents.get("incidents", [])),
            "alerts": len(alerts.get("alerts", [])),
        },
        "severity_counts": {
            "critical": len([item for item in alerts.get("alerts", []) if item.get("severity") == "critical"]),
            "warning": len([item for item in alerts.get("alerts", []) if item.get("severity") == "warning"]),
            "info": len([item for item in alerts.get("alerts", []) if item.get("severity") == "info"]),
        },
    }
