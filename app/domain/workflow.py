from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now


class WorkflowStage(str, Enum):
    DISCOVERED = "discovered"
    EXTRACTED = "extracted"
    EVALUATED = "evaluated"
    PRICED = "priced"
    QUOTE_GENERATED = "quote_generated"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REVIEW_READY = "review_ready"
    PROOF_RECORDED = "proof_recorded"
    REFUSED = "refused"
    ARCHIVED = "archived"


class WorkflowState(StrictBaseModel):
    tender_id: str
    stage: WorkflowStage
    updated_at: Any = Field(default_factory=utc_now)
    details: Dict[str, Any] = Field(default_factory=dict)


class WorkflowTransition(StrictBaseModel):
    tender_id: str
    from_stage: WorkflowStage
    to_stage: WorkflowStage
    transitioned_at: Any = Field(default_factory=utc_now)
    reason: str = ""


class WorkflowEvent(StrictBaseModel):
    tender_id: str
    from_stage: WorkflowStage
    to_stage: WorkflowStage
    actor: str = ""
    reason: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    transitioned_at: Any = Field(default_factory=utc_now)
