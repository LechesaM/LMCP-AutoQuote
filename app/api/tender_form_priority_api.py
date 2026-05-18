from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.tender_form_priority_engine import build_tender_submission_plan


router = APIRouter(prefix="/tender-forms", tags=["Tender Form Priority"])


class TenderFormPriorityRequest(BaseModel):
    tender_root: str = Field(..., description="Folder containing downloaded RFQ/tender pack")
    tender_id: Optional[str] = Field(default=None, description="Optional tender/RFQ identifier")
    instructions_text: Optional[str] = Field(
        default=None,
        description="Extracted instructions or advert text used to detect required forms",
    )
    mandatory_form_codes: List[str] = Field(
        default_factory=list,
        description="Explicitly mandatory form codes, e.g. ['sbd1', 'sbd4', 'pricing_schedule']",
    )
    enable_archive_extract: bool = Field(
        default=True,
        description="Whether ZIP files inside the tender pack should be extracted and scanned",
    )


@router.post("/plan")
def plan_tender_forms(request: TenderFormPriorityRequest):
    try:
        result = build_tender_submission_plan(
            tender_root=request.tender_root,
            tender_id=request.tender_id,
            instructions_text=request.instructions_text,
            mandatory_form_codes=request.mandatory_form_codes,
            enable_archive_extract=request.enable_archive_extract,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}") from exc
