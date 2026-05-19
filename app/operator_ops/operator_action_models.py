from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now


class OperatorActionRequest(StrictBaseModel):
    operator_id: str
    tender_id: str = ""
    action: str = ""
    note: str = ""
    target_type: str = "rfq"
    details: Dict[str, Any] = Field(default_factory=dict)


class OperatorActionRecord(StrictBaseModel):
    action_id: str
    action: str
    operator_id: str
    tender_id: str = ""
    target_type: str = "rfq"
    note: str = ""
    status: str = "queued_for_manual_followup"
    reversible: bool = True
    reviewable: bool = True
    audit_event_id: str = ""
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)
    details: Dict[str, Any] = Field(default_factory=dict)


class OperatorAssignmentRecord(StrictBaseModel):
    assignment_id: str
    operator_id: str
    tender_id: str
    status: str = "assigned"
    priority: int = 0
    assigned_at: Any = Field(default_factory=utc_now)
    due_at: Optional[datetime] = None
    workload: int = 0
    recommendation: str = "manual"
    source: str = "runtime"
    details: Dict[str, Any] = Field(default_factory=dict)


class OperatorNotificationRecord(StrictBaseModel):
    notification_id: str
    type: str = "info"
    severity: str = "info"
    title: str = ""
    message: str = ""
    tender_id: str = ""
    operator_id: str = ""
    acknowledged: bool = False
    created_at: Any = Field(default_factory=utc_now)
    details: Dict[str, Any] = Field(default_factory=dict)


class OperatorTimelineEvent(StrictBaseModel):
    event_id: str
    event_type: str
    operator_id: str = ""
    tender_id: str = ""
    title: str = ""
    severity: str = "info"
    reversible: bool = True
    reviewable: bool = True
    created_at: Any = Field(default_factory=utc_now)
    details: Dict[str, Any] = Field(default_factory=dict)


class OperatorCapacitySnapshot(StrictBaseModel):
    team_size: int = 10
    per_operator_daily_capacity: int = 100
    total_daily_capacity: int = 1000
    assigned_today: int = 0
    remaining_capacity: int = 1000
    overloaded: bool = False
    recommended_load: int = 0
    generated_at: Any = Field(default_factory=utc_now)
    status: str = "ok"


def new_operator_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"
