from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .service_contracts import ServiceStatus


@dataclass(frozen=True)
class ServiceRecord:
    name: str
    module: str
    status: ServiceStatus


SERVICE_REGISTRY = [
    ServiceRecord("manual_approval_service", "app.services.manual_approval_service", ServiceStatus.PRODUCTION),
    ServiceRecord("submission_review_service", "app.services.submission_review_service", ServiceStatus.PRODUCTION),
    ServiceRecord("immutable_submission_lock_service", "app.services.immutable_submission_lock_service", ServiceStatus.PRODUCTION),
    ServiceRecord("controlled_validation_service", "app.services.controlled_validation_service", ServiceStatus.PRODUCTION),
    ServiceRecord("legacy_submission_service", "app.services.auto_submission_v46_service", ServiceStatus.LEGACY),
    ServiceRecord("deprecated_portal_submission_service", "app.services.portal_submission_service", ServiceStatus.DEPRECATED),
]

_INDEX: Dict[str, ServiceRecord] = {}
for record in SERVICE_REGISTRY:
    _INDEX[record.name] = record
    _INDEX[record.module] = record


def validate_unique_service_names() -> None:
    names = [record.name for record in SERVICE_REGISTRY]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate service names detected.")


def get_service(name: str) -> Optional[ServiceRecord]:
    return _INDEX.get(name)


def get_production_services() -> List[ServiceRecord]:
    return [record for record in SERVICE_REGISTRY if record.status is ServiceStatus.PRODUCTION]


def get_legacy_services() -> List[ServiceRecord]:
    return [record for record in SERVICE_REGISTRY if record.status in {ServiceStatus.LEGACY, ServiceStatus.DEPRECATED}]
