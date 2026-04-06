from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class OpportunityOut(BaseModel):
    id: int
    source: str
    source_url: Optional[str] = None
    tender_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    buyer: Optional[str] = None
    category: Optional[str] = None
    province: Optional[str] = None
    published_at: Optional[datetime] = None
    closing_at: Optional[datetime] = None
    submission_method: Optional[str] = None
    submission_email: Optional[str] = None
    submission_instructions: Optional[str] = None
    is_relevant: bool
    relevance_score: float

    class Config:
        from_attributes = True


class QuoteLineItemCreate(BaseModel):
    description: str
    unit: Optional[str] = "item"
    quantity: float = 1.0
    unit_cost: float = 0.0
    markup_percent: float = 0.0


class QuoteLineItemOut(BaseModel):
    id: int
    line_no: int
    description: str
    unit: Optional[str] = None
    quantity: float
    unit_cost: float
    markup_percent: float
    unit_price: float
    line_total: float

    class Config:
        from_attributes = True


class QuoteDraftOut(BaseModel):
    id: int
    opportunity_id: int
    quote_number: str
    status: str
    subtotal: float
    vat: float
    total: float
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    line_items: List[QuoteLineItemOut] = []

    class Config:
        from_attributes = True


class SupplierItemCreate(BaseModel):
    supplier_name: str
    item_name: str
    item_code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = "item"
    unit_cost: float = 0.0
    available_qty: float = 0.0
    lead_time_days: int = 0
    brand: Optional[str] = None
    category: Optional[str] = None


class SupplierItemOut(BaseModel):
    id: int
    supplier_name: str
    item_name: str
    item_code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    unit_cost: float
    available_qty: float
    lead_time_days: int
    brand: Optional[str] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True


class MarkupRuleCreate(BaseModel):
    name: str
    min_value: float = 0.0
    max_value: Optional[float] = None
    markup_percent: float = 15.0
    is_active: bool = True


class MarkupRuleOut(BaseModel):
    id: int
    name: str
    min_value: float
    max_value: Optional[float] = None
    markup_percent: float
    is_active: bool

    class Config:
        from_attributes = True


class SubmissionEmailRequest(BaseModel):
    quote_draft_id: int
    recipient_email: Optional[EmailStr] = None
    cc_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    auto_use_opportunity_email: bool = True


class SubmissionRecordOut(BaseModel):
    id: int
    opportunity_id: int
    quote_draft_id: int
    recipient_email: str
    cc_email: Optional[str] = None
    subject: str
    body: str
    attachment_path: str
    status: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    message_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
