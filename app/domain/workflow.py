from __future__ import annotations

from enum import Enum


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

