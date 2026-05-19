from __future__ import annotations

import logging
import sqlite3
from hashlib import sha256
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Dict, Any

from app.core.runtime_paths import get_runtime_paths

logger = logging.getLogger(__name__)

_INITIALIZED = False
_INITIALIZED_PATH: Path | None = None


def get_database_path() -> Path:
    return get_runtime_paths().manual_production_db_path


def _apply_pragmas(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA foreign_keys=ON;")
    connection.execute("PRAGMA synchronous=NORMAL;")


def _create_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_state_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_state_records_tender_created
            ON workflow_state_records (tender_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS workflow_event_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL DEFAULT '',
            from_stage TEXT NOT NULL DEFAULT '',
            to_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_event_records_tender_created
            ON workflow_event_records (tender_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS approval_record_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS submission_review_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS submission_proof_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_event_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL DEFAULT '',
            workflow_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT '',
            quote_number TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_event_entities_tender_created
            ON audit_event_entities (tender_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS pricing_decision_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quote_pack_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT NOT NULL,
            workflow_stage TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            operator TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def initialize_database() -> Path:
    path = get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        _apply_pragmas(connection)
        _create_tables(connection)
        connection.commit()
    finally:
        connection.close()
    return path


def safe_initialize_database() -> bool:
    global _INITIALIZED, _INITIALIZED_PATH
    path = get_database_path()
    if _INITIALIZED and _INITIALIZED_PATH == path and path.exists():
        return True
    try:
        initialize_database()
        _INITIALIZED = True
        _INITIALIZED_PATH = path
        return True
    except Exception:
        logger.warning("SQLite persistence database could not be initialized", exc_info=True)
        return False


def get_connection() -> sqlite3.Connection:
    safe_initialize_database()
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    _apply_pragmas(connection)
    return connection


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def database_integrity_check() -> Dict[str, Any]:
    try:
        with connection_scope() as connection:
            row = connection.execute("PRAGMA integrity_check;").fetchone()
        result = str(row[0] if row else "").strip().lower()
        return {
            "healthy": result == "ok",
            "status": "healthy" if result == "ok" else "degraded",
            "result": result or "unknown",
            "db_path": str(get_database_path()),
        }
    except Exception as exc:
        return {
            "healthy": False,
            "status": "degraded",
            "result": "error",
            "error": str(exc),
            "db_path": str(get_database_path()),
        }


def database_checksum(path: Path | None = None) -> str:
    target = path or get_database_path()
    if not target.exists():
        return ""
    digest = sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
