from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.deployment.startup_validator import validate_startup

from .dependency_validator import validate_dependencies
from .environment_validator import validate_environment
from .production_blockers import build_production_blocker_report


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_startup_health_report(*, allow_degraded_startup: bool = False, limit: int = 25) -> Dict[str, Any]:
    environment = validate_environment()
    dependencies = validate_dependencies()
    startup = validate_startup(allow_degraded_startup=allow_degraded_startup)
    blockers = build_production_blocker_report(
        environment_report=environment,
        dependency_report=dependencies,
        startup_report=startup,
    )
    status = "healthy"
    if blockers.get("blockers"):
        status = "failing"
    elif any(
        report.get("status") in {"degraded", "warning"}
        for report in (environment, dependencies, startup, blockers)
    ):
        status = "degraded"

    return {
        "status": status,
        "generated_at": _now_iso(),
        "strict_production_startup": blockers.get("strict_production_startup", False),
        "environment": environment,
        "dependencies": dependencies,
        "startup_validation": startup,
        "production_blockers": blockers,
        "blockers": blockers.get("blockers", []),
        "warnings": blockers.get("warnings", []),
        "critical_blocker_count": len(blockers.get("blockers", [])),
        "limit": limit,
    }


def get_startup_health_report(*, allow_degraded_startup: bool = False, limit: int = 25) -> Dict[str, Any]:
    return build_startup_health_report(allow_degraded_startup=allow_degraded_startup, limit=limit)
