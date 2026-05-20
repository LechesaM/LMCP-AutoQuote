from __future__ import annotations

from typing import Any, Dict, List

from app.api.router_registry import iter_router_specs
from app.core.runtime_config import get_runtime_config
from app.orchestration.queue_monitor import get_queue_summary
from app.persistence.persistence_health import validate_persistence_health

from ._shared import clamp, now_iso, safe_int


def build_deployment_stability_report(limit: int = 100) -> Dict[str, Any]:
    persistence = validate_persistence_health()
    queue = get_queue_summary(limit=limit)
    router_specs = list(iter_router_specs())
    runtime = get_runtime_config()

    route_names = {spec.name for spec in router_specs}
    blockers: List[str] = []
    warnings: List[str] = []
    if persistence.get("status") == "failing":
        blockers.append("Persistence validation is failing.")
    if safe_int(queue.get("blocked_jobs", 0), 0):
        warnings.append("Queue blocked jobs are present.")
    if runtime.mode.value in {"production", "supervised_live"} and not runtime.observability_enabled:
        blockers.append("Observability must remain enabled in supervised-live mode.")
    if runtime.enable_legacy_routers and runtime.mode.value in {"production", "supervised_live"}:
        blockers.append("Legacy routers are enabled in a production deployment.")
    if not runtime.manual_production_enforced:
        blockers.append("Manual production enforcement is disabled.")

    required_routes = {
        "auth_router": "app.api.auth_routes" in {spec.module_path for spec in router_specs},
        "telemetry_router": "app.api.telemetry_routes" in {spec.module_path for spec in router_specs},
        "stabilization_router": "app.api.stabilization_routes" in {spec.module_path for spec in router_specs},
        "observability_router": "app.api.observability_routes" in {spec.module_path for spec in router_specs},
    }
    required_route_missing = [name for name, available in required_routes.items() if not available]
    if required_route_missing:
        blockers.append(f"Missing expected routes: {', '.join(required_route_missing)}")

    score = 100.0
    score -= 20.0 if persistence.get("status") == "failing" else 0.0
    score -= min(20.0, safe_int(queue.get("blocked_jobs", 0), 0) * 5.0)
    score = clamp(score, 0.0, 100.0)

    status = "healthy"
    if blockers:
        status = "failing"
    elif warnings:
        status = "degraded"

    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "deployment_stability_score": round(score, 2),
        "startup_readiness": {
            "status": "healthy" if runtime.observability_enabled and not runtime.enable_legacy_routers else "degraded",
            "mode": runtime.mode.value,
            "manual_production_enforced": runtime.manual_production_enforced,
            "final_submission_manual_only": runtime.final_submission_manual_only,
        },
        "runtime_integrity": {
            "observability_enabled": runtime.observability_enabled,
            "legacy_routers_enabled": runtime.enable_legacy_routers,
            "runtime_safety_enabled": runtime.runtime_safety_enabled,
        },
        "environment_summary": {
            "environment": runtime.environment,
            "debug": runtime.debug,
            "log_level": runtime.log_level,
        },
        "persistence_health": persistence,
        "queue_summary": queue,
        "route_availability": required_routes,
        "route_names": sorted(route_names),
        "warnings": warnings,
        "startup_blockers": [],
        "blockers": blockers,
        "auth_available": required_routes.get("auth_router", False),
        "persistence_available": persistence.get("status") != "failing",
        "queue_available": queue.get("status") == "ok",
        "observability_available": required_routes.get("observability_router", False) and runtime.observability_enabled,
    }
