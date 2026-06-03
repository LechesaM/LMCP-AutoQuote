from __future__ import annotations

from typing import Any, Dict, List

from app.config import settings
from app.api.router_registry import iter_router_specs
from app.core import workflow_state_engine
from app.persistence import db as persistence_db
from app.persistence.repositories import get_persistence_health
from app.services import audit_trail_service


def get_system_health() -> Dict[str, Any]:
    runtime_root = settings.runtime_dir
    components: List[Dict[str, Any]] = [
        {"component": "runtime", "status": "healthy", "details": {"runtime_root": str(runtime_root)}},
        {
            "component": "db",
            "status": "healthy" if persistence_db.database_connection_ready() else "degraded",
            "details": {"db_file_present": settings.operator_auth_db_path.exists()},
        },
        {"component": "workflow_engine", "status": "healthy", "details": {"states": len(workflow_state_engine._STATE_BY_FILE.get(str(workflow_state_engine.WORKFLOW_STATE_LOG_FILE), {}))}},
        {"component": "audit_service", "status": "healthy", "details": {"audit_file_present": audit_trail_service.AUDIT_FILE.exists()}},
        {"component": "router_registry", "status": "healthy", "details": {"routers": len(list(iter_router_specs()))}},
        {"component": "persistence", "status": get_persistence_health().get("status", "healthy"), "details": get_persistence_health()},
    ]
    status = "healthy" if all(item["status"] == "healthy" for item in components) else "degraded"
    return {"status": status, "components": components}
