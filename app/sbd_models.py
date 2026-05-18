from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(Integer, primary_key=True, index=True)
    legal_name = Column(String(255), nullable=False)
    trading_name = Column(String(255), nullable=True)
    registration_number = Column(String(100), nullable=True)
    vat_number = Column(String(100), nullable=True)
    csd_supplier_number = Column(String(100), nullable=True)
    tax_pin = Column(String(100), nullable=True)
    bbbee_level = Column(String(50), nullable=True)
    bbbee_expiry = Column(String(50), nullable=True)

    contact_person = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(100), nullable=True)

    physical_address = Column(Text, nullable=True)
    postal_address = Column(Text, nullable=True)

    bank_name = Column(String(255), nullable=True)
    bank_account_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(100), nullable=True)
    bank_branch_code = Column(String(50), nullable=True)
    bank_account_type = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    directors = relationship(
        "CompanyDirector",
        back_populates="company_profile",
        cascade="all, delete-orphan",
    )


class CompanyDirector(Base):
    __tablename__ = "company_directors"

    id = Column(Integer, primary_key=True, index=True)
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id"), nullable=False)

    full_name = Column(String(255), nullable=False)
    id_number = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    mobile = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    company_profile = relationship("CompanyProfile", back_populates="directors")


class TenderSBDRequirement(Base):
    __tablename__ = "tender_sbd_requirements"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "form_code", name="uq_tender_sbd_requirement"),
    )

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    form_code = Column(String(50), nullable=False, index=True)
    required = Column(Boolean, default=True, nullable=False)
    detected = Column(Boolean, default=False, nullable=False)
    source_file = Column(String(500), nullable=True)
    version = Column(String(50), nullable=True)

    status = Column(String(50), default="pending", nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SBDFieldValue(Base):
    __tablename__ = "sbd_field_values"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "form_code", "field_name", name="uq_sbd_field"),
    )

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    form_code = Column(String(50), nullable=False, index=True)
    field_name = Column(String(255), nullable=False)
    field_value = Column(Text, nullable=True)
    source = Column(String(100), default="system", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SBDTemplate(Base):
    __tablename__ = "sbd_templates"
    __table_args__ = (
        UniqueConstraint("form_code", "version", name="uq_sbd_template"),
    )

    id = Column(Integer, primary_key=True, index=True)
    form_code = Column(String(50), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SBDGeneratedFile(Base):
    __tablename__ = "sbd_generated_files"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "form_code", name="uq_sbd_generated_file"),
    )

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    form_code = Column(String(50), nullable=False, index=True)
    docx_path = Column(String(500), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    signed_status = Column(String(50), default="unsigned", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)

    check_code = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False)  # pass / warning / fail
    message = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
