from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.submission_pack_v45_service import (
    get_v45_status,
    prepare_submission_from_pdf,
    prepare_submission_from_v44_json,
    prepare_submission_from_v44_workspace,
)

router = APIRouter(prefix="/v45-submission-pack", tags=["V45 PDF Submission Pack"])


class PrepareFromV44WorkspaceRequest(BaseModel):
    workspace_path: str
    output_dir: Optional[str] = None
    company_name: str = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    create_zip: bool = True


class PrepareFromV44JsonRequest(BaseModel):
    v44_metadata_json: str
    output_dir: Optional[str] = None
    company_name: str = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    create_zip: bool = True


class PrepareFromPdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: Optional[str] = None
    output_dir: Optional[str] = None
    company_name: str = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    margin_percent: float = Field(25.0, ge=1.0, le=90.0)
    minimum_profit_required: float = Field(30000.0, ge=0.0)
    apply_profit_floor: bool = True
    min_confidence: float = Field(0.35, ge=0.0, le=1.0)
    create_zip: bool = True


@router.get("/status")
def status():
    return get_v45_status()


@router.post("/prepare-from-v44-workspace")
def prepare_from_v44_workspace(payload: PrepareFromV44WorkspaceRequest):
    return prepare_submission_from_v44_workspace(
        workspace_path=payload.workspace_path,
        output_dir=payload.output_dir,
        company_name=payload.company_name,
        create_zip=payload.create_zip,
    )


@router.post("/prepare-from-v44-json")
def prepare_from_v44_json(payload: PrepareFromV44JsonRequest):
    return prepare_submission_from_v44_json(
        v44_metadata_json=payload.v44_metadata_json,
        output_dir=payload.output_dir,
        company_name=payload.company_name,
        create_zip=payload.create_zip,
    )


@router.post("/prepare-from-pdf")
def prepare_from_pdf(payload: PrepareFromPdfRequest):
    return prepare_submission_from_pdf(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        output_dir=payload.output_dir,
        company_name=payload.company_name,
        margin_percent=payload.margin_percent,
        minimum_profit_required=payload.minimum_profit_required,
        apply_profit_floor=payload.apply_profit_floor,
        min_confidence=payload.min_confidence,
        create_zip=payload.create_zip,
    )
