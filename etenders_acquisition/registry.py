from datetime import datetime
from typing import Optional

from .models import CanonicalRecord
from .normalizer import normalize_text, normalize_date
from .fingerprint import build_fingerprint


class InMemoryDedupeStore:
    """
    Simple dedupe store for Milestone 1.
    Replace with Redis/Postgres later.
    """
    def __init__(self):
        self.seen = set()

    def exists(self, key: str) -> bool:
        return key in self.seen

    def insert(self, key: str) -> None:
        self.seen.add(key)


class SourceRegistry:
    def __init__(self, source_id: str, dedupe_store: InMemoryDedupeStore):
        self.source_id = source_id
        self.dedupe_store = dedupe_store

    def process(self, raw_item: dict) -> Optional[CanonicalRecord]:
        """
        Returns:
            CanonicalRecord if new
            None if duplicate or invalid
        """

        if not raw_item:
            return None

        title = raw_item.get("title") or ""
        url = raw_item.get("url") or ""
        closing_date_raw = raw_item.get("closing_date")

        # Skip invalid records early
        if not title or not url:
            return None

        normalized_title = normalize_text(title)
        closing_date = normalize_date(closing_date_raw)

        fingerprint = build_fingerprint(title, url, closing_date_raw)
        record_uid = f"{self.source_id}:{fingerprint}"

        # 🔒 DEDUP CHECK
        if self.dedupe_store.exists(record_uid):
            return None

        self.dedupe_store.insert(record_uid)

        now = datetime.utcnow()

        return CanonicalRecord(
            source_id=self.source_id,
            record_uid=record_uid,
            entity_type="tender",
            title=title,
            normalized_title=normalized_title,
            url=url,
            closing_date=closing_date,
            fingerprint=fingerprint,
            first_seen=now,
            last_seen=now,
            raw=raw_item,
        )
