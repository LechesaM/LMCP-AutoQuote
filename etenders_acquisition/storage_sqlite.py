import sqlite3
import time
from typing import List, Tuple
from source_registry import TenderRecord


DB_FILE = "etenders.db"


class SQLiteStore:

    def __init__(self, db_file=DB_FILE):
        self.conn = sqlite3.connect(db_file)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            id TEXT PRIMARY KEY,
            tender_id TEXT,
            title TEXT,
            department TEXT,
            province TEXT,
            closing_date TEXT,
            content_hash TEXT,
            ingested_at REAL,
            updated_at REAL,
            raw_json TEXT
        )
        """)
        self.conn.commit()

    # =========================
    # UPSERT WITH CHANGE DETECTION
    # =========================
    def upsert_batch(self, records: List[TenderRecord]) -> Tuple[int, int, int]:

        now = time.time()

        inserted = 0
        updated = 0
        skipped = 0

        for r in records:

            key = r.dedup_key()
            new_hash = r.content_hash()

            row = self.conn.execute(
                "SELECT content_hash FROM tenders WHERE id = ?",
                (key,)
            ).fetchone()

            # =========================
            # NEW RECORD
            # =========================
            if not row:
                self.conn.execute("""
                INSERT INTO tenders (
                    id, tender_id, title, department, province,
                    closing_date, content_hash,
                    ingested_at, updated_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    r.tender_id,
                    r.title,
                    r.department,
                    r.province,
                    r.closing_date,
                    new_hash,
                    now,
                    now,
                    str(r.raw)
                ))
                inserted += 1

            # =========================
            # EXISTS → CHECK CHANGE
            # =========================
            else:
                old_hash = row[0]

                if old_hash != new_hash:
                    self.conn.execute("""
                    UPDATE tenders
                    SET title = ?,
                        department = ?,
                        province = ?,
                        closing_date = ?,
                        content_hash = ?,
                        updated_at = ?,
                        raw_json = ?
                    WHERE id = ?
                    """, (
                        r.title,
                        r.department,
                        r.province,
                        r.closing_date,
                        new_hash,
                        now,
                        str(r.raw),
                        key
                    ))
                    updated += 1

                else:
                    skipped += 1

        self.conn.commit()

        return inserted, updated, skipped

    def close(self):
        self.conn.close()
