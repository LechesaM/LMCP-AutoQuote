import json
import time
from typing import List, Tuple, Any

from app.db.models import Tender
from app.db.session import SessionLocal


class PostgreSQLStore:
    """
    PostgreSQL-backed tender store.

    Mirrors SQLiteStore.upsert_batch(records).
    Does not import TenderRecord directly, so it works with any record object
    that has: dedup_key(), content_hash(), tender_id, title, department,
    province, closing_date, raw.
    """

    def __init__(self):
        self.SessionLocal = SessionLocal

    def upsert_batch(self, records: List[Any]) -> Tuple[int, int, int]:
        now = time.time()

        inserted = 0
        updated = 0
        skipped = 0

        with self.SessionLocal() as session:
            for r in records:
                key = r.dedup_key()
                new_hash = r.content_hash()

                raw_json = json.dumps(
                    getattr(r, "raw", {}),
                    ensure_ascii=False,
                    default=str,
                )

                existing = session.get(Tender, key)

                if existing is None:
                    session.add(Tender(
                        id=key,
                        tender_id=getattr(r, "tender_id", None),
                        title=getattr(r, "title", None),
                        department=getattr(r, "department", None),
                        province=getattr(r, "province", None),
                        closing_date=getattr(r, "closing_date", None),
                        content_hash=new_hash,
                        ingested_at=now,
                        updated_at=now,
                        raw_json=raw_json,
                    ))
                    inserted += 1

                elif existing.content_hash != new_hash:
                    existing.tender_id = getattr(r, "tender_id", None)
                    existing.title = getattr(r, "title", None)
                    existing.department = getattr(r, "department", None)
                    existing.province = getattr(r, "province", None)
                    existing.closing_date = getattr(r, "closing_date", None)
                    existing.content_hash = new_hash
                    existing.updated_at = now
                    existing.raw_json = raw_json
                    updated += 1

                else:
                    skipped += 1

            session.commit()

        return inserted, updated, skipped

    def close(self):
        pass
