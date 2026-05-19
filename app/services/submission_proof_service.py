from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from app.domain.submission import SubmissionProof
from app.core.runtime_paths import get_runtime_paths
from app.services import submission_review_service

logger = logging.getLogger(__name__)


RUNTIME_DIR = get_runtime_paths().runtime_root
MANUAL_PRODUCTION_DIR = get_runtime_paths().manual_production_dir
MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
SUBMISSION_PROOF_LOG_FILE = MANUAL_PRODUCTION_DIR / "submission_proofs.jsonl"

_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def append_submission_proof(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("timestamp", _now_iso())
    MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with SUBMISSION_PROOF_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    if _clean(item.get("status")) == "recorded":
        try:
            from app.core.workflow_state_engine import WorkflowStage, record_transition

            record_transition(
                tender_id=_clean(item.get("tender_id")),
                from_stage=WorkflowStage.REVIEW_READY,
                to_stage=WorkflowStage.PROOF_RECORDED,
                actor=_clean(item.get("submitted_by")) or "submission_proof_service",
                reason="submission proof recorded",
                details={"source_log": "submission_proofs.jsonl", "status": _clean(item.get("status"))},
            )
        except Exception:
            logger.warning("workflow transition review_ready -> proof_recorded was not recorded", exc_info=True)
    return item


def list_recent_submission_proofs(limit: int = 20) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    if SUBMISSION_PROOF_LOG_FILE.exists():
        try:
            for line in SUBMISSION_PROOF_LOG_FILE.read_text(encoding="utf-8").splitlines():
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
        "log_file": str(SUBMISSION_PROOF_LOG_FILE),
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
) -> Dict[str, Any]:
    review = submission_review_service.find_latest_submission_review(tender_id, tender_root)
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
    return SubmissionProof.validate_payload(record).to_jsonable_dict()
