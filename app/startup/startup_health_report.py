from __future__ import annotations

import os
from typing import Any

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.deployment.environment_validator import validate_environment
from app.deployment.startup_validator import validate_startup


def build_startup_health_report() -> dict[str, Any]:
    config = get_runtime_config()
    paths = get_runtime_paths()
    environment = validate_environment(paths=paths)
    startup_validation = validate_startup(paths=paths, allow_degraded_startup=config.allow_degraded_startup)
    strict = os.getenv("STRICT_PRODUCTION_STARTUP", "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    blockers = []
    if strict and os.getenv("LMCP_SECRET_KEY", "").strip() in {"", "change-me", "lmcp-dev-secret"}:
        blockers.append({"code": "placeholder_secret_key"})
    production_blockers = {"fail_loudly": bool(blockers), "items": blockers}
    return {
        "environment": environment,
        "dependencies": {"status": "healthy"},
        "startup_validation": startup_validation,
        "production_blockers": production_blockers,
        "blockers": blockers,
        "warnings": [],
        "strict_production_startup": strict,
    }
