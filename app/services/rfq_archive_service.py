from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.services.rfq_operational_classification_service import (
    CLASSIFICATION_VERSION,
    RfqOperationalClassification,
    RfqOperationalClassificationService,
    canonical_rfq_id,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT = PROJECT_ROOT / "runtime" / "rfq_archive"
HISTORICAL_RFQ_FILE = ARCHIVE_ROOT / "historical_rfqs.json"
CLASSIFICATION_REVIEW_FILE = ARCHIVE_ROOT / "classification_review_rfqs.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_store(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": "rfq_archive_v1", "updated_at": "", "items": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            return data
    except Exception:
        pass
    return {"version": "rfq_archive_v1", "updated_at": "", "items": {}}


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _decorate(rfq: Dict[str, Any], classification: Dict[str, Any], reason: str, original_store: str) -> Dict[str, Any]:
    record = dict(rfq)
    meta = dict(record.get("archive_metadata") or {})
    meta.update(
        {
            "operational_classification": classification.get("classification"),
            "archive_reason": reason,
            "archived_at": meta.get("archived_at") or _now_iso(),
            "classification_version": CLASSIFICATION_VERSION,
            "original_store": original_store,
            "classification_confidence": classification.get("confidence"),
            "raw_status": record.get("status") or record.get("raw_status") or "",
            "raw_closing_date": record.get("closing_date") or record.get("closing_at") or record.get("deadline") or "",
        }
    )
    record["archive_metadata"] = meta
    record.setdefault("rfq_id", canonical_rfq_id(record))
    record["operational_classification"] = classification.get("classification")
    record["operational_classification_reason"] = reason
    return record


class RfqArchiveService:
    def __init__(
        self,
        historical_file: Path = HISTORICAL_RFQ_FILE,
        review_file: Path = CLASSIFICATION_REVIEW_FILE,
        classifier: Optional[RfqOperationalClassificationService] = None,
    ) -> None:
        self.historical_file = historical_file
        self.review_file = review_file
        self.classifier = classifier or RfqOperationalClassificationService()

    def list_archived_rfqs(self) -> Dict[str, Any]:
        payload = _read_store(self.historical_file)
        items = list(payload.get("items", {}).values())
        return {"status": "ok", "count": len(items), "items": items, "updated_at": payload.get("updated_at", "")}

    def get_archived_rfq(self, rfq_id: str) -> Dict[str, Any]:
        payload = _read_store(self.historical_file)
        item = payload.get("items", {}).get(str(rfq_id))
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}
        return {"status": "ok", "item": item}

    def archive_rfq(self, rfq: Dict[str, Any], reason: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = _read_store(self.historical_file)
        result = self.classifier.classify(rfq).to_dict()
        record = _decorate(rfq, result, reason, str((metadata or {}).get("original_store") or "runtime/live_rfqs.json"))
        record["archive_metadata"].update(metadata or {})
        payload.setdefault("items", {})[canonical_rfq_id(record)] = record
        payload["updated_at"] = _now_iso()
        _atomic_write(self.historical_file, payload)
        return {"status": "ok", "rfq_id": canonical_rfq_id(record), "count": len(payload["items"])}

    def archive_many(self, rfqs: Iterable[Dict[str, Any]], original_store: str = "runtime/live_rfqs.json") -> Dict[str, Any]:
        payload = _read_store(self.historical_file)
        added = 0
        for rfq in rfqs:
            result = self.classifier.classify(rfq).to_dict()
            record = _decorate(rfq, result, str(result.get("reason") or ""), original_store)
            key = canonical_rfq_id(record)
            if key not in payload.setdefault("items", {}):
                added += 1
            payload["items"][key] = record
        payload["updated_at"] = _now_iso()
        _atomic_write(self.historical_file, payload)
        return {"status": "ok", "added": added, "count": len(payload["items"])}

    def store_review_required(self, rfqs: Iterable[Dict[str, Any]], original_store: str = "runtime/live_rfqs.json") -> Dict[str, Any]:
        payload = _read_store(self.review_file)
        added = 0
        for rfq in rfqs:
            result = self.classifier.classify(rfq).to_dict()
            record = _decorate(rfq, result, str(result.get("reason") or ""), original_store)
            record["review_metadata"] = dict(record.get("archive_metadata") or {})
            key = canonical_rfq_id(record)
            if key not in payload.setdefault("items", {}):
                added += 1
            payload["items"][key] = record
        payload["updated_at"] = _now_iso()
        _atomic_write(self.review_file, payload)
        return {"status": "ok", "added": added, "count": len(payload["items"])}

    def list_review_required_rfqs(self) -> Dict[str, Any]:
        payload = _read_store(self.review_file)
        items = list(payload.get("items", {}).values())
        return {"status": "ok", "count": len(items), "items": items, "updated_at": payload.get("updated_at", "")}

    def get_archive_summary(self) -> Dict[str, Any]:
        archived = self.list_archived_rfqs()["items"]
        review = self.list_review_required_rfqs()["items"]
        reasons = Counter(str((item.get("archive_metadata") or {}).get("archive_reason") or item.get("operational_classification_reason") or "UNKNOWN") for item in archived)
        review_reasons = Counter(str(item.get("operational_classification_reason") or "UNKNOWN") for item in review)
        return {
            "status": "ok",
            "archived_total": len(archived),
            "review_required_total": len(review),
            "historical_reasons": dict(sorted(reasons.items())),
            "review_reasons": dict(sorted(review_reasons.items())),
        }

    def restore_to_active(self, rfq_id: str, reason: str) -> Dict[str, Any]:
        payload = _read_store(self.historical_file)
        item = payload.get("items", {}).get(str(rfq_id))
        if not item:
            return {"status": "not_found", "rfq_id": rfq_id}
        restored = dict(item)
        restored.setdefault("archive_metadata", {})["restored_at"] = _now_iso()
        restored["archive_metadata"]["restore_reason"] = reason
        return {"status": "ok", "item": restored, "mutated_active_store": False}
