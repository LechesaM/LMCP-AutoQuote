from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.portal_submission_v47_service import (
    get_v47_status,
    prepare_portal_submission_from_pdf,
    prepare_portal_submission_from_v45_workspace,
    record_portal_submission_proof,
)

router = APIRouter(prefix="/v47-portal-submission", tags=["V47 Portal Submission Engine"])


class PrepareFromV45WorkspaceRequest(BaseModel):
    workspace_path: str
    buyer_rfq_number: Optional[str] = None
    buyer_name: Optional[str] = None
    portal_url: Optional[str] = None
    output_dir: Optional[str] = None
    require_operator_confirmation: bool = True


class PrepareFromPdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: Optional[str] = None
    buyer_name: Optional[str] = None
    portal_url: Optional[str] = None
    output_dir: Optional[str] = None
    margin_percent: float = Field(25.0, ge=1.0, le=90.0)
    minimum_profit_required: float = Field(30000.0, ge=0.0)
    apply_profit_floor: bool = True
    min_confidence: float = Field(0.35, ge=0.0, le=1.0)


class RecordProofRequest(BaseModel):
    portal_manifest_json: str
    portal_receipt_number: Optional[str] = None
    submitted_by: Optional[str] = None
    proof_files: Optional[List[str]] = None
    notes: Optional[str] = None


@router.get("/status")
def status():
    return get_v47_status()


@router.post("/prepare-from-v45-workspace")
def prepare_from_v45_workspace(payload: PrepareFromV45WorkspaceRequest):
    return prepare_portal_submission_from_v45_workspace(
        workspace_path=payload.workspace_path,
        buyer_rfq_number=payload.buyer_rfq_number,
        buyer_name=payload.buyer_name,
        portal_url=payload.portal_url,
        output_dir=payload.output_dir,
        require_operator_confirmation=payload.require_operator_confirmation,
    )


@router.post("/prepare-from-pdf")
def prepare_from_pdf(payload: PrepareFromPdfRequest):
    return prepare_portal_submission_from_pdf(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        buyer_name=payload.buyer_name,
        portal_url=payload.portal_url,
        output_dir=payload.output_dir,
        margin_percent=payload.margin_percent,
        minimum_profit_required=payload.minimum_profit_required,
        apply_profit_floor=payload.apply_profit_floor,
        min_confidence=payload.min_confidence,
    )


@router.post("/record-proof")
def record_proof(payload: RecordProofRequest):
    return record_portal_submission_proof(
        portal_manifest_json=payload.portal_manifest_json,
        portal_receipt_number=payload.portal_receipt_number,
        submitted_by=payload.submitted_by,
        proof_files=payload.proof_files,
        notes=payload.notes,
    )
