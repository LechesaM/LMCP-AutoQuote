from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict


class ComplianceDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_code: str
    document_name: str
    file_path: str
    file_type: Optional[str] = None
    expiry_date: Optional[str] = None
    status: str
    notes: Optional[str] = None
class OpportunityComplianceRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int
    document_code: str
    required: bool
    detected: bool
    notes: Optional[str] = None
    status: str
class OpportunityComplianceFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int
    document_code: str
    master_document_id: Optional[int] = None
    attached_file_path: Optional[str] = None
    status: str
