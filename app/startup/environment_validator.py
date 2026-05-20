from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.auth.rbac import ROLE_PERMISSIONS, permissions_for_role
from app.config import settings
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.deployment.environment_validator import validate_environment as validate_deployment_environment
from app.persistence.db import get_database_path, safe_initialize_database
from app.persistence.postgres_config import get_postgres_config, postgres_connection_ready
from app.api.router_registry import iter_router_specs


REQUIRED_ENV_VARS = (
    "LMCP_PROJECT_ROOT",
    "LMCP_RUNTIME_DIR",
    "LMCP_MANUAL_PRODUCTION_DIR",
    "LMCP_MANUAL_PRODUCTION_DB_PATH",
    "LMCP_SECRET_KEY",
    "LMCP_DB_BACKEND",
    "LMCP_QUEUE_BACKEND",
    "STRICT_PRODUCTION_STARTUP",
)

EXPECTED_TELEMETRY_ROUTERS = (
    "telemetry_router",
    "observability_router",
    "operations_runtime_router",
    "persistence_ops_router",
    "operator_ops_router",
    "operator_productivity_router",
    "business_intelligence_router",
    "governance_router",
    "stabilization_router",
)

NGINX_EXPECTATIONS = (
    "location ~ ^/(api|auth|operations|observability|persistence|queue|operator|telemetry)/",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Permissions-Policy",
)

PLACEHOLDER_SECRETS = {"", "change-me", "lmcp-dev-secret", "please-change-me", "replace-me"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_bool(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in {"0", "false", "no", "off", "none"}


def _check_writable(path: Path) -> Dict[str, Any]:
    path = Path(path)
    result = {"path": str(path), "exists": path.exists(), "writable": False, "status": "failing"}
    if not path.exists() or not path.is_dir():
        result["error"] = "Path is missing or not a directory."
        return result
    marker = path / f".startup-write-check-{os.getpid()}"
    try:
        marker.write_text("ok", encoding="utf-8")
        result["writable"] = True
        result["status"] = "healthy"
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        try:
            if marker.exists():
                marker.unlink()
        except Exception:
            pass
    return result


def _router_names(include_legacy: bool = False) -> List[str]:
    return [spec.name for spec in iter_router_specs(include_legacy=include_legacy)]


def validate_environment() -> Dict[str, Any]:
    runtime = get_runtime_config()
    runtime_paths = get_runtime_paths()
    base_report = validate_deployment_environment(paths=runtime_paths)
    issues: List[Dict[str, Any]] = list(base_report.get("issues", []))
    warnings: List[str] = []
    blockers: List[str] = []

    env_snapshot = {name: str(os.environ.get(name, "") or "").strip() for name in REQUIRED_ENV_VARS}
    missing_env_vars = [name for name, value in env_snapshot.items() if not value]
    if missing_env_vars:
        warnings.append(f"Missing explicit environment variables: {', '.join(missing_env_vars)}")

    secret_key = settings.secret_key
    if secret_key in PLACEHOLDER_SECRETS or len(secret_key) < 16:
        blockers.append("JWT/secret key is missing or still using a placeholder value.")

    writable_targets = [
        runtime_paths.runtime_root,
        runtime_paths.manual_production_dir,
        runtime_paths.logs_dir,
        runtime_paths.backups_dir,
        runtime_paths.health_dir,
        runtime_paths.exports_dir,
        runtime_paths.operator_auth_dir,
    ]
    writable_checks = [_check_writable(path) for path in writable_targets]
    for check in writable_checks:
        if not check.get("writable"):
            blockers.append(f"Path is not writable: {check['path']}")

    db_path = get_database_path()
    db_ok = safe_initialize_database() and db_path.exists()
    if not db_ok:
        blockers.append("Database connectivity or initialization failed.")

    postgres = get_postgres_config()
    postgres_ready = postgres_connection_ready()
    if runtime.mode.value in {"production", "supervised_live"} and postgres.backend == "postgres" and not postgres_ready:
        blockers.append("PostgreSQL backend is configured but not ready.")

    nginx_path = runtime.project_root / "nginx" / "default.conf"
    nginx_text = ""
    nginx_matches = []
    if nginx_path.exists():
        nginx_text = nginx_path.read_text(encoding="utf-8", errors="ignore")
        nginx_matches = [needle for needle in NGINX_EXPECTATIONS if needle in nginx_text]
        if len(nginx_matches) != len(NGINX_EXPECTATIONS):
            blockers.append("nginx/default.conf is missing required production proxy or security directives.")
    else:
        blockers.append("nginx/default.conf is missing.")

    frontend_index = runtime.project_root / "frontend" / "command-centre" / "dist" / "index.html"
    frontend_assets_dir = frontend_index.parent / "assets"
    frontend_assets = list(frontend_assets_dir.glob("*.js")) if frontend_assets_dir.exists() else []
    if not frontend_index.exists() or not frontend_assets:
        blockers.append("Frontend production assets are missing or incomplete.")

    router_names = _router_names(include_legacy=False)
    missing_routers = [name for name in EXPECTED_TELEMETRY_ROUTERS if name not in router_names]
    if missing_routers:
        blockers.append(f"Critical telemetry or operational routers are missing: {', '.join(missing_routers)}")

    duplicate_router_names = sorted(name for name in router_names if router_names.count(name) > 1)
    if duplicate_router_names:
        blockers.append(f"Duplicate router names detected: {', '.join(sorted(set(duplicate_router_names)))}")

    rbac_permissions = {role: tuple(permissions_for_role(role)) for role in ROLE_PERMISSIONS}
    if any(not permissions for permissions in rbac_permissions.values()):
        blockers.append("RBAC initialization returned an empty permission set for one or more roles.")

    prohibited_permissions = {"autonomous_submit", "auto_approve", "bypass_review_ready", "bypass_proof_capture"}
    for role, permissions in rbac_permissions.items():
        if prohibited_permissions.intersection(permissions):
            blockers.append(f"Prohibited permissions detected in RBAC role '{role}'.")
            break

    status = "healthy"
    if blockers:
        status = "failing"
    elif warnings or missing_env_vars or not _safe_bool(runtime.strict_production_startup):
        status = "degraded"

    return {
        "status": status,
        "generated_at": _now_iso(),
        "strict_production_startup": runtime.strict_production_startup,
        "runtime_mode": runtime.mode.value,
        "environment": runtime.environment,
        "required_env_vars": env_snapshot,
        "missing_env_vars": missing_env_vars,
        "jwt_secret": {
            "present": secret_key not in PLACEHOLDER_SECRETS,
            "length": len(secret_key),
        },
        "database": {
            "path": str(db_path),
            "available": db_ok,
            "backend": postgres.backend,
            "postgres_configured": postgres.configured,
            "postgres_ready": postgres_ready,
        },
        "writable_paths": writable_checks,
        "nginx": {
            "path": str(nginx_path),
            "present": nginx_path.exists(),
            "matched_expectations": nginx_matches,
            "expected_count": len(NGINX_EXPECTATIONS),
        },
        "frontend_assets": {
            "index_path": str(frontend_index),
            "present": frontend_index.exists(),
            "asset_count": len(frontend_assets),
        },
        "telemetry_endpoints": {
            "routers": router_names,
            "expected_routers": list(EXPECTED_TELEMETRY_ROUTERS),
            "missing_routers": missing_routers,
        },
        "rbac": {
            "roles": sorted(rbac_permissions),
            "permissions_by_role": {role: list(permissions) for role, permissions in rbac_permissions.items()},
        },
        "warnings": warnings,
        "blockers": blockers,
        "deployment_environment": base_report,
        "routes_present": router_names,
        "router_integrity": {
            "duplicate_router_names": sorted(set(duplicate_router_names)),
            "router_count": len(router_names),
        },
        "database_connectivity": {
            "sqlite_ready": db_ok,
            "postgres_ready": postgres_ready,
        },
        "runtime_paths": {
            "runtime_root": str(runtime_paths.runtime_root),
            "manual_production_dir": str(runtime_paths.manual_production_dir),
            "backups_dir": str(runtime_paths.backups_dir),
            "health_dir": str(runtime_paths.health_dir),
            "exports_dir": str(runtime_paths.exports_dir),
        },
    }


def get_environment_summary() -> Dict[str, Any]:
    return validate_environment()
