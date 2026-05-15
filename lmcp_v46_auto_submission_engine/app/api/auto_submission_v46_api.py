from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.auto_submission_v46_service import (
    get_v46_status,
    submit_from_email_draft_json,
    submit_from_pdf_workflow,
    submit_from_v45_workspace,
)

router = APIRouter(prefix="/v46-auto-submission", tags=["V46 Auto Submission Engine"])


class SubmitFromV45WorkspaceRequest(BaseModel):
    workspace_path: str
    buyer_rfq_number: Optional[str] = None
    dry_run: bool = True
    output_dir: Optional[str] = None
    allow_send: bool = False


class SubmitFromEmailDraftJsonRequest(BaseModel):
    email_draft_json: str
    buyer_rfq_number: Optional[str] = None
    dry_run: bool = True
    output_dir: Optional[str] = None
    allow_send: bool = False


class SubmitFromPdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: Optional[str] = None
    dry_run: bool = True
    output_dir: Optional[str] = None
    allow_send: bool = False
    margin_percent: float = Field(25.0, ge=1.0, le=90.0)
    minimum_profit_required: float = Field(30000.0, ge=0.0)
    apply_profit_floor: bool = True
    min_confidence: float = Field(0.35, ge=0.0, le=1.0)


@router.get("/status")
def status():
    return get_v46_status()


@router.post("/submit-from-v45-workspace")
def submit_workspace(payload: SubmitFromV45WorkspaceRequest):
    return submit_from_v45_workspace(
        workspace_path=payload.workspace_path,
        buyer_rfq_number=payload.buyer_rfq_number,
        dry_run=payload.dry_run,
        output_dir=payload.output_dir,
        allow_send=payload.allow_send,
    )


@router.post("/submit-from-email-draft-json")
def submit_email_draft(payload: SubmitFromEmailDraftJsonRequest):
    return submit_from_email_draft_json(
        email_draft_json=payload.email_draft_json,
        buyer_rfq_number=payload.buyer_rfq_number,
        dry_run=payload.dry_run,
        output_dir=payload.output_dir,
        allow_send=payload.allow_send,
    )


@router.post("/submit-from-pdf")
def submit_pdf(payload: SubmitFromPdfRequest):
    return submit_from_pdf_workflow(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        dry_run=payload.dry_run,
        output_dir=payload.output_dir,
        allow_send=payload.allow_send,
        margin_percent=payload.margin_percent,
        minimum_profit_required=payload.minimum_profit_required,
        apply_profit_floor=payload.apply_profit_floor,
        min_confidence=payload.min_confidence,
    )
