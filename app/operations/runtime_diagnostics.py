from __future__ import annotations

from typing import Any, Dict

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.monitoring.health_service import get_system_health
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence.repositories import get_persistence_health

from .runtime_metrics import get_runtime_metrics
from .structured_logging import log_runtime_diagnostic


def get_runtime_diagnostics(limit: int = 25) -> Dict[str, Any]:
    config = get_runtime_config()
    paths = get_runtime_paths()
    health = get_system_health()
    workflow = get_workflow_summary(limit=limit)
    persistence = get_persistence_health()
    metrics = get_runtime_metrics(limit=limit)

    payload = {
        "status": "ok" if str(health.get("status") or "").lower() in {"ok", "healthy"} else "degraded",
        "generated_at": metrics.get("generated_at"),
        "environment": config.environment,
        "runtime_dir": str(paths.runtime_root),
        "log_dir": str(paths.logs_dir),
        "health_dir": str(paths.health_dir),
        "system_health": health,
        "workflow_summary": workflow,
        "persistence": persistence,
        "metrics": metrics,
    }
    log_runtime_diagnostic("runtime_diagnostics", "Collected runtime diagnostics", diagnostics=payload)
    return payload
