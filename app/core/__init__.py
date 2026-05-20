from __future__ import annotations

"""Lazy exports for core services.

Keeping this module lightweight avoids import-time cycles when submodules such
as `app.core.runtime_paths` are imported by persistence/queue code.
"""

from importlib import import_module
from typing import Any

_EXPORT_MAP = {
    "FailureBlocker": ("app.core.service_contracts", "FailureBlocker"),
    "OperationResult": ("app.core.service_contracts", "OperationResult"),
    "ServiceStatus": ("app.core.service_contracts", "ServiceStatus"),
    "ServiceResponse": ("app.core.service_contracts", "ServiceResponse"),
    "ValidationErrorDetail": ("app.core.service_contracts", "ValidationErrorDetail"),
    "SERVICE_REGISTRY": ("app.core.service_registry", "SERVICE_REGISTRY"),
    "ServiceRecord": ("app.core.service_registry", "ServiceRecord"),
    "get_legacy_services": ("app.core.service_registry", "get_legacy_services"),
    "get_production_services": ("app.core.service_registry", "get_production_services"),
    "get_service": ("app.core.service_registry", "get_service"),
    "validate_unique_service_names": ("app.core.service_registry", "validate_unique_service_names"),
    "archive_workflow": ("app.core.workflow_state_engine", "archive_workflow"),
    "assert_can_transition": ("app.core.workflow_state_engine", "assert_can_transition"),
    "get_current_state": ("app.core.workflow_state_engine", "get_current_state"),
    "list_recent_states": ("app.core.workflow_state_engine", "list_recent_states"),
    "record_transition": ("app.core.workflow_state_engine", "record_transition"),
    "refuse_workflow": ("app.core.workflow_state_engine", "refuse_workflow"),
    "workflow_state_engine": ("app.core.workflow_state_engine", None),
}

__all__ = sorted(_EXPORT_MAP)


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    return module if attribute_name is None else getattr(module, attribute_name)

