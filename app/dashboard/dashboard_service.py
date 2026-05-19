from __future__ import annotations

from typing import Any, Dict, List

from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.dashboard.workflow_queue_service import get_queue_overview
from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.quality.context import build_quality_context
from app.quality.extraction_quality import build_rfq_extraction_quality_report
from app.quality.operator_recommendations import generate_operator_recommendations
from app.quality.pricing_schedule_quality import build_pricing_schedule_quality_report
from app.quality.quote_pack_quality import build_quote_pack_quality_report
from app.quality.supplier_pricing_quality import build_supplier_comparison_summary
from app.qualification.qualification_engine import build_qualification_summary, qualify_rfq
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
    quality_context = build_quality_context(limit=limit)
    quality_summary = build_rfq_extraction_quality_report(quality_context.get("rfq_payload") or {"line_items": []})
    schedule_quality = build_pricing_schedule_quality_report(quality_context.get("schedule_payload") or {"rows": []})
    quote_pack_quality = build_quote_pack_quality_report(quality_context.get("quote_pack_payload") or {"artifacts": []})
    supplier_quality = build_supplier_comparison_summary(quality_context.get("supplier_quotes") or [])
    qualification_result = qualify_rfq(quality_context.get("rfq_payload")) if quality_context.get("rfq_payload") else {}
    tender_analytics = build_tender_success_analytics(limit=limit)
    recommendations = generate_operator_recommendations(
        workflow_summary=workflow_summary,
        quality_summary=quote_pack_quality,
        queue_summary=queue_overview.get("summary", {}),
    )
    return {
        "workflow_summary": workflow_summary,
        "operational_summary": get_operational_summary(limit=limit),
        "queue_overview": queue_overview,
        "pilot_mode": get_pilot_execution_metadata(),
        "pilot_metrics": pilot_metrics,
        "pilot_failures": get_pilot_failures(limit=limit),
        "pilot_readiness_score": pilot_readiness.get("pilot_readiness_score", 0.0),
        "governance_compliance_score": pilot_readiness.get("governance_compliance_score", 0.0),
        "manual_governance_integrity_score": pilot_readiness.get("manual_governance_integrity_score", 0.0),
        "supervised_live_governance_summary": pilot_readiness.get("supervised_live_governance_summary", {}),
        "pilot_warnings": pilot_readiness.get("warnings", []),
        "quality_summary": {
            "rfq_extraction": quality_summary,
            "pricing_schedule": schedule_quality,
            "quote_pack": quote_pack_quality,
            "supplier_pricing": supplier_quality,
        },
        "qualification_summary": build_qualification_summary([qualification_result] if qualification_result else []),
        "qualification_result": qualification_result,
        "operator_recommendations": recommendations,
        "tender_success_analytics": tender_analytics,
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
        "qualification_summary": report.get("pilot", {}).get("qualification_summary", {}),
        "supervised_live_governance_summary": report.get("pilot", {}).get("supervised_live_governance_summary", {}),
        "governance_compliance_score": report.get("pilot", {}).get("governance_compliance_score", 0.0),
        "manual_governance_integrity_score": report.get("pilot", {}).get("manual_governance_integrity_score", 0.0),
        "warnings": report.get("runtime_diagnostics", {}).get("warnings", []),
    }
