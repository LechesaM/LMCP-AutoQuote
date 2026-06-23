from __future__ import annotations

from typing import Any, Dict, List

from .api_timeout_policy import build_api_timeout_policy
from .retry_policy import build_retry_policy
from .stale_data_guard import build_stale_data_guard_report


def build_service_recovery_report(service_name: str, snapshot: Dict[str, Any], *, timeout_seconds: float | None = None) -> Dict[str, Any]:
    stale_guard = build_stale_data_guard_report(service_name, snapshot or {})
    timeout_policy = build_api_timeout_policy(service_name, timeout_seconds=timeout_seconds)
    retry_policy = build_retry_policy(service_name)
    warnings: List[str] = list(stale_guard.get("warnings") or [])
    blockers: List[str] = []
    if stale_guard.get("stale"):
        warnings.append(f"{service_name} snapshot is stale")
    if str(snapshot.get("status") or "").lower() not in {"ok", "healthy", "fresh"}:
        blockers.append(f"{service_name} reported {snapshot.get('status') or 'unknown'}")
    if not snapshot.get("data_source"):
        warnings.append(f"{service_name} snapshot has no explicit data source")
    return {
        "service_name": service_name,
        "advisory_only": True,
        "status": "degraded" if blockers or stale_guard.get("stale") else "ok",
        "generated_at": stale_guard.get("generated_at"),
        "timeout_policy": timeout_policy,
        "retry_policy": retry_policy,
        "snapshot": dict(snapshot or {}),
        "stale_guard": stale_guard,
        "warnings": warnings,
        "blockers": blockers,
    }

