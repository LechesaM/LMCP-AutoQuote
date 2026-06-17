from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


RUNTIME_DIR = Path("runtime")
IMMUTABLE_SUBMISSION_DIR = RUNTIME_DIR / "locks" / "immutable_submission"
IMMUTABLE_SUBMISSION_LOG_FILE = IMMUTABLE_SUBMISSION_DIR / "immutable_submission_chain.jsonl"
IMMUTABLE_SUBMISSION_MANIFEST_FILE = IMMUTABLE_SUBMISSION_DIR / "immutable_submission_manifest.json"

_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _read_records() -> List[Dict[str, Any]]:
    if not IMMUTABLE_SUBMISSION_LOG_FILE.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in IMMUTABLE_SUBMISSION_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _record_hash_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": _safe_text(record.get("timestamp")),
        "kind": _safe_text(record.get("kind")),
        "actor": _safe_text(record.get("actor")),
        "source_service": _safe_text(record.get("source_service")),
        "source_log": _safe_text(record.get("source_log")),
        "tender_id": _safe_text(record.get("tender_id")),
        "status": _safe_text(record.get("status")),
        "payload": record.get("payload") if isinstance(record.get("payload"), dict) else {},
        "previous_hash": _safe_text(record.get("previous_hash")),
    }


def _hash_record(record: Dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(_canonical_json(_record_hash_payload(record)).encode("utf-8"))
    return digest.hexdigest()


def _write_manifest(records: List[Dict[str, Any]], verification: Dict[str, Any]) -> None:
    IMMUTABLE_SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _now_iso(),
        "total_records": len(records),
        "latest_record_hash": _safe_text(records[-1].get("record_hash")) if records else "",
        "valid": bool(verification.get("valid")),
        "invalid_entries": int(len(verification.get("invalid_entries") or [])),
    }
    IMMUTABLE_SUBMISSION_MANIFEST_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def append_immutable_submission_record(record: Dict[str, Any]) -> Dict[str, Any]:
    IMMUTABLE_SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)
    records = _read_records()
    item = {
        "timestamp": _safe_text((record or {}).get("timestamp")) or _now_iso(),
        "kind": _safe_text((record or {}).get("kind")),
        "actor": _safe_text((record or {}).get("actor")),
        "source_service": _safe_text((record or {}).get("source_service")),
        "source_log": _safe_text((record or {}).get("source_log")),
        "tender_id": _safe_text((record or {}).get("tender_id")),
        "status": _safe_text((record or {}).get("status")),
        "payload": (record or {}).get("payload") if isinstance((record or {}).get("payload"), dict) else {},
        "previous_hash": _safe_text(records[-1].get("record_hash")) if records else "",
    }
    item["record_hash"] = _hash_record(item)
    line = _canonical_json(item)
    with _LOCK:
        with IMMUTABLE_SUBMISSION_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    updated_records = records + [item]
    _write_manifest(updated_records, {"valid": True, "invalid_entries": []})
    return item


def verify_submission_chain() -> Dict[str, Any]:
    records = _read_records()
    invalid_entries: List[Dict[str, Any]] = []
    previous_hash = ""
    for index, record in enumerate(records):
        expected_previous = previous_hash
        actual_previous = _safe_text(record.get("previous_hash"))
        expected_hash = _hash_record(record)
        actual_hash = _safe_text(record.get("record_hash"))
        if actual_previous != expected_previous or actual_hash != expected_hash:
            invalid_entries.append(
                {
                    "index": index,
                    "tender_id": _safe_text(record.get("tender_id")),
                    "kind": _safe_text(record.get("kind")),
                    "expected_previous_hash": expected_previous,
                    "actual_previous_hash": actual_previous,
                    "expected_record_hash": expected_hash,
                    "actual_record_hash": actual_hash,
                }
            )
        previous_hash = actual_hash
    verification = {
        "valid": not invalid_entries,
        "checked_at": _now_iso(),
        "total_records": len(records),
        "invalid_entries": invalid_entries,
    }
    _write_manifest(records, verification)
    return verification


def get_submission_lock_status(limit: int = 50) -> Dict[str, Any]:
    records = _read_records()
    verification = verify_submission_chain()
    safe_limit = max(1, int(limit or 50))
    return {
        "status": "ok",
        "summary": {
            "total_records": len(records),
            "valid": bool(verification.get("valid")),
            "latest_record_hash": _safe_text(records[-1].get("record_hash")) if records else "",
        },
        "verification": verification,
        "recent_records": list(reversed(records[-safe_limit:])),
        "log_file": str(IMMUTABLE_SUBMISSION_LOG_FILE),
        "manifest_file": str(IMMUTABLE_SUBMISSION_MANIFEST_FILE),
        "updated_at": _now_iso(),
    }
