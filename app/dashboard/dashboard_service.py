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
from app.productivity.bulk_review_actions import build_bulk_action_preview
from app.productivity.evidence_review_accelerator import build_evidence_acceleration_summary
from app.productivity.operator_focus_sessions import build_focus_session_summary
from app.productivity.operator_shortcuts import build_operator_shortcut_catalog
from app.productivity.operator_workload_balancer import build_operator_workload_summary
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics
from app.productivity.review_priority_engine import build_review_priority_summary
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary
from app.pilot.pilot_mode import get_pilot_execution_metadata
from app.pilot.pilot_metrics import get_pilot_metrics
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.pilot.pilot_run_service import get_pilot_failures
from app.persistence.repositories import WorkflowRepository, get_persistence_health
from app.operations.backup_validation import get_backup_validation_summary
from app.operations.health_snapshots import get_health_snapshots
from app.operations.incident_tracker import get_incident_summary
from app.operations.runtime_alerts import get_runtime_alerts
from app.operations.runtime_metrics import get_runtime_metrics, get_runtime_snapshots
from app.observability.metrics_registry import get_observability_overview
from app.analytics.operator_performance_analytics import build_operator_performance_analytics
from app.analytics.review_queue_analytics import build_review_queue_analytics
from app.analytics.source_reliability_analytics import build_source_reliability_analytics
from app.business_intelligence.executive_dashboard import build_executive_dashboard
from app.governance.compliance_reporting import build_compliance_report
from app.governance.governance_risk_register import build_governance_risk_register
from app.business_intelligence.strategic_reporting import build_strategic_report
from app.operator_ops import (
    get_operator_actions,
    get_operator_assignments,
    get_operator_capacity_snapshot,
    get_operator_notifications,
    get_operator_timeline,
)


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
        "supervised_live_pilot_metrics": pilot_readiness.get("supervised_live_pilot_metrics", {}),
        "governance_audit_summary": pilot_readiness.get("governance_audit_summary", {}),
        "incident_summary": pilot_readiness.get("incident_summary", {}),
        "operational_reliability_summary": pilot_readiness.get("operational_reliability_summary", {}),
        "pilot_warnings": pilot_readiness.get("warnings", []),
        "quality_summary": {
            "rfq_extraction": quality_summary,
            "pricing_schedule": schedule_quality,
            "quote_pack": quote_pack_quality,
            "supplier_pricing": supplier_quality,
        },
        "operator_actions_summary": get_operator_actions(limit=limit),
        "operator_assignments_summary": get_operator_assignments(limit=limit),
        "operator_timeline_summary": get_operator_timeline(limit=limit),
        "operator_notifications_summary": get_operator_notifications(limit=limit),
        "operator_capacity_snapshot": get_operator_capacity_snapshot(),
        "runtime_metrics_summary": get_runtime_metrics(limit=limit),
        "runtime_alerts_summary": get_runtime_alerts(limit=limit),
        "observability_summary": get_observability_overview(limit=limit),
        "health_snapshot": get_health_snapshots(limit=limit),
        "runtime_snapshots": get_runtime_snapshots(limit=limit),
        "backup_validation_summary": get_backup_validation_summary(),
        "incident_summary_runtime": get_incident_summary(limit=limit),
        "operator_performance_analytics": build_operator_performance_analytics(limit=limit),
        "review_queue_analytics": build_review_queue_analytics(limit=limit),
        "source_reliability_analytics": build_source_reliability_analytics(limit=limit),
        "business_intelligence_summary": build_executive_dashboard(limit=limit),
        "strategic_report_summary": build_strategic_report(limit=limit),
        "productivity_summary": {
            "workload": build_operator_workload_summary(limit=limit),
            "queue_optimization": build_review_queue_optimization_summary(limit=limit),
            "review_efficiency": build_review_efficiency_analytics(limit=limit),
            "focus_sessions": build_focus_session_summary(limit=limit),
            "review_priorities": build_review_priority_summary(limit=limit),
            "evidence_acceleration": build_evidence_acceleration_summary(limit=limit),
            "shortcuts": build_operator_shortcut_catalog(),
            "bulk_preview": build_bulk_action_preview(operator_id="", tender_ids=[], action="preview"),
        },
        "qualification_summary": build_qualification_summary([qualification_result] if qualification_result else []),
        "qualification_result": qualification_result,
        "qualification_recommendation": qualification_result.get("recommendation", "MANUAL_REVIEW"),
        "qualification_readiness_state": qualification_result.get("readiness_state", "HIGH_RISK"),
        "qualification_risk_breakdown": qualification_result.get("risk_breakdown", {}),
        "qualification_supplier_match_score": qualification_result.get("supplier_match_score", 0.0),
        "qualification_supplier_evidence_score": qualification_result.get("supplier_evidence_score", 0.0),
        "qualification_pricing_confidence": qualification_result.get("pricing_confidence", {}),
        "qualification_pricing_validation": qualification_result.get("pricing_validation", {}),
        "qualification_quote_aging": qualification_result.get("quote_aging", {}),
        "qualification_pricing_traceability_summary": qualification_result.get("pricing_traceability_summary", {}),
        "qualification_stale_quote_warning": qualification_result.get("stale_quote_warning", False),
        "qualification_manual_pricing_review_required": qualification_result.get("manual_pricing_review_required", False),
        "qualification_next_operator_action": qualification_result.get("next_operator_action", ""),
        "qualification_manual_review_triggers": qualification_result.get("manual_review_triggers", []),
        "qualification_detected_language_patterns": qualification_result.get("detected_language_patterns", []),
        "pricing_evidence_summary": supplier_quality.get("pricing_evidence_summary", {}),
        "pricing_validation_summary": supplier_quality.get("pricing_validation_summary", {}),
        "pricing_traceability_summary": supplier_quality.get("pricing_traceability_summary", {}),
        "quote_aging_summary": supplier_quality.get("quote_aging_summary", {}),
        "pricing_confidence_summary": supplier_quality.get("pricing_confidence_summary", {}),
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
        "qualification_recommendation": report.get("pilot", {}).get("qualification_result", {}).get("recommendation", "MANUAL_REVIEW"),
        "qualification_readiness_state": report.get("pilot", {}).get("qualification_result", {}).get("readiness_state", "HIGH_RISK"),
        "qualification_risk_breakdown": report.get("pilot", {}).get("qualification_result", {}).get("risk_breakdown", {}),
        "qualification_supplier_match_score": report.get("pilot", {}).get("qualification_result", {}).get("supplier_match_score", 0.0),
        "qualification_supplier_evidence_score": report.get("pilot", {}).get("qualification_result", {}).get("supplier_evidence_score", 0.0),
        "qualification_pricing_confidence": report.get("pilot", {}).get("qualification_result", {}).get("pricing_confidence", {}),
        "qualification_pricing_validation": report.get("pilot", {}).get("qualification_result", {}).get("pricing_validation", {}),
        "qualification_quote_aging": report.get("pilot", {}).get("qualification_result", {}).get("quote_aging", {}),
        "qualification_pricing_traceability_summary": report.get("pilot", {}).get("qualification_result", {}).get("pricing_traceability_summary", {}),
        "qualification_stale_quote_warning": report.get("pilot", {}).get("qualification_result", {}).get("stale_quote_warning", False),
        "qualification_manual_pricing_review_required": report.get("pilot", {}).get("qualification_result", {}).get("manual_pricing_review_required", False),
        "qualification_next_operator_action": report.get("pilot", {}).get("qualification_result", {}).get("next_operator_action", ""),
        "qualification_manual_review_triggers": report.get("pilot", {}).get("qualification_result", {}).get("manual_review_triggers", []),
        "qualification_detected_language_patterns": report.get("pilot", {}).get("qualification_result", {}).get("detected_language_patterns", []),
        "operator_actions_summary": report.get("operator_actions_summary", {}),
        "operator_assignments_summary": report.get("operator_assignments_summary", {}),
        "operator_timeline_summary": report.get("operator_timeline_summary", {}),
        "operator_notifications_summary": report.get("operator_notifications_summary", {}),
        "operator_capacity_snapshot": report.get("operator_capacity_snapshot", {}),
        "health_snapshot": report.get("health_snapshot", {}),
        "runtime_snapshots": report.get("runtime_snapshots", {}),
        "observability_summary": report.get("observability_summary", {}),
        "pricing_evidence_summary": report.get("supplier_pricing_summary", {}).get("pricing_evidence_summary", {}),
        "pricing_validation_summary": report.get("supplier_pricing_summary", {}).get("pricing_validation_summary", {}),
        "pricing_traceability_summary": report.get("supplier_pricing_summary", {}).get("pricing_traceability_summary", {}),
        "quote_aging_summary": report.get("supplier_pricing_summary", {}).get("quote_aging_summary", {}),
        "pricing_confidence_summary": report.get("supplier_pricing_summary", {}).get("pricing_confidence_summary", {}),
        "supervised_live_governance_summary": report.get("pilot", {}).get("supervised_live_governance_summary", {}),
        "supervised_live_pilot_metrics": report.get("pilot", {}).get("supervised_live_pilot_metrics", {}),
        "governance_audit_summary": report.get("pilot", {}).get("governance_audit_summary", {}),
        "incident_summary": report.get("pilot", {}).get("incident_summary", {}),
        "operational_reliability_summary": report.get("pilot", {}).get("operational_reliability_summary", {}),
        "governance_compliance_score": report.get("pilot", {}).get("governance_compliance_score", 0.0),
        "manual_governance_integrity_score": report.get("pilot", {}).get("manual_governance_integrity_score", 0.0),
        "warnings": report.get("runtime_diagnostics", {}).get("warnings", []),
    }
