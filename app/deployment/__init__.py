from __future__ import annotations

"""Lazy exports for deployment helpers.

This module stays lightweight so importing deployment profile/config helpers
does not recursively import startup/runtime integrity modules.
"""

from importlib import import_module
from typing import Any

_EXPORT_MAP = {
    "create_backup": ("app.deployment.backup_service", "create_backup"),
    "list_backups": ("app.deployment.backup_service", "list_backups"),
    "verify_backup": ("app.deployment.backup_service", "verify_backup"),
    "build_deployment_report": ("app.deployment.deployment_report", "build_deployment_report"),
    "render_deployment_report_text": ("app.deployment.deployment_report", "render_deployment_report_text"),
    "get_environment_summary": ("app.deployment.environment_validator", "get_environment_summary"),
    "validate_environment": ("app.deployment.environment_validator", "validate_environment"),
    "build_shutdown_snapshot": ("app.deployment.graceful_shutdown", "build_shutdown_snapshot"),
    "run_graceful_shutdown": ("app.deployment.graceful_shutdown", "run_graceful_shutdown"),
    "get_recovery_summary": ("app.deployment.recovery_service", "get_recovery_summary"),
    "restore_backup": ("app.deployment.recovery_service", "restore_backup"),
    "validate_recovery": ("app.deployment.recovery_service", "validate_recovery"),
    "get_integrity_report": ("app.deployment.runtime_integrity", "get_integrity_report"),
    "run_integrity_checks": ("app.deployment.runtime_integrity", "run_integrity_checks"),
    "generate_startup_report": ("app.deployment.startup_validator", "generate_startup_report"),
    "validate_startup": ("app.deployment.startup_validator", "validate_startup"),
}

__all__ = sorted(_EXPORT_MAP)


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
