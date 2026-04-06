# app/db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://autoquote:autoquote@db:5432/autoquote"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ✅ FastAPI dependency
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
