from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from app.services import submission_review_service
from app.persistence import db as persistence_db


RUNTIME_DIR = Path("runtime")
MANUAL_PRODUCTION_DIR = RUNTIME_DIR / "manual_production"
MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
SUBMISSION_PROOF_LOG_FILE = MANUAL_PRODUCTION_DIR / "submission_proofs.jsonl"

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


def append_submission_proof(record: Dict[str, Any], runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("timestamp", _now_iso())
    proof_log = _resolve_runtime_path(SUBMISSION_PROOF_LOG_FILE, runtime_dir)
    proof_log.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with proof_log.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    try:
        persistence_db.insert_json_record("submission_proof_entities", item)
    except Exception:
        pass
    return item


def list_recent_submission_proofs(limit: int = 20, runtime_dir: Optional[str] = None) -> Dict[str, Any]:
    proof_log = _resolve_runtime_path(SUBMISSION_PROOF_LOG_FILE, runtime_dir)
    records: List[Dict[str, Any]] = []
    if proof_log.exists():
        try:
            for line in proof_log.read_text(encoding="utf-8").splitlines():
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
        "log_file": str(proof_log),
        "updated_at": _now_iso(),
    }


def build_submission_proof_record(
    *,
    tender_id: str,
    tender_root: str,
    portal_name: str,
    submission_reference: str,
    submitted_by: str,
    proof_file: str = "",
    runtime_dir: Optional[str] = None,
) -> Dict[str, Any]:
    review = submission_review_service.find_latest_submission_review(tender_id, tender_root, runtime_dir=runtime_dir)
    blockers: List[str] = []

    if _clean(review.get("status")) != "review_ready":
        blockers.append("submission review status must be review_ready")
    if not review:
        blockers.append("submission review record missing")
    if not _clean(submission_reference):
        blockers.append("submission_reference required")
    if not _clean(submitted_by):
        blockers.append("submitted_by required")

    proof_path = Path(_clean(proof_file)).expanduser() if _clean(proof_file) else None
    proof_present = bool(proof_path and proof_path.exists()) if proof_path else False

    record = {
        "tender_id": _clean(tender_id),
        "tender_root": _clean(tender_root),
        "portal_name": _clean(portal_name),
        "submission_reference": _clean(submission_reference),
        "submitted_by": _clean(submitted_by),
        "proof_file": _clean(proof_file),
        "proof_file_present": proof_present,
        "submission_review_status": _clean(review.get("status")) if review else "",
        "submission_review_ready": _clean(review.get("status")) == "review_ready",
        "final_submission_attempted": False,
        "manual_submission_recorded": not blockers,
        "blockers": blockers,
        "status": "recorded" if not blockers else "refused",
        "timestamp": _now_iso(),
    }
    return record
