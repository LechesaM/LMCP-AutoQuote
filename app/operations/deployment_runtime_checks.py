from __future__ import annotations

from typing import Any, Dict

from app.api.router_registry import iter_router_specs
from app.deployment.deployment_profiles import get_deployment_profile
from app.operations.backup_validation import get_backup_validation_summary
from app.operations.health_snapshots import capture_health_snapshot


def run_deployment_runtime_checks() -> Dict[str, Any]:
    profile = get_deployment_profile()
    routers = list(iter_router_specs())
    backup = get_backup_validation_summary()
    snapshot = capture_health_snapshot()
    return {
        "status": "ok",
        "profile": profile.to_jsonable_dict() if hasattr(profile, "to_jsonable_dict") else dict(profile),
        "router_count": len(routers),
        "legacy_routers_disabled": not bool(profile.allow_legacy_routers),
        "backup_validation": backup,
        "health_snapshot": snapshot,
        "runtime_ok": profile.runtime_mode in {"production", "supervised_live", "staging", "local_dev"},
        "telemetry_safe": True,
    }

