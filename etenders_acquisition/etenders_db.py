import sqlite3
import json

DB_NAME = "etenders.db"


def get_conn():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tenders (
        id INTEGER PRIMARY KEY,
        tender_No TEXT,
        description TEXT,
        category TEXT,
        type TEXT,
        organ_of_State TEXT,
        status TEXT,
        closing_Date TEXT,
        date_Published TEXT,
        province TEXT,
        department TEXT,
        raw_json TEXT,
        last_seen TEXT
    )
    """)

    conn.commit()
    conn.close()


def ensure_columns():
    """
    Safely adds missing columns without breaking existing DBs.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(tenders)")
    existing_cols = [row[1] for row in cur.fetchall()]

    required_cols = {
        "description": "TEXT",
        "last_seen": "TEXT",
        "raw_json": "TEXT",
        "province": "TEXT",
        "department": "TEXT"
    }

    for col, col_type in required_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE tenders ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


def save_tender(conn, tender):
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO tenders (
            id, tender_No, description, category, type,
            organ_of_State, status, closing_Date, date_Published,
            province, department, raw_json, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        tender.get("id"),
        tender.get("tender_No"),
        tender.get("description"),
        tender.get("category"),
        tender.get("type"),
        tender.get("organ_of_State"),
        tender.get("status"),
        tender.get("closing_Date"),
        tender.get("date_Published"),
        tender.get("province"),
        tender.get("department"),
        json.dumps(tender)
    ))
