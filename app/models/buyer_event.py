from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class BuyerEvent(Base):
    __tablename__ = "buyer_events"

    id = Column(Integer, primary_key=True, index=True)

    buyer_code = Column(String(255), index=True, nullable=False)
    buyer_name_raw = Column(String(500), nullable=True)
    buyer_name_normalized = Column(String(500), index=True, nullable=False)

    buyer_type = Column(String(100), nullable=True)
    province = Column(String(100), nullable=True)
    portal_source = Column(String(255), nullable=True)

    title = Column(String(1000), nullable=False)
    description = Column(Text, nullable=True)

    category = Column(String(255), index=True, nullable=False)
    subcategory = Column(String(255), nullable=True)
    notice_type = Column(String(100), nullable=True)

    published_at = Column(DateTime, nullable=True)
    closing_at = Column(DateTime, nullable=True)

    estimated_value = Column(Float, nullable=True)
    currency = Column(String(20), nullable=True, default="ZAR")

    source_url = Column(String(2000), nullable=True)
    source_hash = Column(String(255), unique=True, index=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
