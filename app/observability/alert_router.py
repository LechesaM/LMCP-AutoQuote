from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.operations.runtime_alerts import get_runtime_alerts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _targets_for(alert: Dict[str, Any]) -> List[str]:
    targets = ["runtime_log"]
    severity = str(alert.get("severity") or "info")
    alert_type = str(alert.get("type") or "")
    if severity in {"warning", "critical"}:
        targets.append("operator_notification")
    if severity == "critical" or alert_type in {"persistence_failure", "auth_anomaly", "queue_overload", "source_outage"}:
        targets.append("incident_tracker")
    if alert_type in {"sla_breach", "runtime_degradation"}:
        targets.append("webhook_placeholder")
    if alert_type in {"auth_anomaly", "persistence_failure"}:
        targets.append("email_placeholder")
    return list(dict.fromkeys(targets))


def build_alert_routing_summary(limit: int = 100) -> Dict[str, Any]:
    payload = get_runtime_alerts(limit=limit)
    routes: List[Dict[str, Any]] = []
    target_counts = Counter()
    category_counts = Counter()
    for alert in payload.get("alerts", []):
        targets = _targets_for(alert)
        for target in targets:
            target_counts[target] += 1
        category_counts[str(alert.get("type") or "runtime")] += 1
        routes.append(
            {
                "alert_id": alert.get("alert_id", ""),
                "severity": alert.get("severity", "info"),
                "category": alert.get("type", "runtime"),
                "targets": targets,
                "advisory_only": True,
            }
        )
    return {
        "status": "ok" if routes else "fallback",
        "generated_at": _now_iso(),
        "data_source": payload.get("data_source", "fallback"),
        "routes": routes,
        "route_count": len(routes),
        "category_counts": dict(category_counts),
        "target_counts": dict(target_counts),
        "advisory_only": True,
    }
