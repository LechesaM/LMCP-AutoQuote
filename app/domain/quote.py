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
    generated_pdf_path: str = ""
    generated_json_path: str = ""
    completed_buyer_schedule_path: str = ""
    quote_pack_ready: bool = False
    missing_artifacts: List[str] = Field(default_factory=list)
    artifacts: List[QuotePackArtifact] = Field(default_factory=list)
    quality_score: float = 0.0
    quality_notes: List[str] = Field(default_factory=list)
