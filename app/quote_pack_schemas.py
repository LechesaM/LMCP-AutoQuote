from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.quote_pack_models import QuoteStatus


class QuotePackItemCreate(BaseModel):
    description: str = Field(..., min_length=1)
    unit: str = Field(default="each")
    quantity: Decimal = Field(default=Decimal("1.00"))
    unit_price: Decimal = Field(default=Decimal("0.00"))
    supplier_cost: Decimal = Field(default=Decimal("0.00"))
    delivery_cost: Decimal = Field(default=Decimal("0.00"))
    margin_percent: Decimal = Field(default=Decimal("25.00"))
    final_quoted_price: Decimal = Field(default=Decimal("0.00"))
    buyer_row_code: Optional[str] = None
    buyer_row_text: Optional[str] = None
    notes: Optional[str] = None
    mapping_confidence: float = 0.0
    requires_manual_review: bool = False


class QuotePackItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_no: int
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    supplier_cost: Decimal
    delivery_cost: Decimal
    margin_percent: Decimal
    final_quoted_price: Decimal
    buyer_row_code: Optional[str]
    buyer_row_text: Optional[str]
    notes: Optional[str]
    mapping_confidence: float
    requires_manual_review: bool

class QuotePackCreate(BaseModel):
    client_name: str
    client_email: Optional[EmailStr] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None

    project_title: str
    rfq_reference: Optional[str] = None
    currency: str = "ZAR"

    company_name: str = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    company_registration: Optional[str] = None
    company_vat_number: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_address: Optional[str] = None

    validity_days: int = 30
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    created_by: Optional[str] = None

    items: List[QuotePackItemCreate] = []


class QuoteStatusAction(BaseModel):
    action_by: Optional[str] = None
    comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    override_validation: bool = False
    override_reason: Optional[str] = None
    reject_reason_code: Optional[str] = None


class QuotePackHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: Optional[str]
    to_status: str
    action_by: Optional[str]
    comment: Optional[str]
    created_at: datetime

class QuotePackEditAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_pack_item_id: Optional[int]
    action: str
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    operator_id: Optional[str]
    operator_name: Optional[str]
    operator_role: Optional[str]
    notes: Optional[str]
    created_at: datetime

class QuotePackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_number: str

    client_name: str
    client_email: Optional[str]
    client_phone: Optional[str]
    client_address: Optional[str]

    project_title: str
    rfq_reference: Optional[str]
    currency: str

    company_name: str
    company_registration: Optional[str]
    company_vat_number: Optional[str]
    company_email: Optional[str]
    company_phone: Optional[str]
    company_address: Optional[str]

    validity_days: int
    issue_date: datetime
    expiry_date: Optional[datetime]

    subtotal: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal

    notes: Optional[str]
    terms_and_conditions: Optional[str]
    buyer_name: Optional[str]
    province: Optional[str]
    delivery_location: Optional[str]
    closing_date_text: Optional[str]
    briefing_required: bool
    approval_required: bool
    validation_override_reason: Optional[str]
    extraction_confidence: float
    classification_confidence: float
    estimated_profit: Decimal
    estimated_margin_percent: Decimal
    extraction_payload_json: Optional[str]
    classification_payload_json: Optional[str]
    pricing_payload_json: Optional[str]
    validation_payload_json: Optional[str]
    compliance_payload_json: Optional[str]
    submission_gate_payload_json: Optional[str]

    status: QuoteStatus
    docx_path: Optional[str]
    pdf_path: Optional[str]

    created_by: Optional[str]
    approved_by: Optional[str]
    rejected_by: Optional[str]
    rejection_reason: Optional[str]

    created_at: datetime
    updated_at: datetime

    items: List[QuotePackItemResponse] = []
    history: List[QuotePackHistoryResponse] = []
    edit_audits: List[QuotePackEditAuditResponse] = []


class RFQReviewIngestRequest(BaseModel):
    rfq_data: Dict[str, Any] = Field(default_factory=dict)
    company_data: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None


class QuotePackItemUpdate(BaseModel):
    unit_price: Optional[Decimal] = None
    margin_percent: Optional[Decimal] = None
    supplier_cost: Optional[Decimal] = None
    delivery_cost: Optional[Decimal] = None
    notes: Optional[str] = None
    final_quoted_price: Optional[Decimal] = None
    requires_manual_review: Optional[bool] = None


class ComplianceChecklistBulkUpdate(BaseModel):
    status: str = Field(default="present")


class ReviewQueueExportRequest(BaseModel):
    format: str = Field(default="json")


class ComplianceChecklistItem(BaseModel):
    key: str
    label: str
    status: str
    reason: Optional[str] = None
    source: Optional[str] = None


class ComplianceChecklistUpdate(BaseModel):
    items: List[ComplianceChecklistItem]


class QuotePackReviewSummary(BaseModel):
    id: int
    quote_number: str
    project_title: str
    buyer_name: Optional[str]
    rfq_reference: Optional[str]
    status: QuoteStatus
    province: Optional[str]
    closing_date_text: Optional[str]
    briefing_required: bool
    extraction_confidence: float
    classification_confidence: float
    estimated_profit: Decimal
    estimated_margin_percent: Decimal
    validation_status: Optional[str] = None
    pricing_rows_total: int = 0
    pricing_rows_completed: int = 0
    pricing_rows_needing_review: int = 0
    suggested_total_quote: Decimal = Field(default=Decimal("0.00"))
    compliance_status: Optional[str] = None
    easiest_to_approve_rank: int = 0
    easiest_to_approve_score: float = 0.0
    next_action: Optional[str] = None
    approval_ready: bool = False


class QuotePackValidationResponse(BaseModel):
    status: str
    ready_for_approval: bool
    ready_for_submission: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
