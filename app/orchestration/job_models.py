from __future__ import annotations

from enum import Enum


class QueueJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    BLOCKED = "blocked"


class QueueJobType(str, Enum):
    RFQ_EXTRACTION = "rfq_extraction"
    PRICING = "pricing"
    APPROVAL_TRACKING = "approval_tracking"
    SUBMISSION_REVIEW = "submission_review"
    PROOF_CAPTURE = "proof_capture"
    WORKFLOW_RECOVERY = "workflow_recovery"
    INTEGRITY_CHECK = "integrity_check"
