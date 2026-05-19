from __future__ import annotations

from typing import Any, Dict, List

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
