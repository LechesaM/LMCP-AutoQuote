from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class ComplianceDocument(Base):
    __tablename__ = "compliance_documents"
    __table_args__ = (
        UniqueConstraint("document_code", name="uq_compliance_document_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_code = Column(String(100), nullable=False, index=True)
    document_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    expiry_date = Column(String(50), nullable=True)
    status = Column(String(50), default="valid", nullable=False)
    notes = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OpportunityComplianceRequirement(Base):
    __tablename__ = "opportunity_compliance_requirements"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "document_code", name="uq_opp_compliance_requirement"),
    )

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)
    document_code = Column(String(100), nullable=False, index=True)
    required = Column(Boolean, default=True, nullable=False)
    detected = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OpportunityComplianceFile(Base):
    __tablename__ = "opportunity_compliance_files"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "document_code", name="uq_opp_compliance_file"),
    )

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False, index=True)
    document_code = Column(String(100), nullable=False, index=True)
    master_document_id = Column(Integer, ForeignKey("compliance_documents.id"), nullable=True)
    attached_file_path = Column(String(500), nullable=True)
    status = Column(String(50), default="attached", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
