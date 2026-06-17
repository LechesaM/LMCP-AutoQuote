from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(100), nullable=False, default="manual")
    source_url = Column(Text, nullable=True)

    tender_number = Column(String(255), nullable=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    buyer = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    province = Column(String(100), nullable=True)

    published_at = Column(DateTime, nullable=True)
    closing_at = Column(DateTime, nullable=True)

    submission_method = Column(String(100), nullable=True)
    submission_email = Column(String(255), nullable=True)
    submission_instructions = Column(Text, nullable=True)

    is_relevant = Column(Boolean, default=True)
    relevance_score = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    quote_drafts = relationship(
        "QuoteDraft",
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )
    submissions = relationship(
        "SubmissionRecord",
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )


class QuoteDraft(Base):
    __tablename__ = "quote_drafts"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    quote_number = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(50), nullable=False, default="draft")

    subtotal = Column(Float, default=0.0)
    vat = Column(Float, default=0.0)
    total = Column(Float, default=0.0)

    pdf_path = Column(Text, nullable=True)
    docx_path = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    opportunity = relationship("Opportunity", back_populates="quote_drafts")
    line_items = relationship(
        "QuoteLineItem",
        back_populates="quote_draft",
        cascade="all, delete-orphan",
    )
    submissions = relationship(
        "SubmissionRecord",
        back_populates="quote_draft",
        cascade="all, delete-orphan",
    )


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id = Column(Integer, primary_key=True, index=True)
    quote_draft_id = Column(Integer, ForeignKey("quote_drafts.id"), nullable=False, index=True)

    line_no = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=False)
    unit = Column(String(50), nullable=True, default="item")
    quantity = Column(Float, default=1.0)
    unit_cost = Column(Float, default=0.0)
    markup_percent = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    line_total = Column(Float, default=0.0)

    quote_draft = relationship("QuoteDraft", back_populates="line_items")


class SupplierItem(Base):
    __tablename__ = "supplier_items"

    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String(255), nullable=False)
    item_name = Column(Text, nullable=False)
    item_code = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True, default="item")
    unit_cost = Column(Float, default=0.0)
    available_qty = Column(Float, default=0.0)
    lead_time_days = Column(Integer, default=0)
    brand = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class MarkupRule(Base):
    __tablename__ = "markup_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    min_value = Column(Float, default=0.0)
    max_value = Column(Float, nullable=True)
    markup_percent = Column(Float, default=15.0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class SubmissionRecord(Base):
    __tablename__ = "submission_records"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)
    quote_draft_id = Column(Integer, ForeignKey("quote_drafts.id"), nullable=False, index=True)

    recipient_email = Column(String(255), nullable=False)
    cc_email = Column(Text, nullable=True)
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    attachment_path = Column(Text, nullable=False)

    status = Column(String(50), nullable=False, default="pending")
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    message_id = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    opportunity = relationship("Opportunity", back_populates="submissions")
    quote_draft = relationship("QuoteDraft", back_populates="submissions")
