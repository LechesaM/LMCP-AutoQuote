from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.portal_form_autofill_v47_1_service import (
    generate_portal_form_autofill_plan,
    get_v47_1_status,
)

router = APIRouter(prefix="/v47-portal-autofill", tags=["V47.1 Portal Form Auto-Fill"])


class GeneratePlanRequest(BaseModel):
    portal_manifest_json: str
    company_profile: Optional[Dict[str, Any]] = Field(default=None)
    output_dir: Optional[str] = None


@router.get("/status")
def status():
    return get_v47_1_status()


@router.post("/generate-plan")
def generate_plan(payload: GeneratePlanRequest):
    return generate_portal_form_autofill_plan(
        portal_manifest_json=payload.portal_manifest_json,
        company_profile=payload.company_profile,
        output_dir=payload.output_dir,
    )
