from __future__ import annotations

import logging
from typing import Generator
from urllib.parse import urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


logger = logging.getLogger(__name__)

Base = declarative_base()
DATABASE_URL = settings.database_url


def _mask_url(raw_url: str) -> str:
    try:
        parsed = urlparse(raw_url)
        username = parsed.username or ""
        password = parsed.password or ""
        host = parsed.hostname or ""
        auth = username
        if password:
            auth += ":***"
        netloc = f"{auth}@{host}" if auth else host
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return "<unavailable>"


logger.info("Database URL in use: %s", _mask_url(DATABASE_URL))

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import base as _base  # noqa: F401

    Base.metadata.create_all(bind=engine)


def test_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection test succeeded.")
        return True
    except Exception as exc:
        logger.exception("Database connection test failed: %s", exc)
        return False
