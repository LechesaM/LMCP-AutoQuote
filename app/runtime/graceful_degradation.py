from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .stale_data_guard import build_stale_data_guard_report


def _warnings_from(values: Iterable[str] | None) -> List[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def build_graceful_degradation_report(
    service_name: str,
    current_snapshot: Mapping[str, Any] | None,
    *,
    warnings: Iterable[str] | None = None,
    blockers: Iterable[str] | None = None,
    stale_after_minutes: int = 15,
) -> Dict[str, Any]:
    guard = build_stale_data_guard_report(
        service_name,
        current_snapshot or {},
        stale_after_minutes=stale_after_minutes,
    )
    report_warnings = _warnings_from(warnings) + list(guard.get("warnings", []))
    report_blockers = _warnings_from(blockers) + list(guard.get("blockers", []))
    status = guard.get("status", "healthy")
    if report_blockers:
        status = "failing"
    elif report_warnings and status == "healthy":
        status = "degraded"
    return {
        "status": status,
        "generated_at": guard.get("generated_at"),
        "data_source": guard.get("data_source", "runtime"),
        "service_name": service_name,
        "stale": guard.get("stale", False),
        "effective_snapshot": guard.get("effective_snapshot", {}),
        "current_snapshot": guard.get("current_snapshot", {}),
        "last_safe_snapshot": guard.get("last_safe_snapshot", {}),
        "last_safe_snapshot_at": guard.get("last_safe_snapshot_at"),
        "warnings": report_warnings,
        "blockers": report_blockers,
        "advisory_only": True,
    }

