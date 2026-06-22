from dataclasses import dataclass
import hashlib
import time
from typing import Dict, Any, List


@dataclass
class TenderRecord:
    tender_id: str
    title: str
    department: str | None
    province: str | None
    closing_date: str | None
    raw: Dict[str, Any]
    ingested_at: float

    # =========================
    # DEDUP KEY (STABLE ID)
    # =========================
    def dedup_key(self) -> str:
        base = self.tender_id or f"{self.title}|{self.department}|{self.closing_date}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    # =========================
    # CHANGE DETECTION HASH
    # =========================
    def content_hash(self) -> str:
        base = f"{self.tender_id}|{self.title}|{self.department}|{self.province}|{self.closing_date}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()


class SourceRegistry:

    @staticmethod
    def normalize(raw: Dict[str, Any]) -> TenderRecord:
        return TenderRecord(
            tender_id=str(raw.get("tenderId") or raw.get("id") or ""),
            title=(raw.get("title") or "").strip(),
            department=raw.get("departmentName"),
            province=raw.get("province"),
            closing_date=raw.get("closingDate"),
            raw=raw,
            ingested_at=time.time()
        )

    @staticmethod
    def ingest_raw(items: List[Dict[str, Any]]) -> List[TenderRecord]:
        clean = []

        for item in items or []:
            try:
                r = SourceRegistry.normalize(item)
                if r.title:
                    clean.append(r)
            except Exception:
                continue

        return clean
