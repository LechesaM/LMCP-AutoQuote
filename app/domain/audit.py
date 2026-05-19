from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now
from app.domain.workflow import WorkflowStage


class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"
    CRITICAL = "critical"


class AuditActor(StrictBaseModel):
    actor_type: str = "system"
    actor_id: str = ""
    display_name: str = ""


class AuditEvent(StrictBaseModel):
    timestamp: Any = Field(default_factory=utc_now)
    actor: AuditActor = Field(default_factory=AuditActor)
    action: str
    tender_id: str = ""
    workflow_stage: Optional[WorkflowStage] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    severity: AuditSeverity = AuditSeverity.INFO
