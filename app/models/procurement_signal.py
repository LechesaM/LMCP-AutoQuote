from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text

from app.database import Base


class ProcurementSignal(Base):
    __tablename__ = "procurement_signals"

    id = Column(Integer, primary_key=True, index=True)

    buyer_code = Column(String(255), index=True, nullable=False)
    signal_type = Column(String(150), index=True, nullable=False)

    category = Column(String(255), index=True, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)

    reason = Column(Text, nullable=True)

    predicted_start_date = Column(Date, nullable=True)
    predicted_end_date = Column(Date, nullable=True)

    source_event_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
