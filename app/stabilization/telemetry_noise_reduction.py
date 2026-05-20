from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from app.observability.runtime_anomaly_detector import build_runtime_anomaly_report
from app.operations.runtime_alerts import get_runtime_alerts

from ._shared import now_iso, safe_int, safe_str


def _signature(item: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        safe_str(item.get("type") or item.get("alert_type") or "runtime"),
        safe_str(item.get("severity") or "info"),
        safe_str(item.get("title") or item.get("message") or "alert"),
    )


def reduce_telemetry_noise(
    *,
    alerts: List[Dict[str, Any]] | None = None,
    anomalies: List[Dict[str, Any]] | None = None,
    limit: int = 100,
    deduplication_window_minutes: int = 15,
) -> Dict[str, Any]:
    alerts = list(alerts or [])
    anomalies = list(anomalies or [])
    candidates = []
    for record in alerts:
        if isinstance(record, dict):
            candidates.append({**record, "source": "runtime_alerts"})
    for record in anomalies:
        if isinstance(record, dict):
            candidates.append(
                {
                    "alert_id": record.get("anomaly_id"),
                    "type": record.get("type", "anomaly"),
                    "severity": record.get("severity", "warning"),
                    "title": record.get("message", "Runtime anomaly"),
                    "message": record.get("message", "Runtime anomaly"),
                    "created_at": record.get("created_at"),
                    "details": record.get("evidence", {}),
                    "source": "runtime_anomalies",
                }
            )

    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[_signature(item)].append(item)

    retained: List[Dict[str, Any]] = []
    aggregated_groups: List[Dict[str, Any]] = []
    duplicate_count = 0
    critical_count = 0
    for signature, items in grouped.items():
        severity = safe_str(items[0].get("severity") or "info")
        if severity == "critical":
            retained.extend(items)
            critical_count += len(items)
            aggregated_groups.append(
                {
                    "type": signature[0],
                    "severity": severity,
                    "title": signature[2],
                    "count": len(items),
                    "deduplicated": False,
                }
            )
            continue
        lead = dict(items[0])
        lead["related_count"] = len(items)
        lead["deduplicated"] = len(items) > 1
        retained.append(lead)
        duplicate_count += max(0, len(items) - 1)
        aggregated_groups.append(
            {
                "type": signature[0],
                "severity": severity,
                "title": signature[2],
                "count": len(items),
                "deduplicated": len(items) > 1,
            }
        )

    severity_counts = Counter(safe_str(item.get("severity") or "info") for item in retained)
    retained.sort(key=lambda item: (safe_str(item.get("severity") or "info"), safe_str(item.get("created_at") or ""), safe_str(item.get("title") or "")))
    status = "healthy" if not duplicate_count and not critical_count else "degraded"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime" if candidates else "fallback",
        "deduplication_window_minutes": deduplication_window_minutes,
        "alerts": retained[: max(1, int(limit or 100))],
        "alert_groups": aggregated_groups,
        "severity_counts": dict(severity_counts),
        "retained_count": len(retained),
        "suppressed_count": duplicate_count,
        "critical_count": critical_count,
        "noise_score": safe_int(duplicate_count * 10 + len(candidates)),
        "advisory_only": True,
    }


def build_telemetry_noise_reduction_report(limit: int = 100, deduplication_window_minutes: int = 15) -> Dict[str, Any]:
    alerts = list(get_runtime_alerts(limit=limit).get("alerts", []))
    anomalies = list(build_runtime_anomaly_report(limit=limit).get("anomalies", []))
    return reduce_telemetry_noise(
        alerts=alerts,
        anomalies=anomalies,
        limit=limit,
        deduplication_window_minutes=deduplication_window_minutes,
    )
