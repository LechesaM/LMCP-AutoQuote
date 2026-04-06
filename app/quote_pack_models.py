from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Numeric,
    Enum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class QuoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT = "SENT"


class QuotePack(Base):
    __tablename__ = "quote_packs"

    id = Column(Integer, primary_key=True, index=True)
    quote_number = Column(String(100), unique=True, nullable=False, index=True)

    client_name = Column(String(255), nullable=False)
    client_email = Column(String(255), nullable=True)
    client_phone = Column(String(100), nullable=True)
    client_address = Column(Text, nullable=True)

    project_title = Column(String(255), nullable=False)
    rfq_reference = Column(String(255), nullable=True)
    currency = Column(String(10), nullable=False, default="ZAR")

    company_name = Column(
        String(255),
        nullable=False,
        default="Lechesa Manaba Consulting and Projects (Pty) Ltd",
    )
    company_registration = Column(String(100), nullable=True)
    company_vat_number = Column(String(100), nullable=True)
    company_email = Column(String(255), nullable=True)
    company_phone = Column(String(100), nullable=True)
    company_address = Column(Text, nullable=True)

    validity_days = Column(Integer, nullable=False, default=30)
    issue_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)

    subtotal = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    vat_rate = Column(Numeric(8, 4), nullable=False, default=Decimal("0.15"))
    vat_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    notes = Column(Text, nullable=True)
    terms_and_conditions = Column(Text, nullable=True)

    status = Column(Enum(QuoteStatus), nullable=False, default=QuoteStatus.DRAFT)

    docx_path = Column(Text, nullable=True)
    pdf_path = Column(Text, nullable=True)

    created_by = Column(String(255), nullable=True)
    approved_by = Column(String(255), nullable=True)
    rejected_by = Column(String(255), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    items = relationship(
        "QuotePackItem",
        back_populates="quote_pack",
        cascade="all, delete-orphan",
        order_by="QuotePackItem.item_no",
    )

    history = relationship(
        "QuotePackStatusHistory",
        back_populates="quote_pack",
        cascade="all, delete-orphan",
        order_by="QuotePackStatusHistory.id",
    )


class QuotePackItem(Base):
    __tablename__ = "quote_pack_items"

    id = Column(Integer, primary_key=True, index=True)
    quote_pack_id = Column(Integer, ForeignKey("quote_packs.id"), nullable=False, index=True)

    item_no = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=False)
    unit = Column(String(50), nullable=False, default="each")
    quantity = Column(Numeric(18, 2), nullable=False, default=Decimal("1.00"))
    unit_price = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    line_total = Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    quote_pack = relationship("QuotePack", back_populates="items")


class QuotePackStatusHistory(Base):
    __tablename__ = "quote_pack_status_history"

    id = Column(Integer, primary_key=True, index=True)
    quote_pack_id = Column(Integer, ForeignKey("quote_packs.id"), nullable=False, index=True)

    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    action_by = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    quote_pack = relationship("QuotePack", back_populates="history")

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List


class QuotePackLineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_no: int = Field(..., description="Line number")
    description: str = Field(..., description="Item description")
    quantity: float = Field(1.0, description="Quantity")
    unit: str = Field("Item", description="Unit of measure")
    unit_price: float = Field(0.0, description="Unit price in ZAR")
    total_price: float = Field(0.0, description="Total price in ZAR")
    notes: Optional[str] = Field(None, description="Optional line note")


class QuotePackCompanyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_name: str = Field("Lechesa Manaba Consulting and Projects (Pty) Ltd")
    registration_number: Optional[str] = Field(None)
    vat_number: Optional[str] = Field(None)
    contact_person: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    address: Optional[str] = Field(None)


class QuotePackRFQInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rfq_id: Optional[str] = None
    tender_number: Optional[str] = None
    title: str = Field(..., description="Tender title")
    description: Optional[str] = None
    issuing_entity: Optional[str] = None
    province: Optional[str] = None
    closing_date: Optional[str] = None
    briefing_required: Optional[bool] = None
    source_url: Optional[str] = None
    delivery_location: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None


class QuotePackPricingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtotal: float = 0.0
    vat_amount: float = 0.0
    total_including_vat: float = 0.0
    margin_percent: float = 25.0
    currency: str = "ZAR"


class QuotePackPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pack_id: str
    prepared_at: datetime
    rfq: QuotePackRFQInfo
    company: QuotePackCompanyInfo
    line_items: List[QuotePackLineItem]
    pricing: QuotePackPricingSummary
    validity_days: int = 30
    delivery_period_days: Optional[int] = None
    payment_terms: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    prepared_by: Optional[str] = None


class AutoQuotePipelineRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rfq_data: Dict[str, Any]
    company_data: Optional[Dict[str, Any]] = None
    recipient_email: str
    cc_email: Optional[str] = None
    margin_percent: float = Field(25.0, ge=0.0, le=100.0)
    include_docx: bool = True
    include_pdf: bool = True
    email_subject: Optional[str] = None
    email_body: Optional[str] = None


class AutoQuotePipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    message: str
    quote_pack_id: Optional[str] = None
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
    email_sent: bool = False
    email_error: Optional[str] = None
    quote_summary: Dict[str, Any] = Field(default_factory=dict)


class QuotePackBuildRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rfq_data: Dict[str, Any]
    quote_data: Optional[Dict[str, Any]] = None
    company_data: Optional[Dict[str, Any]] = None
    margin_percent: float = Field(25.0, ge=0.0, le=100.0)
    include_docx: bool = True
    include_pdf: bool = True


class QuotePackBuildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    message: str
    payload: QuotePackPayload
    output_dir: str
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None
