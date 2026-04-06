from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.tender_submission_pipeline import TenderSubmissionPipeline


router = APIRouter(prefix="/tender-submission", tags=["Tender Submission Pipeline"])


class TenderSubmissionPipelineRequest(BaseModel):
    tender_root: str = Field(..., description="Folder containing downloaded RFQ/tender pack")
    tender_id: Optional[str] = Field(default=None)
    instructions_text: Optional[str] = Field(default=None)
    mandatory_form_codes: List[str] = Field(default_factory=list)
    company_data: Dict[str, Any] = Field(default_factory=dict)
    director_data: Dict[str, Any] = Field(default_factory=dict)
    tender_data: Dict[str, Any] = Field(default_factory=dict)
    signature_path: Optional[str] = Field(default=None)
    form_profile_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Map form code to profile JSON filename, e.g. {'sbd4':'example_sbd4_profile.json'}",
    )
    enable_archive_extract: bool = Field(default=True)


@router.post("/run")
def run_tender_submission_pipeline(request: TenderSubmissionPipelineRequest):
    try:
        pipeline = TenderSubmissionPipeline()
        result = pipeline.run(
            tender_root=request.tender_root,
            tender_id=request.tender_id,
            instructions_text=request.instructions_text,
            mandatory_form_codes=request.mandatory_form_codes,
            company_data=request.company_data,
            director_data=request.director_data,
            tender_data=request.tender_data,
            signature_path=request.signature_path,
            form_profile_map=request.form_profile_map,
            enable_archive_extract=request.enable_archive_extract,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}") from exc
