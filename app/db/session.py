# app/db/session.py

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Generator, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _is_running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True

    for path in ("/proc/1/cgroup", "/proc/self/cgroup"):
        try:
            p = Path(path)
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
                if "docker" in content or "containerd" in content or "kubepods" in content:
                    return True
        except Exception:
            pass

    return False


def _normalize_scheme(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return "postgresql://" + raw_url[len("postgres://"):]
    return raw_url


def _replace_host(raw_url: str, new_host: str) -> str:
    parsed = urlparse(raw_url)

    username = parsed.username or ""
    password = parsed.password or ""
    port = parsed.port

    auth = username
    if password:
        auth += f":{password}"

    netloc = ""
    if auth:
        netloc += f"{auth}@"
    netloc += new_host
    if port:
        netloc += f":{port}"

    rebuilt = parsed._replace(netloc=netloc)
    return urlunparse(rebuilt)


def _ensure_connect_timeout(raw_url: str, seconds: int = 10) -> str:
    parsed = urlparse(raw_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(seconds))
    rebuilt = parsed._replace(query=urlencode(query))
    return urlunparse(rebuilt)


def _mask_url(raw_url: str) -> str:
    try:
        parsed = urlparse(raw_url)
        username = parsed.username or ""
        password = parsed.password or ""
        host = parsed.hostname or ""
        port = parsed.port
        dbname = parsed.path or ""

        auth = username
        if password:
            auth += ":***"

        netloc = ""
        if auth:
            netloc += f"{auth}@"
        netloc += host
        if port:
            netloc += f":{port}"

        masked = parsed._replace(netloc=netloc, path=dbname)
        return urlunparse(masked)
    except Exception:
        return "<unavailable>"


# -----------------------------------------------------------------------------
# URL derivation
# -----------------------------------------------------------------------------

def _build_docker_url_from_env() -> Optional[str]:
    """
    Inside Docker, prefer the live POSTGRES_* / DB_* environment values instead of
    a stale DATABASE_URL that may contain the wrong password.
    """
    db_user = _env("POSTGRES_USER") or _env("DB_USER")
    db_password = _env("POSTGRES_PASSWORD") or _env("DB_PASSWORD")
    db_name = _env("POSTGRES_DB") or _env("DB_NAME")
    db_port = _env("DB_PORT", "5432")
    db_host = _env("DB_DOCKER_HOST", _env("DB_HOST", "db"))

    if db_user and db_password and db_name:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    return None


def _build_host_url_from_env() -> Optional[str]:
    """
    Outside Docker, prefer explicit local values if available.
    """
    db_user = _env("POSTGRES_USER") or _env("DB_USER")
    db_password = _env("POSTGRES_PASSWORD") or _env("DB_PASSWORD")
    db_name = _env("POSTGRES_DB") or _env("DB_NAME")
    db_port = _env("DB_PORT", "5432")
    db_host = _env("DB_LOCAL_HOST", _env("DB_HOST", "localhost"))

    if db_user and db_password and db_name:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    return None


def _derive_database_url() -> str:
    in_docker = _is_running_in_docker()

    # -------------------------------------------------------------------------
    # 1) Inside Docker: prefer discrete POSTGRES_* / DB_* vars.
    #    This avoids stale DATABASE_URL values with wrong credentials.
    # -------------------------------------------------------------------------
    if in_docker:
        docker_url = _build_docker_url_from_env()
        if docker_url:
            raw_url = docker_url
        else:
            raw_url = _env("DATABASE_URL") or _env("SQLALCHEMY_DATABASE_URL") or ""
    else:
        # ---------------------------------------------------------------------
        # 2) Outside Docker: prefer DATABASE_URL_LOCAL, then explicit local vars.
        # ---------------------------------------------------------------------
        raw_url = _env("DATABASE_URL_LOCAL") or _build_host_url_from_env() or _env("DATABASE_URL") or _env("SQLALCHEMY_DATABASE_URL") or ""

    # -------------------------------------------------------------------------
    # 3) Final fallback defaults
    # -------------------------------------------------------------------------
    if not raw_url:
        if in_docker:
            raw_url = "postgresql://postgres:postgres@db:5432/lmcp_autoquote"
        else:
            raw_url = "postgresql://postgres:postgres@localhost:5432/lmcp_autoquote"

    raw_url = _normalize_scheme(raw_url)

    parsed = urlparse(raw_url)
    current_host = (parsed.hostname or "").strip().lower()

    docker_hosts = {"postgres", "db", "database", "lmcp-db", "postgresql"}
    local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", ""}

    # Outside Docker: never keep Docker-only host aliases.
    if not in_docker and current_host in docker_hosts:
        raw_url = _replace_host(raw_url, _env("DB_LOCAL_HOST", "localhost"))

    # Inside Docker: never use localhost; normalize legacy postgres -> db
    if in_docker and current_host in local_hosts:
        raw_url = _replace_host(raw_url, _env("DB_DOCKER_HOST", "db"))

    if in_docker and current_host == "postgres":
        raw_url = _replace_host(raw_url, _env("DB_DOCKER_HOST", "db"))

    raw_url = _ensure_connect_timeout(raw_url, 10)
    return raw_url


# -----------------------------------------------------------------------------
# Engine / Session
# -----------------------------------------------------------------------------

DATABASE_URL = _derive_database_url()

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


# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
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
