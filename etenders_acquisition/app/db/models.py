from sqlalchemy import Column, Float, Text

from app.db.base import Base


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Text, primary_key=True)
    tender_id = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    department = Column(Text, nullable=True)
    province = Column(Text, nullable=True)
    closing_date = Column(Text, nullable=True)
    content_hash = Column(Text, nullable=False)
    ingested_at = Column(Float)
    updated_at = Column(Float)
    raw_json = Column(Text)


class TenderDocument(Base):
    __tablename__ = "tender_documents"

    id = Column(Text, primary_key=True)
    tender_id = Column(Text, nullable=True)
    workflow_id = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)
    filename = Column(Text, nullable=True)
    local_path = Column(Text, nullable=True)
    sha256 = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="pending")
    created_at = Column(Float)
    updated_at = Column(Float)


class BOQExtraction(Base):
    __tablename__ = "boq_extractions"

    id = Column(Text, primary_key=True)
    workflow_id = Column(Text, nullable=True)
    tender_id = Column(Text, nullable=True)
    source_document_id = Column(Text, nullable=True)
    extraction_status = Column(Text, nullable=False, default="pending")
    item_count = Column(Float, default=0)
    confidence = Column(Float, default=0)
    raw_json = Column(Text)
    created_at = Column(Float)
    updated_at = Column(Float)


class BOQItem(Base):
    __tablename__ = "boq_items"

    id = Column(Text, primary_key=True)

    extraction_id = Column(Text, nullable=True)
    workflow_id = Column(Text, nullable=True)
    tender_id = Column(Text, nullable=True)
    source_document_id = Column(Text, nullable=True)

    sheet_name = Column(Text, nullable=True)
    row_number = Column(Float, nullable=True)

    item_code = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    unit = Column(Text, nullable=True)
    quantity = Column(Float, nullable=True)

    raw_row_json = Column(Text)
    created_at = Column(Float)
