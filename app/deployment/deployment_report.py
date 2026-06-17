from __future__ import annotations

from typing import Any

from .environment_validator import validate_environment
from .runtime_integrity import run_integrity_checks
from .startup_validator import validate_startup
from app.core.runtime_paths import RuntimePaths


def build_deployment_report(*, paths: RuntimePaths | None = None) -> dict[str, Any]:
    environment = validate_environment(paths=paths)
    startup = validate_startup(paths=paths, allow_degraded_startup=True)
    integrity = run_integrity_checks(paths=paths)
    status = "healthy"
    if environment["status"] != "healthy" or integrity["status"] != "healthy":
        status = "degraded"
    if startup["status"] == "unhealthy":
        status = "unhealthy"
    return {
        "status": status,
        "environment": environment,
        "startup": startup,
        "integrity": integrity,
    }


def render_deployment_report_text(report: dict[str, Any]) -> str:
    return (
        f"Deployment status: {report.get('status', 'unknown')}\n"
        f"Environment: {report.get('environment', {}).get('status', 'unknown')}\n"
        f"Startup: {report.get('startup', {}).get('status', 'unknown')}\n"
        f"Integrity: {report.get('integrity', {}).get('status', 'unknown')}\n"
    )
