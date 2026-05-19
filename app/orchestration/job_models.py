from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now


class QueueJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


class QueueJobType(str, Enum):
    RFQ_EXTRACTION = "rfq_extraction"
    PRICING = "pricing"
    QUOTE_GENERATION = "quote_generation"
    APPROVAL_TRACKING = "approval_tracking"
    SUBMISSION_REVIEW = "submission_review"
    PROOF_CAPTURE = "proof_capture"
    WORKFLOW_RECOVERY = "workflow_recovery"
    INTEGRITY_CHECK = "integrity_check"


class QueueJob(StrictBaseModel):
    job_id: str
    tender_id: str = ""
    job_type: QueueJobType
    status: QueueJobStatus = QueueJobStatus.QUEUED
    actor: str = ""
    operator: str = ""
    workflow_stage: str = ""
    attempt_count: int = 0
    max_attempts: int = 3
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


class QueueRetryRecord(StrictBaseModel):
    job_id: str
    tender_id: str = ""
    job_type: QueueJobType
    attempt_count: int = 0
    delay_seconds: int = 0
    actor: str = ""
    operator: str = ""
    reason: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)


class QueueFailureRecord(StrictBaseModel):
    job_id: str
    tender_id: str = ""
    job_type: QueueJobType
    status: QueueJobStatus = QueueJobStatus.FAILED
    actor: str = ""
    operator: str = ""
    reason: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
