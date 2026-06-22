from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from app.persistence import db as persistence_db


RUNTIME_DIR = Path("runtime")
MANUAL_PRODUCTION_DIR = RUNTIME_DIR / "manual_production"
MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
APPROVAL_LOG_FILE = MANUAL_PRODUCTION_DIR / "approvals.jsonl"

_LOCK = Lock()


def _resolve_runtime_path(default_path: Path, runtime_dir: Optional[str] = None) -> Path:
    if not runtime_dir:
        return default_path
    runtime_root = Path(runtime_dir).expanduser().resolve()
    try:
        relative = default_path.relative_to(RUNTIME_DIR)
    except Exception:
        return default_path
    return runtime_root / relative


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


def append_manual_approval(record: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("timestamp", _now_iso())
    approval_file = _resolve_runtime_path(APPROVAL_LOG_FILE, runtime_dir)
    approval_file.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with approval_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    try:
        persistence_db.insert_json_record("approval_record_entities", item)
    except Exception:
        pass
    return item


def list_recent_manual_approvals(limit: int = 20, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    approval_file = _resolve_runtime_path(APPROVAL_LOG_FILE, runtime_dir)
    records: List[Dict[str, Any]] = []
    if approval_file.exists():
        try:
            for line in approval_file.read_text(encoding="utf-8").splitlines():
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
        "log_file": str(approval_file),
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
    approved = bool(gate["approved"]) and bool(confirm_approval)
    approved_at = _now_iso() if approved else ""
    return {
        "tender_id": _clean(tender_id or result.get("tender_id")),
        "tender_root": _clean(tender_root or result.get("tender_root")),
        "pricing_file": _clean(pricing_file),
        "operator_name": _clean(operator_name),
        "confirm_approval": bool(confirm_approval),
        "manual_approval_recorded": approved,
        "approved_by_operator": approved,
        "approved_by": _clean(operator_name) if approved else "",
        "approved_at": approved_at,
        "approval_decision": "approved" if approved else ("refused" if bool(confirm_approval) else "pending"),
        "submission_ready": approved,
        "final_submission_attempted": False,
        "quote_pack_quality_status": _clean(result.get("quote_pack_quality_status")),
        "approval_blocked": bool(result.get("approval_blocked", False)),
        "pricing_items_unmatched": int(result.get("pricing_items_unmatched", 0) or 0),
        "warnings": _safe_list(result.get("warnings")),
        "gate": gate,
        "status": "recorded" if approved else "refused",
    }
