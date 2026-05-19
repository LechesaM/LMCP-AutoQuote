from __future__ import annotations

from typing import List

from pydantic import Field

from app.domain.base import StrictBaseModel


class QuotePackArtifact(StrictBaseModel):
    artifact_type: str
    path: str = ""
    present: bool = False


class BuyerPricingScheduleCompletion(StrictBaseModel):
    completed_buyer_schedule_path: str = ""
    completed: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    completion_score: float = 0.0
    warnings: List[str] = Field(default_factory=list)


class QuotePack(StrictBaseModel):
    tender_id: str
    company_name: str = ""
    company_contact_person: str = ""
    company_email: str = ""
    company_phone: str = ""
    buyer_name: str = ""
    tender_reference: str = ""
    pricing_schedule_path: str = ""
    generated_pdf_path: str = ""
    generated_json_path: str = ""
    completed_buyer_schedule_path: str = ""
    manifest_path: str = ""
    validity_days: int = 0
    delivery_terms: str = ""
    vat_treatment: str = ""
    quote_pack_ready: bool = False
    company_details_present: bool = False
    buyer_details_present: bool = False
    tender_reference_present: bool = False
    pricing_schedule_present: bool = False
    vat_treatment_shown: bool = False
    validity_period_present: bool = False
    delivery_terms_present: bool = False
    signature_placeholder_present: bool = False
    missing_artifacts: List[str] = Field(default_factory=list)
    artifacts: List[QuotePackArtifact] = Field(default_factory=list)
    quality_score: float = 0.0
    quality_notes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
