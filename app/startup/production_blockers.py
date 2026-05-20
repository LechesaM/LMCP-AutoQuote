from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from app.core.runtime_config import get_runtime_config


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_entries(items: Iterable[Dict[str, Any]], key: str = "blockers") -> List[str]:
    values: List[str] = []
    for item in items:
        values.extend(str(entry) for entry in item.get(key, []) if str(entry).strip())
    return values


def build_production_blocker_report(
    *,
    environment_report: Dict[str, Any] | None = None,
    dependency_report: Dict[str, Any] | None = None,
    startup_report: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    runtime = get_runtime_config()
    env_report = environment_report or {}
    dep_report = dependency_report or {}
    start_report = startup_report or {}

    blockers = _collect_entries((env_report, dep_report, start_report), key="blockers")
    warnings = _collect_entries((env_report, dep_report, start_report), key="warnings")
    fatal = [entry for entry in blockers if entry]

    status = "healthy"
    if fatal:
        status = "failing"
    elif warnings:
        status = "degraded"

    return {
        "status": status,
        "generated_at": _now_iso(),
        "strict_production_startup": runtime.strict_production_startup,
        "blockers": fatal,
        "warnings": warnings,
        "blocker_count": len(fatal),
        "warning_count": len(warnings),
        "fail_loudly": bool(runtime.strict_production_startup and fatal),
    }


def strict_production_startup_enabled() -> bool:
    return get_runtime_config().strict_production_startup
