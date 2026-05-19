from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now


class PersistenceEntity(StrictBaseModel):
    tender_id: str = ""
    workflow_stage: str = ""
    actor: str = ""
    operator: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)

    def payload_json(self) -> Dict[str, Any]:
        return self.payload


class WorkflowStateRecord(PersistenceEntity):
    workflow_stage: str


class WorkflowEventRecord(PersistenceEntity):
    from_stage: str = ""
    to_stage: str = ""
    reason: str = ""


class ApprovalRecordEntity(PersistenceEntity):
    workflow_stage: str = "approval_required"


class SubmissionReviewEntity(PersistenceEntity):
    workflow_stage: str = "review_ready"


class SubmissionProofEntity(PersistenceEntity):
    workflow_stage: str = "proof_recorded"


class AuditEventEntity(PersistenceEntity):
    event_type: str = ""
    source: str = ""
    severity: str = ""
    quote_number: str = ""


class PricingDecisionEntity(PersistenceEntity):
    workflow_stage: str = "priced"


class QuotePackEntity(PersistenceEntity):
    workflow_stage: str = "quote_generated"


class PilotRunEntity(PersistenceEntity):
    workflow_stage: str = ""
    pilot_mode: str = ""
    run_status: str = ""


class PilotSignoffEntity(PersistenceEntity):
    workflow_stage: str = ""
    signoff_type: str = ""
    signoff_status: str = ""
