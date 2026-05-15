from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path("runtime")
GUARD_DIR = RUNTIME_DIR / "go_live_guards"
GUARD_DIR.mkdir(parents=True, exist_ok=True)

DUPLICATE_SUBMISSION_FILE = GUARD_DIR / "submission_locks.json"
GUARD_AUDIT_FILE = GUARD_DIR / "guard_events.json"

OPERATOR_DIR = RUNTIME_DIR / "operator_actions"
REJECTION_FILE = OPERATOR_DIR / "operator_rejections.json"
PAUSED_SOURCES_FILE = OPERATOR_DIR / "paused_sources.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_list(path: Path, items: List[Dict[str, Any]], limit: int = 5000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[-limit:], indent=2, default=str))


def record_guard_event(event_type: str, status: str, message: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    item = {
        "event_type": event_type,
        "status": status,
        "message": message,
        "payload": payload or {},
        "created_at": _now_iso(),
    }
    events = _load_list(GUARD_AUDIT_FILE)
    events.append(item)
    _save_list(GUARD_AUDIT_FILE, events)
    return item


def is_rfq_rejected(buyer_rfq_number: str) -> bool:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    if not buyer_rfq_number:
        return False
    return any(str(x.get("buyer_rfq_number") or "").strip() == buyer_rfq_number for x in _load_list(REJECTION_FILE))


def is_source_paused(source_name: str) -> bool:
    source_name = str(source_name or "").strip()
    if not source_name:
        return False
    return any(str(x.get("source_name") or "").strip() == source_name for x in _load_list(PAUSED_SOURCES_FILE))


def has_submission_lock(buyer_rfq_number: str, quote_number: str = "") -> bool:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()
    locks = _load_list(DUPLICATE_SUBMISSION_FILE)
    for item in locks:
        if str(item.get("buyer_rfq_number") or "").strip() == buyer_rfq_number:
            if not quote_number or str(item.get("quote_number") or "").strip() == quote_number:
                return True
    return False


def create_submission_lock(
    buyer_rfq_number: str,
    quote_number: str = "",
    reason: str = "submission_completed_or_in_progress",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()

    locks = _load_list(DUPLICATE_SUBMISSION_FILE)
    for existing in locks:
        if str(existing.get("buyer_rfq_number") or "").strip() == buyer_rfq_number and str(existing.get("quote_number") or "").strip() == quote_number:
            return existing

    item = {
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "reason": reason,
        "metadata": metadata or {},
        "created_at": _now_iso(),
    }

    locks.append(item)
    _save_list(DUPLICATE_SUBMISSION_FILE, locks)
    record_guard_event("submission_lock_created", "ok", "Submission duplicate lock created.", item)
    return item


def clear_submission_lock(buyer_rfq_number: str, quote_number: str = "") -> Dict[str, Any]:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()
    locks = _load_list(DUPLICATE_SUBMISSION_FILE)

    kept = []
    removed = []
    for item in locks:
        same_rfq = str(item.get("buyer_rfq_number") or "").strip() == buyer_rfq_number
        same_quote = not quote_number or str(item.get("quote_number") or "").strip() == quote_number
        if same_rfq and same_quote:
            removed.append(item)
        else:
            kept.append(item)

    _save_list(DUPLICATE_SUBMISSION_FILE, kept)
    result = {"status": "ok", "removed": len(removed), "buyer_rfq_number": buyer_rfq_number, "quote_number": quote_number}
    record_guard_event("submission_lock_cleared", "ok", "Submission duplicate lock cleared.", result)
    return result


def evaluate_pipeline_guard(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = (
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("tender_number")
        or payload.get("reference")
        or ""
    )
    quote_number = payload.get("quote_number") or ""
    source_name = payload.get("source_name") or payload.get("source") or ""

    blockers: List[str] = []
    warnings: List[str] = []

    if is_rfq_rejected(str(buyer_rfq_number)):
        blockers.append("RFQ is rejected by operator and must not be quoted/submitted.")

    if is_source_paused(str(source_name)):
        blockers.append("Source is paused by operator and must not be harvested.")

    if has_submission_lock(str(buyer_rfq_number), str(quote_number)):
        blockers.append("Duplicate submission lock exists for this RFQ/quote.")

    allowed = len(blockers) == 0
    result = {
        "status": "ok",
        "allowed": allowed,
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "source_name": source_name,
        "blockers": blockers,
        "warnings": warnings,
        "checked_at": _now_iso(),
    }

    record_guard_event("pipeline_guard_check", "allowed" if allowed else "blocked", "Pipeline guard evaluated.", result)
    return result


def get_guard_summary(limit: int = 80) -> Dict[str, Any]:
    locks = _load_list(DUPLICATE_SUBMISSION_FILE)
    rejected = _load_list(REJECTION_FILE)
    paused = _load_list(PAUSED_SOURCES_FILE)
    events = _load_list(GUARD_AUDIT_FILE)

    return {
        "status": "ok",
        "summary": {
            "submission_locks": len(locks),
            "operator_rejections": len(rejected),
            "paused_sources": len(paused),
            "guard_events": len(events),
        },
        "submission_locks": list(reversed(locks[-limit:])),
        "operator_rejections": list(reversed(rejected[-limit:])),
        "paused_sources": list(reversed(paused[-limit:])),
        "recent_guard_events": list(reversed(events[-limit:])),
        "files": {
            "submission_locks": str(DUPLICATE_SUBMISSION_FILE),
            "operator_rejections": str(REJECTION_FILE),
            "paused_sources": str(PAUSED_SOURCES_FILE),
            "guard_events": str(GUARD_AUDIT_FILE),
        },
        "updated_at": _now_iso(),
    }
