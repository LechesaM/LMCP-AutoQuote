from __future__ import annotations

from typing import Any, Dict, List

from app.orchestration.queue_manager import get_jobs_by_status
from app.orchestration.queue_monitor import find_stalled_jobs, get_queue_health, get_queue_summary
from app.orchestration.workflow_recovery import scan_for_recovery_candidates
from app.core.runtime_paths import get_runtime_paths
from app.persistence.repositories import WorkflowRepository


def _workflow_repo() -> WorkflowRepository:
    paths = get_runtime_paths()
    return WorkflowRepository(jsonl_path=paths.manual_production_file("workflow_state.jsonl"))


def _queue(stage: str, limit: int = 100) -> List[Dict[str, Any]]:
    return _workflow_repo().fetch_current_by_stage(stage, limit=limit)


def get_pending_approval_queue(limit: int = 100) -> List[Dict[str, Any]]:
    return _queue("approval_required", limit=limit)


def get_review_ready_queue(limit: int = 100) -> List[Dict[str, Any]]:
    return _queue("approved", limit=limit)


def get_proof_capture_queue(limit: int = 100) -> List[Dict[str, Any]]:
    return _queue("review_ready", limit=limit)


def get_refused_queue(limit: int = 100) -> List[Dict[str, Any]]:
    return _queue("refused", limit=limit)


def get_archived_queue(limit: int = 100) -> List[Dict[str, Any]]:
    return _queue("archived", limit=limit)


def get_active_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    return get_jobs_by_status(limit=limit)


def get_failed_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    return get_jobs_by_status(status="failed", limit=limit)


def get_retry_queue(limit: int = 100) -> List[Dict[str, Any]]:
    return get_jobs_by_status(status="retry_pending", limit=limit)


def get_blocked_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    return get_jobs_by_status(status="blocked", limit=limit)


def get_recovery_candidates(limit: int = 100, stuck_after_minutes: int = 240) -> Dict[str, Any]:
    return scan_for_recovery_candidates(stuck_after_minutes=stuck_after_minutes, limit=limit)


def get_queue_overview(limit: int = 100) -> Dict[str, Any]:
    return {
        "health": get_queue_health(limit=limit),
        "summary": get_queue_summary(limit=limit),
        "stalled": find_stalled_jobs(limit=limit),
        "active_jobs": get_active_jobs(limit=limit),
        "failed_jobs": get_failed_jobs(limit=limit),
        "retry_queue": get_retry_queue(limit=limit),
        "blocked_jobs": get_blocked_jobs(limit=limit),
        "recovery_candidates": get_recovery_candidates(limit=limit),
    }
