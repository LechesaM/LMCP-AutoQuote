from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now


class ServiceStatus(str, Enum):
    PRODUCTION = "production"
    LEGACY = "legacy"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


class FailureBlocker(StrictBaseModel):
    code: str = ""
    message: str = ""
    field: str = ""


class ValidationErrorDetail(StrictBaseModel):
    field: str = ""
    message: str = ""
    value: Any = None


class OperationResult(StrictBaseModel):
    service_name: str
    status: str = "ok"
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    blockers: List[FailureBlocker] = Field(default_factory=list)
    errors: List[ValidationErrorDetail] = Field(default_factory=list)
    created_at: Any = Field(default_factory=utc_now)


class ServiceResponse(StrictBaseModel):
    service_name: str
    ok: bool = True
    result: Optional[OperationResult] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    blockers: List[FailureBlocker] = Field(default_factory=list)
    errors: List[ValidationErrorDetail] = Field(default_factory=list)
    created_at: Any = Field(default_factory=utc_now)
