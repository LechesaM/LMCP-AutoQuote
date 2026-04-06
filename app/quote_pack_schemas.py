from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.quote_pack_models import QuoteStatus


class QuotePackItemCreate(BaseModel):
    description: str = Field(..., min_length=1)
    unit: str = Field(default="each")
    quantity: Decimal = Field(default=Decimal("1.00"))
    unit_price: Decimal = Field(default=Decimal("0.00"))


class QuotePackItemResponse(BaseModel):
    id: int
    item_no: int
    description: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal

    class Config:
        orm_mode = True


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


class QuotePackHistoryResponse(BaseModel):
    id: int
    from_status: Optional[str]
    to_status: str
    action_by: Optional[str]
    comment: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class QuotePackResponse(BaseModel):
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

    class Config:
        orm_mode = True
