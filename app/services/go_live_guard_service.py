from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUNTIME_DIR = Path("runtime")
GUARD_DIR = RUNTIME_DIR / "go_live_guards"

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


def is_rfq_rejected(buyer_rfq_number: str) -> bool:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    return any(
        str(x.get("buyer_rfq_number") or "").strip() == buyer_rfq_number
        for x in _load_list(REJECTION_FILE)
    )


def is_source_paused(source_name: str) -> bool:
    source_name = str(source_name or "").strip()
    return any(
        str(x.get("source_name") or "").strip() == source_name
        for x in _load_list(PAUSED_SOURCES_FILE)
    )


def has_submission_lock(buyer_rfq_number: str, quote_number: str = "") -> bool:
    buyer_rfq_number = str(buyer_rfq_number or "").strip()
    quote_number = str(quote_number or "").strip()

    for item in _load_list(DUPLICATE_SUBMISSION_FILE):
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
    item = {
        "buyer_rfq_number": str(buyer_rfq_number or "").strip(),
        "quote_number": str(quote_number or "").strip(),
        "reason": reason,
        "metadata": metadata or {},
        "created_at": _now_iso(),
    }

    locks = _load_list(DUPLICATE_SUBMISSION_FILE)

    for existing in locks:
        if (
            str(existing.get("buyer_rfq_number") or "").strip() == item["buyer_rfq_number"]
            and str(existing.get("quote_number") or "").strip() == item["quote_number"]
        ):
            return existing

    locks.append(item)
    _save_list(DUPLICATE_SUBMISSION_FILE, locks)
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

    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "removed": len(removed),
    }


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

    blockers = []

    if is_rfq_rejected(str(buyer_rfq_number)):
        blockers.append("RFQ is rejected by operator and must not be quoted/submitted.")

    if is_source_paused(str(source_name)):
        blockers.append("Source is paused by operator and must not be harvested.")

    if has_submission_lock(str(buyer_rfq_number), str(quote_number)):
        blockers.append("Duplicate submission lock exists for this RFQ/quote.")

    return {
        "status": "ok",
        "allowed": len(blockers) == 0,
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "source_name": source_name,
        "blockers": blockers,
        "warnings": [],
        "checked_at": _now_iso(),
    }


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
        "updated_at": _now_iso(),
    }
