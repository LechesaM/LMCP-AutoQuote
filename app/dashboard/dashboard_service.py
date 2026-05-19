from __future__ import annotations

from typing import Any, Dict, List

from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.dashboard.workflow_queue_service import get_queue_overview
from app.pilot.pilot_mode import get_pilot_execution_metadata
from app.pilot.pilot_metrics import get_pilot_metrics
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.pilot.pilot_run_service import get_pilot_failures
from app.persistence.repositories import WorkflowRepository, get_persistence_health


def _workflow_repo() -> WorkflowRepository:
    from app.core.runtime_paths import get_runtime_paths

    paths = get_runtime_paths()
    return WorkflowRepository(jsonl_path=paths.manual_production_file("workflow_state.jsonl"))


def _records_for_stage(stage: str, limit: int = 100) -> List[Dict[str, Any]]:
    return _workflow_repo().fetch_current_by_stage(stage, limit=limit)


def get_recent_workflows(limit: int = 25) -> List[Dict[str, Any]]:
    return _workflow_repo().fetch_recent(limit=limit)


def get_recent_refusals(limit: int = 25) -> List[Dict[str, Any]]:
    return _records_for_stage("refused", limit=limit)


def get_recent_approvals(limit: int = 25) -> List[Dict[str, Any]]:
    return _records_for_stage("approved", limit=limit)


def get_recent_reviews(limit: int = 25) -> List[Dict[str, Any]]:
    return _records_for_stage("review_ready", limit=limit)


def get_recent_proofs(limit: int = 25) -> List[Dict[str, Any]]:
    return _records_for_stage("proof_recorded", limit=limit)


def get_dashboard_summary(limit: int = 100) -> Dict[str, Any]:
    workflow_summary = get_workflow_summary(limit=limit)
    operational = build_operational_report(limit=limit)
    queue_overview = get_queue_overview(limit=limit)
    pilot_readiness = build_pilot_readiness_report(limit=limit)
    pilot_metrics = get_pilot_metrics()
    return {
        "workflow_summary": workflow_summary,
        "operational_summary": get_operational_summary(limit=limit),
        "queue_overview": queue_overview,
        "pilot_mode": get_pilot_execution_metadata(),
        "pilot_metrics": pilot_metrics,
        "pilot_failures": get_pilot_failures(limit=limit),
        "pilot_readiness_score": pilot_readiness.get("pilot_readiness_score", 0.0),
        "pilot_warnings": pilot_readiness.get("warnings", []),
        "counts_by_stage": workflow_summary.get("stage_counts", {}),
        "pending_approvals": workflow_summary.get("approvals_pending", 0),
        "pending_review_ready": workflow_summary.get("review_ready_pending", 0),
        "pending_proof_capture": workflow_summary.get("proof_capture_pending", 0),
        "refused_workflows": len(get_recent_refusals(limit=limit)),
        "archived_workflows": workflow_summary.get("stage_counts", {}).get("archived", 0),
        "operational_warnings": operational.get("runtime_diagnostics", {}).get("warnings", []),
        "persistence_health": get_persistence_health(),
        "workflow_health": workflow_summary,
        "queue_health": queue_overview.get("health", {}),
        "queue_summary": queue_overview.get("summary", {}),
    }


def get_operational_summary(limit: int = 100) -> Dict[str, Any]:
    report = build_operational_report(limit=limit)
    return {
        "status": report.get("system_health", {}).get("status", "unknown"),
        "system_health": report.get("system_health", {}),
        "workflow_summary": report.get("workflow_summary", {}),
        "persistence": report.get("persistence", {}),
        "monitoring": report.get("runtime_diagnostics", {}),
        "metrics": report.get("metrics", {}),
        "warnings": report.get("runtime_diagnostics", {}).get("warnings", []),
    }
