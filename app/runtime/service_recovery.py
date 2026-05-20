from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .api_timeout_policy import build_api_timeout_policy, get_timeout_policy
from .graceful_degradation import build_graceful_degradation_report
from .retry_policy import build_retry_policy
from .stale_data_guard import build_stale_data_guard_report, get_last_safe_snapshot


def _clean(items: Iterable[str] | None) -> List[str]:
    return [str(item).strip() for item in (items or []) if str(item).strip()]


def build_service_recovery_report(
    service_name: str,
    current_snapshot: Mapping[str, Any] | None = None,
    *,
    timeout_seconds: float | None = None,
    stale_after_minutes: int = 15,
) -> Dict[str, Any]:
    timeout_policy = build_api_timeout_policy(service_name, timeout_seconds=timeout_seconds) if timeout_seconds is not None else get_timeout_policy(service_name)
    retry_policy = build_retry_policy(service_name)
    guard = build_stale_data_guard_report(service_name, current_snapshot or {}, stale_after_minutes=stale_after_minutes)
    degradation = build_graceful_degradation_report(
        service_name,
        current_snapshot or {},
        warnings=guard.get("warnings", []),
        blockers=guard.get("blockers", []),
        stale_after_minutes=stale_after_minutes,
    )
    last_safe = get_last_safe_snapshot(service_name)
    recommended_actions: List[str] = []
    if guard.get("stale"):
        recommended_actions.append("surface stale telemetry to operators")
    if guard.get("blockers"):
        recommended_actions.append("investigate runtime blockers before resuming normal reporting")
    if not last_safe.get("available"):
        recommended_actions.append("generate a safe runtime snapshot before declaring recovery")
    if guard.get("recovery_success"):
        recommended_actions.append("continue serving the last known safe telemetry until fresh runtime data is healthy")
    return {
        "status": guard.get("status", "degraded"),
        "generated_at": guard.get("generated_at"),
        "data_source": guard.get("data_source", "runtime"),
        "service_name": service_name,
        "timeout_policy": timeout_policy,
        "retry_policy": retry_policy,
        "degradation": degradation,
        "guard": guard,
        "last_safe_snapshot": last_safe.get("payload", {}),
        "last_safe_snapshot_at": last_safe.get("generated_at"),
        "recommended_actions": _clean(recommended_actions),
        "warnings": _clean(guard.get("warnings", [])),
        "blockers": _clean(guard.get("blockers", [])),
        "advisory_only": True,
    }
