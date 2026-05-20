from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.operations.health_snapshots import get_health_snapshots
from app.operations.runtime_metrics import get_runtime_metrics, get_runtime_snapshots

from ._shared import now_iso, safe_float, safe_int


def _snapshot_age_minutes(snapshot: Dict[str, Any]) -> float:
    try:
        generated_at = str(snapshot.get("generated_at") or "")
        if not generated_at:
            return 0.0
        timestamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        return round(max(0.0, (datetime.now(timezone.utc) - timestamp).total_seconds() / 60.0), 2)
    except Exception:
        return 0.0


def build_fallback_resilience_report(limit: int = 100) -> Dict[str, Any]:
    runtime = get_runtime_metrics(limit=limit)
    snapshots = get_runtime_snapshots(limit=limit).get("snapshots", [])
    health_snapshots = get_health_snapshots(limit=limit).get("snapshots", [])
    combined = list(snapshots) + list(health_snapshots)
    fallback_snapshots = [snapshot for snapshot in combined if str(snapshot.get("data_source") or snapshot.get("payload", {}).get("data_source") or "").lower() != "runtime"]
    stale_fallback_snapshots = [snapshot for snapshot in fallback_snapshots if _snapshot_age_minutes(snapshot) > 15]
    recovery_success = runtime.get("status") == "ok" and not stale_fallback_snapshots
    warnings: List[str] = []
    if fallback_snapshots:
        warnings.append("Fallback data has been activated.")
    if stale_fallback_snapshots:
        warnings.append("Stale fallback data requires refresh.")
    if runtime.get("status") != "ok":
        warnings.append("Runtime recovery is not yet healthy.")
    if not combined:
        warnings.append("No runtime snapshots were available.")
    summary = {
        "runtime_snapshot_count": len(snapshots),
        "health_snapshot_count": len(health_snapshots),
        "fallback_activation_count": len(fallback_snapshots),
        "stale_fallback_count": len(stale_fallback_snapshots),
        "latest_snapshot_age_minutes": _snapshot_age_minutes(combined[-1]) if combined else 0.0,
        "runtime_status": runtime.get("status", "fallback"),
    }
    status = "healthy"
    if stale_fallback_snapshots or runtime.get("status") not in {"ok", "healthy"}:
        status = "degraded"
    if len(stale_fallback_snapshots) > 5:
        status = "failing"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime" if combined else "fallback",
        "fallback_health_summary": summary,
        "fallback_activations": fallback_snapshots[-max(1, int(limit or 100)) :],
        "stale_fallbacks": stale_fallback_snapshots[-max(1, int(limit or 100)) :],
        "runtime_recovery_success": recovery_success,
        "recovery_success_rate": 100.0 if recovery_success else 0.0,
        "warnings": warnings,
        "blockers": ["stale fallback data"] if stale_fallback_snapshots else [],
        "advisory_only": True,
    }

