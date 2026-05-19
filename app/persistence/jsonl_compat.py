from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.persistence.repositories import (
    ApprovalRepository,
    AuditRepository,
    PricingRepository,
    QuoteRepository,
    SubmissionRepository,
    WorkflowRepository,
)

logger = logging.getLogger(__name__)


def read_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _persist_with_repo(label: str, callback, record: Dict[str, Any]) -> bool:
    try:
        callback(record)
        return True
    except Exception:
        logger.warning("%s persistence failed; JSONL remains authoritative", label, exc_info=True)
        return False


def persist_workflow_transition(record: Dict[str, Any]) -> bool:
    repo = WorkflowRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", payload.get("to_stage") or payload.get("stage") or "")
    return _persist_with_repo("workflow_transition", repo.append_event, payload)


def persist_workflow_state(record: Dict[str, Any]) -> bool:
    repo = WorkflowRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", payload.get("stage") or payload.get("workflow_stage") or "")
    return _persist_with_repo("workflow_state", repo.append_state, payload)


def persist_approval(record: Dict[str, Any]) -> bool:
    repo = ApprovalRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", "approved" if payload.get("manual_approval_recorded") else "approval_required")
    return _persist_with_repo("approval_record", repo.append, payload)


def persist_submission_review(record: Dict[str, Any]) -> bool:
    repo = SubmissionRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", "review_ready" if str(payload.get("status") or "").strip() == "review_ready" else "refused")
    return _persist_with_repo("submission_review", repo.append_review, payload)


def persist_submission_proof(record: Dict[str, Any]) -> bool:
    repo = SubmissionRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", "proof_recorded" if str(payload.get("status") or "").strip() == "recorded" else "refused")
    return _persist_with_repo("submission_proof", repo.append_proof, payload)


def persist_audit_event(record: Dict[str, Any]) -> bool:
    repo = AuditRepository()
    payload = dict(record or {})
    nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    payload.setdefault(
        "workflow_stage",
        payload.get("workflow_stage")
        or payload.get("to_stage")
        or nested.get("workflow_stage")
        or nested.get("to_stage")
        or "",
    )
    return _persist_with_repo("audit_event", repo.append_audit_event, payload)


def persist_pricing_decision(record: Dict[str, Any]) -> bool:
    repo = PricingRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", "priced")
    return _persist_with_repo("pricing_decision", repo.append_decision, payload)


def persist_quote_pack(record: Dict[str, Any]) -> bool:
    repo = QuoteRepository()
    payload = dict(record or {})
    payload.setdefault("workflow_stage", "quote_generated")
    return _persist_with_repo("quote_pack", repo.append_quote_pack, payload)
