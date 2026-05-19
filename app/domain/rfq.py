from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel


class RFQDocument(StrictBaseModel):
    name: str = ""
    document_type: str = ""
    source_url: str = ""
    source_path: str = ""
    extracted_text: str = ""


class RFQLineItem(StrictBaseModel):
    line_number: int = 0
    description: str
    quantity: float = 0.0
    unit: str = ""
    unit_of_measure: str = ""
    notes: str = ""


class RFQEvaluation(StrictBaseModel):
    detected_exclusions: List[str] = Field(default_factory=list)
    eligible_for_quoting: bool = True
    extraction_confidence: float = 0.0
    extraction_notes: List[str] = Field(default_factory=list)


class RFQRecord(StrictBaseModel):
    tender_id: str
    source_url: str = ""
    source_path: str = ""
    buyer_name: str = ""
    title: str = ""
    description: str = ""
    extracted_text: str = ""
    submission_instructions: str = ""
    province: str = ""
    category: str = ""
    closing_date: Optional[datetime] = None
    compulsory_briefing_required: bool = False
    briefing_date: Optional[datetime] = None
    estimated_contract_value: float = 0.0
    estimated_profit: float = 0.0
    gross_margin_ratio: float = 0.0
    technical_validation_required: bool = False
    compliance_documents: List[str] = Field(default_factory=list)
    documents: List[RFQDocument] = Field(default_factory=list)
    line_items: List[RFQLineItem] = Field(default_factory=list)
    detected_exclusions: List[str] = Field(default_factory=list)
    eligible_for_quoting: bool = True
    extraction_confidence: float = 0.0
    extraction_notes: List[str] = Field(default_factory=list)
    extraction_quality_score: float = 0.0
    extraction_quality_notes: List[str] = Field(default_factory=list)
