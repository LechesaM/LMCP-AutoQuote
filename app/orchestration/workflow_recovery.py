from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.core import workflow_state_engine
from app.domain.workflow import WorkflowStage
from app.orchestration.job_history import append_history_event
from app.orchestration.job_models import QueueJobStatus
from app.orchestration.queue_manager import get_jobs_by_status, retry_job, archive_job
from app.persistence.repositories import WorkflowRepository, get_persistence_health


def _parse_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def scan_for_recovery_candidates(stuck_after_minutes: int = 240, limit: int = 500) -> Dict[str, Any]:
    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    current = repo.fetch_current_states(limit=limit)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(stuck_after_minutes)))
    candidates: List[Dict[str, Any]] = []
    orphaned_workflows: List[str] = []
    persistence_mismatch: List[Dict[str, Any]] = []
    for item in current:
        stage = str(item.get("stage") or "")
        updated = _parse_timestamp(item.get("updated_at") or item.get("created_at"))
        tender_id = str(item.get("tender_id") or "")
        history = workflow_state_engine.get_transition_history(tender_id, limit=limit)
        history_items = history.get("items", [])
        if not history_items:
            orphaned_workflows.append(tender_id)
        elif history_items:
            latest_history = history_items[-1]
            if str(latest_history.get("stage") or latest_history.get("workflow_stage") or "") != stage:
                persistence_mismatch.append(
                    {
                        "tender_id": tender_id,
                        "current_stage": stage,
                        "history_stage": str(latest_history.get("stage") or latest_history.get("workflow_stage") or ""),
                    }
                )
        if stage in {WorkflowStage.APPROVAL_REQUIRED.value, WorkflowStage.APPROVED.value, WorkflowStage.REVIEW_READY.value, WorkflowStage.PROOF_RECORDED.value}:
            if updated and updated < cutoff:
                candidates.append(
                    {
                        "tender_id": tender_id,
                        "stage": stage,
                        "updated_at": item.get("updated_at") or item.get("created_at") or "",
                        "age_minutes": int((cutoff - updated).total_seconds() / 60),
                    }
                )
    queue_jobs = get_jobs_by_status(limit=limit)
    blocked = [item for item in queue_jobs if str(item.get("status")) == QueueJobStatus.BLOCKED.value]
    failed = [item for item in queue_jobs if str(item.get("status")) == QueueJobStatus.FAILED.value]
    return {
        "status": "ok",
        "recovery_candidates": candidates,
        "blocked_jobs": blocked,
        "failed_jobs": failed,
        "orphaned_workflows": orphaned_workflows,
        "persistence_mismatch": persistence_mismatch,
        "persistence_health": get_persistence_health(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def recover_job(job_id: str, actor: str = "", operator: str = "", approve: bool = False) -> Dict[str, Any]:
    jobs = get_jobs_by_status(limit=1000, job_id=job_id)
    if not jobs:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(jobs[0])
    if approve and str(current.get("status")) in {QueueJobStatus.FAILED.value, QueueJobStatus.RETRY_PENDING.value}:
        result = retry_job(job_id, reason="operator approved recovery", actor=actor, operator=operator)
    else:
        result = archive_job(job_id, actor=actor, operator=operator, reason="recovery archived")
    append_history_event("recovery", {"job_id": job_id, "actor": actor, "operator": operator, "result": result})
    return result


def recover_workflow(tender_id: str, actor: str = "", operator: str = "", reason: str = "") -> Dict[str, Any]:
    current = workflow_state_engine.get_current_state(tender_id)
    if current.stage not in {
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        WorkflowStage.REVIEW_READY,
        WorkflowStage.PROOF_RECORDED,
        WorkflowStage.REFUSED,
    }:
        return {
            "status": "blocked",
            "reason": f"workflow stage {current.stage.value} is not eligible for recovery",
            "tender_id": tender_id,
        }
    append_history_event(
        "workflow_recovery",
        {"tender_id": tender_id, "actor": actor, "operator": operator, "reason": reason, "stage": current.stage.value},
    )
    return {
        "status": "ok",
        "tender_id": tender_id,
        "stage": current.stage.value,
        "reason": reason,
        "operator": operator,
    }


def generate_recovery_report(limit: int = 500) -> Dict[str, Any]:
    candidates = scan_for_recovery_candidates(limit=limit)
    return {
        "status": "ok",
        "recovery_candidates": candidates.get("recovery_candidates", []),
        "blocked_jobs": candidates.get("blocked_jobs", []),
        "failed_jobs": candidates.get("failed_jobs", []),
        "orphaned_workflows": candidates.get("orphaned_workflows", []),
        "persistence_mismatch": candidates.get("persistence_mismatch", []),
        "persistence_health": candidates.get("persistence_health", {}),
        "checked_at": candidates.get("checked_at"),
    }
