from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.universal_form_filler import (
    UniversalFormFiller,
    build_lmcp_default_form_data,
    UniversalFormFillerError,
)

router = APIRouter(prefix="/forms", tags=["Universal Form Filler"])


class FillFormRequest(BaseModel):
    input_path: str = Field(..., description="Path to source form (.pdf/.docx/.xlsx)")
    output_basename: Optional[str] = Field(default=None, description="Base filename for output")
    profile_name: Optional[str] = Field(default=None, description="Optional JSON profile for non-editable PDFs")
    signature_path: Optional[str] = Field(default=None, description="Optional signature image path")
    convert_to_pdf: bool = Field(default=True, description="Convert DOCX/XLSX output to PDF")
    tender_data: Dict[str, Any] = Field(default_factory=dict)
    company_data: Dict[str, Any] = Field(default_factory=dict)
    director_data: Dict[str, Any] = Field(default_factory=dict)
    extra_data: Dict[str, Any] = Field(default_factory=dict)


@router.post("/fill")
def fill_form(request: FillFormRequest):
    try:
        input_file = Path(request.input_path)
        if not input_file.exists():
            raise HTTPException(status_code=404, detail=f"Input file not found: {request.input_path}")

        filler = UniversalFormFiller()

        merged_data = build_lmcp_default_form_data(
            tender_data=request.tender_data,
            company_data=request.company_data,
            director_data=request.director_data,
        )
        merged_data.update(request.extra_data)

        result = filler.fill_form(
            input_path=request.input_path,
            data=merged_data,
            output_basename=request.output_basename,
            profile_name=request.profile_name,
            signature_path=request.signature_path,
            convert_to_pdf=request.convert_to_pdf,
        )
        return result

    except UniversalFormFillerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}") from exc
