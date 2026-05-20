from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, Iterable, List


REQUIRED_MODULES = (
    "fastapi",
    "pydantic",
    "app.api.router_registry",
    "app.auth.rbac",
    "app.auth.session_service",
    "app.core.runtime_config",
    "app.deployment.startup_validator",
    "app.monitoring.workflow_monitor",
    "app.persistence.db",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_modules(modules: Iterable[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for module_name in modules:
        try:
            import_module(module_name)
            results.append({"module": module_name, "status": "ok", "present": True})
        except Exception as exc:
            results.append({"module": module_name, "status": "missing", "present": False, "error": str(exc)})
    return results


def validate_dependencies() -> Dict[str, Any]:
    checks = _check_modules(REQUIRED_MODULES)
    blockers = [check for check in checks if not check.get("present")]
    status = "healthy"
    if blockers:
        status = "failing"
    return {
        "status": status,
        "generated_at": _now_iso(),
        "checks": checks,
        "blockers": blockers,
    }


def get_dependency_summary() -> Dict[str, Any]:
    return validate_dependencies()
