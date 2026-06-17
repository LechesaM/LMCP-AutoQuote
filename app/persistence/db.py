from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Iterator

from app.core.runtime_paths import get_runtime_paths


_INITIALIZED = False
_INITIALIZED_PATH: Path | None = None


def _database_path() -> Path:
    paths = get_runtime_paths()
    override = Path(paths.manual_production_dir) / "lmcp_operations.db"
    return override


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_state_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT,
            stage TEXT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS workflow_event_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT,
            from_stage TEXT,
            to_stage TEXT,
            actor TEXT,
            reason TEXT,
            details_json TEXT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_event_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS approval_record_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS submission_review_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS submission_proof_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS queue_history_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS queue_job_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS pilot_run_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        CREATE TABLE IF NOT EXISTS pilot_signoff_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT
        );
        """
    )


def initialize_database() -> Path:
    global _INITIALIZED, _INITIALIZED_PATH
    db_path = _database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        _ensure_schema(connection)
        connection.commit()
    finally:
        connection.close()
    _INITIALIZED = True
    _INITIALIZED_PATH = db_path
    return db_path


def safe_initialize_database() -> Path:
    return initialize_database()


def get_connection() -> sqlite3.Connection:
    db_path = _database_path()
    if not db_path.exists():
        initialize_database()
    return sqlite3.connect(db_path)


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        _ensure_schema(connection)
        yield connection
    finally:
        connection.close()


def insert_json_record(table: str, payload: dict[str, Any]) -> None:
    with connection_scope() as connection:
        _ensure_schema(connection)
        connection.execute(
            f"INSERT INTO {table} (payload_json) VALUES (?)",
            (json.dumps(payload, default=str),),
        )
        connection.commit()


def database_connection_ready() -> bool:
    try:
        connection = get_connection()
        try:
            connection.execute("SELECT 1")
        finally:
            connection.close()
        return True
    except Exception:
        return False


def get_database_backend() -> str:
    return "sqlite"


def test_db_connection() -> bool:
    return database_connection_ready()


def init_db() -> None:
    initialize_database()


DATABASE_URL = "sqlite:///local-manual-production"
