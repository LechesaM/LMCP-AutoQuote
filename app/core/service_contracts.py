from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ServiceStatus(str, Enum):
    PRODUCTION = "production"
    LEGACY = "legacy"
    DEPRECATED = "deprecated"


@dataclass
class FailureBlocker:
    code: str
    message: str
    field: str = ""

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationErrorDetail:
    field: str
    message: str
    value: Any = None

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OperationResult:
    service_name: str
    status: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    blockers: List[FailureBlocker] = field(default_factory=list)
    errors: List[ValidationErrorDetail] = field(default_factory=list)

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "status": self.status,
            "message": self.message,
            "data": dict(self.data or {}),
            "blockers": [item.to_jsonable_dict() for item in self.blockers],
            "errors": [item.to_jsonable_dict() for item in self.errors],
        }


@dataclass
class ServiceResponse:
    service_name: str
    ok: bool
    result: OperationResult
    data: Dict[str, Any] = field(default_factory=dict)
    blockers: List[FailureBlocker] = field(default_factory=list)
    errors: List[ValidationErrorDetail] = field(default_factory=list)

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "ok": self.ok,
            "result": self.result.to_jsonable_dict(),
            "data": dict(self.data or {}),
            "blockers": [item.to_jsonable_dict() for item in self.blockers],
            "errors": [item.to_jsonable_dict() for item in self.errors],
        }
