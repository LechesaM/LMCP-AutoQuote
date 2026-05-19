from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel


class ApprovalRecord(StrictBaseModel):
    tender_id: str
    tender_root: str
    pricing_file: str = ""
    operator_name: str = ""
    confirm_approval: bool = False
    manual_approval_recorded: bool = False
    approved_by_operator: bool = False
    submission_ready: bool = False
    final_submission_attempted: bool = False
    quote_pack_quality_status: str = ""
    approval_blocked: bool = False
    pricing_items_unmatched: int = 0
    warnings: List[str] = Field(default_factory=list)
    gate: dict = Field(default_factory=dict)
    status: str = ""
    timestamp: str = ""


class SubmissionReview(StrictBaseModel):
    tender_id: str
    tender_root: str
    pricing_file: str = ""
    operator_name: str = ""
    submission_review_ready: bool = False
    review_blockers: List[str] = Field(default_factory=list)
    quote_pack_present: bool = False
    submission_pack_present: bool = False
    pricing_file_present: bool = False
    source_rfq_present: bool = False
    approval_record_present: bool = False
    final_submission_still_false: bool = True
    submission_ready: bool = False
    final_submission_attempted: bool = False
    approval_record: Optional[ApprovalRecord] = None
    quote_pack_path: str = ""
    submission_pack_path: str = ""
    status: str = ""
    timestamp: str = ""


class SubmissionPack(StrictBaseModel):
    tender_id: str
    submission_pack_path: str = ""
    submission_pack_present: bool = False
    submission_ready: bool = False
    missing_artifacts: List[str] = Field(default_factory=list)
    timestamp: str = ""


class SubmissionProof(StrictBaseModel):
    tender_id: str
    tender_root: str
    portal_name: str = ""
    submission_reference: str = ""
    submitted_by: str = ""
    proof_file: str = ""
    proof_file_present: bool = False
    submission_review_status: str = ""
    submission_review_ready: bool = False
    final_submission_attempted: bool = False
    manual_submission_recorded: bool = False
    blockers: List[str] = Field(default_factory=list)
    status: str = ""
    timestamp: str = ""
