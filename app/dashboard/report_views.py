from __future__ import annotations

from typing import Any, Dict

from app.dashboard.dashboard_service import get_dashboard_summary, get_operational_summary
from app.monitoring.reporting_service import build_operational_report


def get_workflow_report_view(limit: int = 100) -> Dict[str, Any]:
    summary = get_dashboard_summary(limit=limit)
    return {
        "workflow_summary": summary.get("workflow_summary", {}),
        "counts_by_stage": summary.get("counts_by_stage", {}),
        "queues": {
            "pending_approvals": summary.get("pending_approvals", 0),
            "pending_review_ready": summary.get("pending_review_ready", 0),
            "pending_proof_capture": summary.get("pending_proof_capture", 0),
        },
    }


def get_refusal_report_view(limit: int = 100) -> Dict[str, Any]:
    summary = get_dashboard_summary(limit=limit)
    return {
        "refused_workflows": summary.get("refused_workflows", 0),
        "operational_warnings": summary.get("operational_warnings", []),
    }


def get_pricing_report_view(limit: int = 100) -> Dict[str, Any]:
    report = build_operational_report(limit=limit)
    metrics = report.get("metrics", {}).get("metrics", {})
    return {
        "quote_packs_generated": metrics.get("quote_packs_generated", 0),
        "approvals_recorded": metrics.get("approvals_recorded", 0),
        "reviews_recorded": metrics.get("reviews_recorded", 0),
        "proofs_recorded": metrics.get("proofs_recorded", 0),
    }


def get_persistence_report_view(limit: int = 100) -> Dict[str, Any]:
    summary = get_operational_summary(limit=limit)
    return {
        "persistence": summary.get("persistence", {}),
        "monitoring": summary.get("monitoring", {}),
    }


def get_operational_report_view(limit: int = 100) -> Dict[str, Any]:
    return {
        "dashboard_summary": get_dashboard_summary(limit=limit),
        "operational_summary": get_operational_summary(limit=limit),
    }
