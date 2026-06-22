import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("runtime/workflow/workflow_layer.db")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_workflow_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS supplier_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL UNIQUE,
        contact_person TEXT,
        email TEXT,
        phone TEXT,
        branch TEXT,
        category TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rfq_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id TEXT,
        supplier_name TEXT NOT NULL,
        rfq_reference TEXT NOT NULL UNIQUE,
        rfq_file_path TEXT,
        total_items INTEGER DEFAULT 0,
        total_estimated_value REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        created_at TEXT NOT NULL,
        sent_at TEXT,
        response_due_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS supplier_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rfq_reference TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        response_status TEXT DEFAULT 'pending',
        quoted_total REAL,
        delivery_days INTEGER,
        exclusions TEXT,
        notes TEXT,
        received_at TEXT,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

    print(f"Workflow DB initialized: {DB_PATH}")


if __name__ == "__main__":
    init_workflow_db()
