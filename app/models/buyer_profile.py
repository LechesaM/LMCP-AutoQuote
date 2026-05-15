from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"

    id = Column(Integer, primary_key=True, index=True)

    buyer_code = Column(String(255), unique=True, index=True, nullable=False)
    buyer_name = Column(String(500), nullable=False)
    buyer_type = Column(String(100), nullable=True)
    province = Column(String(100), nullable=True)

    event_count = Column(Integer, default=0, nullable=False)

    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)

    avg_days_between_buys = Column(Float, nullable=True)

    top_categories_json = Column(Text, nullable=True)
    predicted_next_buy_window_json = Column(Text, nullable=True)

    procurement_frequency_score = Column(Float, default=0.0, nullable=False)
    repeat_buying_score = Column(Float, default=0.0, nullable=False)
    buyer_activity_score = Column(Float, default=0.0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
