from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.clean_ink_extraction_v3 import (
    DEFAULT_OUTPUT_ROOT,
    extract_clean_ink_from_latest_sample,
    extract_clean_ink_v3,
)

router = APIRouter(prefix="/clean-ink-v3", tags=["Clean Ink Extraction V3"])


class CleanInkExtractRequest(BaseModel):
    input_path: str = Field(..., description="Path to handwriting sample image")
    job_id: Optional[str] = Field(default=None, description="Optional job ID")
    sensitivity: int = Field(default=38, ge=20, le=70)
    crop_padding: int = Field(default=14, ge=0, le=120)
    max_side: int = Field(default=2600, ge=600, le=6000)


class CleanInkLatestRequest(BaseModel):
    sample_dir: str = Field(default="runtime/handwriting_simulation")
    job_id: Optional[str] = None
    sensitivity: int = Field(default=38, ge=20, le=70)


@router.get("/status")
def clean_ink_v3_status():
    output_root = Path(DEFAULT_OUTPUT_ROOT)
    output_root.mkdir(parents=True, exist_ok=True)

    jobs = sorted([p.name for p in output_root.iterdir() if p.is_dir()])[-20:]

    return {
        "status": "ok",
        "engine": "LMCP Clean Ink Extraction V3",
        "output_root": str(output_root),
        "recent_jobs": jobs,
    }


@router.post("/extract")
def clean_ink_v3_extract(payload: CleanInkExtractRequest):
    try:
        return extract_clean_ink_v3(
            payload.input_path,
            job_id=payload.job_id,
            sensitivity=payload.sensitivity,
            crop_padding=payload.crop_padding,
            max_side=payload.max_side,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/extract-latest")
def clean_ink_v3_extract_latest(payload: CleanInkLatestRequest):
    try:
        return extract_clean_ink_from_latest_sample(
            sample_dir=payload.sample_dir,
            job_id=payload.job_id,
            sensitivity=payload.sensitivity,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
