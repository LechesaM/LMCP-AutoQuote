from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import Field

from app.core.runtime_paths import get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.domain.workflow import WorkflowStage
from app.orchestration.queue_monitor import get_queue_health, get_queue_summary
from app.persistence.repositories import WorkflowRepository

_ACTIVE_STAGE_VALUES = {
    WorkflowStage.DISCOVERED.value,
    WorkflowStage.EXTRACTED.value,
    WorkflowStage.EVALUATED.value,
    WorkflowStage.PRICED.value,
    WorkflowStage.QUOTE_GENERATED.value,
    WorkflowStage.APPROVAL_REQUIRED.value,
    WorkflowStage.APPROVED.value,
    WorkflowStage.REVIEW_READY.value,
    WorkflowStage.PROOF_RECORDED.value,
}


class WorkflowMonitorSummary(StrictBaseModel):
    status: str = "ok"
    checked_at: Any = None
    total_workflows: int = 0
    stage_counts: Dict[str, int]
    refusals: int = 0
    approvals_pending: int = 0
    review_ready_pending: int = 0
    proof_capture_pending: int = 0
    updated_at: Any = None
    queue_health: Dict[str, Any] = Field(default_factory=dict)
    queue_summary: Dict[str, Any] = Field(default_factory=dict)


def _stage_name(value: Any) -> str:
    return str(value or "").strip()


def _latest_by_tender(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        tender_id = _stage_name(record.get("tender_id"))
        if not tender_id:
            continue
        if tender_id not in latest:
            latest[tender_id] = record
    return latest


def _load_repository() -> WorkflowRepository:
    paths = get_runtime_paths()
    return WorkflowRepository(jsonl_path=paths.manual_production_file("workflow_state.jsonl"))


def get_workflow_summary(limit: int = 500) -> Dict[str, Any]:
    repo = _load_repository()
    records = repo.fetch_recent(limit=limit)
    latest = _latest_by_tender(records)
    stage_counts = Counter()
    refusals = approvals_pending = review_ready_pending = proof_capture_pending = 0
    for record in latest.values():
        stage = _stage_name(record.get("stage"))
        stage_counts[stage] += 1
        if stage == WorkflowStage.REFUSED.value:
            refusals += 1
        if stage == WorkflowStage.APPROVAL_REQUIRED.value:
            approvals_pending += 1
        if stage == WorkflowStage.APPROVED.value:
            review_ready_pending += 1
        if stage == WorkflowStage.REVIEW_READY.value:
            proof_capture_pending += 1
    return WorkflowMonitorSummary(
        checked_at=utc_now(),
        total_workflows=len(latest),
        stage_counts=dict(stage_counts),
        refusals=refusals,
        approvals_pending=approvals_pending,
        review_ready_pending=review_ready_pending,
        proof_capture_pending=proof_capture_pending,
        updated_at=utc_now(),
        queue_health=get_queue_health(limit=limit),
        queue_summary=get_queue_summary(limit=limit),
    ).to_jsonable_dict()


def _parse_timestamp(value: Any) -> Optional[datetime]:
    text = _stage_name(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def find_stuck_workflows(stuck_after_minutes: int = 240, limit: int = 500) -> Dict[str, Any]:
    repo = _load_repository()
    records = repo.fetch_recent(limit=limit)
    latest = _latest_by_tender(records)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(stuck_after_minutes)))
    stuck: List[Dict[str, Any]] = []
    for tender_id, record in latest.items():
        stage = _stage_name(record.get("stage"))
        if stage not in _ACTIVE_STAGE_VALUES:
            continue
        updated_at = _parse_timestamp(record.get("updated_at") or record.get("created_at"))
        if updated_at and updated_at < cutoff:
            stuck.append(
                {
                    "tender_id": tender_id,
                    "stage": stage,
                    "updated_at": record.get("updated_at") or record.get("created_at") or "",
                    "age_minutes": int((cutoff - updated_at).total_seconds() / 60),
                }
            )
    return {
        "status": "ok",
        "checked_at": utc_now(),
        "stuck_after_minutes": int(stuck_after_minutes),
        "count": len(stuck),
        "items": stuck,
    }


def find_invalid_workflows(limit: int = 500) -> Dict[str, Any]:
    repo = _load_repository()
    records = repo.fetch_recent(limit=limit)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        tender_id = _stage_name(record.get("tender_id"))
        if tender_id and tender_id not in grouped:
            grouped[tender_id] = repo.fetch_history(tender_id, limit=limit)
    invalid: List[Dict[str, Any]] = []
    valid_stages = {stage.value for stage in WorkflowStage}
    for tender_id, history in grouped.items():
        reasons: List[str] = []
        previous_stage: Optional[WorkflowStage] = None
        for index, record in enumerate(history):
            stage_name = _stage_name(record.get("stage"))
            if stage_name not in valid_stages:
                reasons.append(f"invalid stage '{stage_name}'")
                continue
            stage = WorkflowStage(stage_name)
            if index == 0 and stage not in {WorkflowStage.DISCOVERED, WorkflowStage.REFUSED, WorkflowStage.ARCHIVED}:
                reasons.append(f"unexpected initial stage '{stage.value}'")
            if previous_stage is not None:
                try:
                    from app.core.workflow_state_engine import assert_can_transition

                    assert_can_transition(previous_stage, stage)
                except Exception as exc:
                    reasons.append(str(exc))
            previous_stage = stage
        if reasons:
            invalid.append({"tender_id": tender_id, "reasons": reasons, "history_length": len(history)})
    return {
        "status": "ok",
        "checked_at": utc_now(),
        "count": len(invalid),
        "items": invalid,
    }
