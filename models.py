from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)

    ocid = Column(String, unique=True, index=True, nullable=False)

    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    buyer = Column(String, nullable=True)

    contact_email = Column(String, nullable=True, index=True)

    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
