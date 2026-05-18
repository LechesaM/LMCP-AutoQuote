from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths

RUNTIME_DIR = get_runtime_paths().runtime_root
MANUAL_PRODUCTION_DIR = get_runtime_paths().manual_production_dir
MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
APPROVAL_LOG_FILE = MANUAL_PRODUCTION_DIR / "approvals.jsonl"

_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def append_manual_approval(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("timestamp", _now_iso())
    MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with APPROVAL_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return item


def list_recent_manual_approvals(limit: int = 20) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    if APPROVAL_LOG_FILE.exists():
        try:
            for line in APPROVAL_LOG_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        except Exception:
            records = []
    recent = list(reversed(records[-max(1, int(limit or 20)) :]))
    return {
        "status": "ok",
        "items": recent,
        "total": len(records),
        "log_file": str(APPROVAL_LOG_FILE),
        "updated_at": _now_iso(),
    }


def evaluate_manual_approval_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    warnings = [str(item).strip() for item in _safe_list(result.get("warnings")) if _clean(item)]
    blockers: List[str] = []

    if _clean(result.get("quote_pack_quality_status")) != "approval_ready":
        blockers.append("quote_pack_quality_status must be approval_ready")
    if bool(result.get("approval_blocked", False)):
        blockers.append("approval_blocked must be false")
    if int(result.get("pricing_items_unmatched", 0) or 0) != 0:
        blockers.append("pricing_items_unmatched must be 0")
    if warnings:
        blockers.append("warnings must be none")
    if bool(result.get("final_submission_attempted", False)):
        blockers.append("final_submission_attempted must be false")

    return {
        "approved": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def build_manual_approval_record(
    result: Dict[str, Any],
    *,
    tender_id: str,
    tender_root: str,
    pricing_file: str,
    operator_name: str = "",
    confirm_approval: bool = False,
) -> Dict[str, Any]:
    gate = evaluate_manual_approval_gate(result)
    return {
        "tender_id": _clean(tender_id or result.get("tender_id")),
        "tender_root": _clean(tender_root or result.get("tender_root")),
        "pricing_file": _clean(pricing_file),
        "operator_name": _clean(operator_name),
        "confirm_approval": bool(confirm_approval),
        "manual_approval_recorded": bool(gate["approved"]) and bool(confirm_approval),
        "approved_by_operator": bool(gate["approved"]) and bool(confirm_approval),
        "submission_ready": bool(gate["approved"]) and bool(confirm_approval),
        "final_submission_attempted": False,
        "quote_pack_quality_status": _clean(result.get("quote_pack_quality_status")),
        "approval_blocked": bool(result.get("approval_blocked", False)),
        "pricing_items_unmatched": int(result.get("pricing_items_unmatched", 0) or 0),
        "warnings": _safe_list(result.get("warnings")),
        "gate": gate,
        "status": "recorded" if gate["approved"] and confirm_approval else "refused",
    }
