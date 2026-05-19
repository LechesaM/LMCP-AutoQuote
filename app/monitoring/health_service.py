from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.api.router_registry import iter_router_specs
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.runtime_diagnostics import get_runtime_diagnostics
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence import db
from app.persistence.repositories import get_persistence_health


class ComponentHealth(StrictBaseModel):
    component: str
    status: str = "healthy"
    healthy: bool = True
    degraded: bool = False
    details: Dict[str, Any]
    checked_at: Any = None


class SystemHealthSummary(StrictBaseModel):
    status: str = "healthy"
    checked_at: Any = None
    environment: str = ""
    production_mode: str = ""
    components: List[Dict[str, Any]]
    healthy_components: int = 0
    degraded_components: int = 0
    unhealthy_components: int = 0


def _component_status(details: Dict[str, Any]) -> str:
    if details.get("healthy") is False:
        return "unhealthy"
    if details.get("degraded") or details.get("status") == "degraded":
        return "degraded"
    return "healthy"


def _component_health(component_name: str, builder: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        details = builder()
        status = _component_status(details)
        return ComponentHealth(
            component=component_name,
            status=status,
            healthy=status == "healthy",
            degraded=status == "degraded",
            details=details,
            checked_at=utc_now(),
        ).to_jsonable_dict()
    except Exception as exc:
        return ComponentHealth(
            component=component_name,
            status="unhealthy",
            healthy=False,
            degraded=False,
            details={"error": str(exc)},
            checked_at=utc_now(),
        ).to_jsonable_dict()


def _runtime_component() -> Dict[str, Any]:
    config = get_runtime_config()
    paths = get_runtime_paths()
    return {
        "healthy": True,
        "status": "healthy",
        "runtime_mode": config.mode.value,
        "environment": config.environment,
        "manual_production_enforced": config.manual_production_enforced,
        "final_submission_manual_only": config.final_submission_manual_only,
        "runtime_root_ready": paths.runtime_root.exists(),
        "manual_production_ready": paths.manual_production_dir.exists(),
    }


def _db_component() -> Dict[str, Any]:
    path = db.get_database_path()
    available = db.safe_initialize_database() and path.exists()
    return {
        "healthy": available,
        "status": "healthy" if available else "degraded",
        "db_ready": available,
        "db_file_present": path.exists(),
    }


def _workflow_component() -> Dict[str, Any]:
    summary = workflow_state_engine.list_recent_states(limit=1)
    return {
        "healthy": True,
        "status": "healthy",
        "available": True,
        "recent_state_count": len(summary.get("items", [])),
    }


def _audit_component() -> Dict[str, Any]:
    from app.services import audit_trail_service

    return {
        "healthy": True,
        "status": "healthy",
        "audit_file_present": audit_trail_service.AUDIT_FILE.exists(),
    }


def _deployment_component() -> Dict[str, Any]:
    from app.deployment.deployment_report import build_deployment_report

    report = build_deployment_report()
    return {
        "healthy": report.get("status") != "unhealthy",
        "status": report.get("status", "unknown"),
        "report": report,
    }


def _router_registry_component() -> Dict[str, Any]:
    specs = list(iter_router_specs())
    production = [spec for spec in specs if spec.status == "production"]
    legacy = [spec for spec in specs if spec.status != "production"]
    duplicate_names = len({spec.name for spec in specs}) != len(specs)
    return {
        "healthy": not duplicate_names,
        "status": "degraded" if duplicate_names else "healthy",
        "total_specs": len(specs),
        "production_specs": len(production),
        "non_production_specs": len(legacy),
        "duplicate_names": duplicate_names,
    }


_COMPONENTS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "runtime": _runtime_component,
    "db": _db_component,
    "workflow_engine": _workflow_component,
    "audit_service": _audit_component,
    "router_registry": _router_registry_component,
    "persistence": lambda: get_persistence_health(),
    "metrics": lambda: {"healthy": True, "status": "healthy", "snapshot": get_metrics_snapshot()},
    "workflow_monitor": lambda: {"healthy": True, "status": "healthy", "summary": get_workflow_summary()},
    "runtime_diagnostics": lambda: {"healthy": True, "status": "healthy", "report": get_runtime_diagnostics()},
    "deployment": _deployment_component,
}


def get_component_health(component_name: str) -> Dict[str, Any]:
    component = _COMPONENTS.get(component_name)
    if component is None:
        return ComponentHealth(
            component=component_name,
            status="unknown",
            healthy=False,
            degraded=True,
            details={"error": "unknown component"},
            checked_at=utc_now(),
        ).to_jsonable_dict()
    return _component_health(component_name, component)


def get_system_health() -> Dict[str, Any]:
    components = [get_component_health(name) for name in ("runtime", "db", "workflow_engine", "audit_service", "router_registry", "persistence")]
    healthy = sum(1 for item in components if item.get("status") == "healthy")
    degraded = sum(1 for item in components if item.get("status") == "degraded")
    unhealthy = sum(1 for item in components if item.get("status") == "unhealthy")
    overall = "healthy"
    if unhealthy:
        overall = "unhealthy"
    elif degraded:
        overall = "degraded"
    config = get_runtime_config()
    return SystemHealthSummary(
        status=overall,
        checked_at=utc_now(),
        environment=config.environment,
        production_mode=config.mode.value,
        components=components,
        healthy_components=healthy,
        degraded_components=degraded,
        unhealthy_components=unhealthy,
    ).to_jsonable_dict()
