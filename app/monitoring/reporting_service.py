from __future__ import annotations

from typing import Any, Dict, Optional

from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.runtime_diagnostics import get_runtime_diagnostics
from app.monitoring.workflow_monitor import find_invalid_workflows, find_stuck_workflows, get_workflow_summary
from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.analytics.operator_performance_analytics import build_operator_performance_analytics
from app.analytics.review_queue_analytics import build_review_queue_analytics
from app.analytics.source_reliability_analytics import build_source_reliability_analytics
from app.business_intelligence.strategic_reporting import build_strategic_report
from app.governance.compliance_reporting import build_compliance_report
from app.governance.governance_risk_register import build_governance_risk_register
from app.quality.context import build_quality_context
from app.quality.operator_recommendations import generate_operator_recommendations
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
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.persistence.repositories import get_persistence_health
from app.persistence.persistence_reliability_report import build_persistence_reliability_report
from app.operations.backup_validation import get_backup_validation_summary
from app.operations.health_snapshots import get_health_snapshots
from app.operations.incident_tracker import get_incident_summary
from app.operations.runtime_alerts import get_runtime_alerts
from app.operations.runtime_metrics import get_runtime_metrics, get_runtime_snapshots
from app.observability.metrics_registry import get_observability_overview
from app.operator_ops import (
    get_operator_actions,
    get_operator_assignments,
    get_operator_capacity_snapshot,
    get_operator_notifications,
    get_operator_timeline,
)

def build_operational_report(*, stuck_after_minutes: int = 240, limit: int = 500) -> Dict[str, Any]:
    from app.stabilization.deployment_stability_checks import build_deployment_stability_report
    from app.stabilization.fallback_resilience import build_fallback_resilience_report
    from app.stabilization.governance_consistency_validator import build_governance_consistency_report
    from app.stabilization.operator_fatigue_monitor import build_operator_fatigue_report
    from app.stabilization.operator_ux_feedback import build_operator_ux_feedback_report
    from app.stabilization.runtime_cleanup import build_runtime_cleanup_report
    from app.stabilization.runtime_stability_engine import build_runtime_stability_report
    from app.stabilization.telemetry_noise_reduction import build_telemetry_noise_reduction_report

    metrics = get_metrics_snapshot()
    pilot = build_pilot_readiness_report(limit=limit)
    tender_analytics = build_tender_success_analytics(limit=limit)
    quality_context = build_quality_context(limit=limit)
    quality_summary = build_quote_pack_quality_report(quality_context.get("quote_pack_payload") or {"artifacts": []})
    supplier_quality = build_supplier_comparison_summary(quality_context.get("supplier_quotes") or [])
    qualification_result = qualify_rfq(quality_context.get("rfq_payload")) if quality_context.get("rfq_payload") else {}
    recommendations = generate_operator_recommendations(
        workflow_summary=get_workflow_summary(limit=limit),
        quality_summary=quality_summary,
    )
    return {
        "system_health": get_system_health(),
        "workflow_summary": get_workflow_summary(limit=limit),
        "stuck_workflows": find_stuck_workflows(stuck_after_minutes=stuck_after_minutes, limit=limit),
        "invalid_workflows": find_invalid_workflows(limit=limit),
        "persistence": get_persistence_health(),
        "runtime_diagnostics": get_runtime_diagnostics(),
        "metrics": metrics,
        "pilot": pilot,
        "quality_summary": quality_summary,
        "supplier_pricing_summary": supplier_quality,
        "qualification_summary": build_qualification_summary([qualification_result] if qualification_result else []),
        "qualification_result": qualification_result,
        "tender_success_analytics": tender_analytics,
        "operator_recommendations": recommendations,
        "supervised_live_governance_summary": pilot.get("supervised_live_governance_summary", {}),
        "governance_compliance_score": pilot.get("governance_compliance_score", 0.0),
        "manual_governance_integrity_score": pilot.get("manual_governance_integrity_score", 0.0),
        "supervised_live_pilot_metrics": pilot.get("supervised_live_pilot_metrics", {}),
        "governance_audit_summary": pilot.get("governance_audit_summary", {}),
        "incident_summary": pilot.get("incident_summary", {}),
        "operational_reliability_summary": pilot.get("operational_reliability_summary", {}),
        "governance_compliance_report": build_compliance_report(limit=limit),
        "governance_risk_register": build_governance_risk_register(),
        "pricing_evidence_summary": supplier_quality.get("pricing_evidence_summary", {}),
        "pricing_validation_summary": supplier_quality.get("pricing_validation_summary", {}),
        "pricing_traceability_summary": supplier_quality.get("pricing_traceability_summary", {}),
        "quote_aging_summary": supplier_quality.get("quote_aging_summary", {}),
        "pricing_confidence_summary": supplier_quality.get("pricing_confidence_summary", {}),
        "runtime_metrics_summary": get_runtime_metrics(limit=limit),
        "runtime_alerts_summary": get_runtime_alerts(limit=limit),
        "observability_summary": get_observability_overview(limit=limit),
        "health_snapshot": get_health_snapshots(limit=limit),
        "runtime_snapshots": get_runtime_snapshots(limit=limit),
        "backup_validation_summary": get_backup_validation_summary(),
        "persistence_reliability_report": build_persistence_reliability_report(),
        "incident_summary_runtime": get_incident_summary(limit=limit),
        "stabilization_summary": {
            "runtime_stability": build_runtime_stability_report(limit=limit),
            "fallback_resilience": build_fallback_resilience_report(limit=limit),
            "telemetry_noise": build_telemetry_noise_reduction_report(limit=limit),
            "governance_consistency": build_governance_consistency_report(limit=limit),
            "operator_fatigue": build_operator_fatigue_report(limit=limit),
            "operator_feedback": build_operator_ux_feedback_report(limit=limit),
            "runtime_cleanup": build_runtime_cleanup_report(limit=limit),
            "deployment_stability": build_deployment_stability_report(limit=limit),
        },
        "operator_performance_analytics": build_operator_performance_analytics(limit=limit),
        "review_queue_analytics": build_review_queue_analytics(limit=limit),
        "source_reliability_analytics": build_source_reliability_analytics(limit=limit),
        "business_intelligence_summary": build_strategic_report(limit=limit),
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
        "operator_actions_summary": get_operator_actions(limit=limit),
        "operator_assignments_summary": get_operator_assignments(limit=limit),
        "operator_timeline_summary": get_operator_timeline(limit=limit),
        "operator_notifications_summary": get_operator_notifications(limit=limit),
        "operator_capacity_snapshot": get_operator_capacity_snapshot(),
        "qualification_supplier_evidence_score": qualification_result.get("supplier_evidence_score", 0.0),
        "qualification_pricing_confidence": qualification_result.get("pricing_confidence", {}),
        "qualification_pricing_validation": qualification_result.get("pricing_validation", {}),
        "qualification_quote_aging": qualification_result.get("quote_aging", {}),
        "qualification_pricing_traceability_summary": qualification_result.get("pricing_traceability_summary", {}),
        "qualification_stale_quote_warning": qualification_result.get("stale_quote_warning", False),
        "qualification_manual_pricing_review_required": qualification_result.get("manual_pricing_review_required", False),
        "failure_summary": {
            "workflow_failures": metrics["metrics"].get("workflow_failures", 0),
            "persistence_failures": metrics["metrics"].get("persistence_failures", 0),
            "audit_failures": metrics["metrics"].get("audit_failures", 0),
            "pilot_failures": len(pilot.get("pilot_failures", [])),
            "pilot_recovery_events": pilot.get("pilot_metrics", {}).get("recovery_events", 0),
        },
    }


def render_operational_report_text(report: Optional[Dict[str, Any]] = None) -> str:
    report = report or build_operational_report()
    health = report.get("system_health", {})
    workflow = report.get("workflow_summary", {})
    metrics = report.get("metrics", {}).get("metrics", {})
    persistence = report.get("persistence", {})
    diagnostics = report.get("runtime_diagnostics", {})
    pilot = report.get("pilot", {})
    quality = report.get("quality_summary", {})
    tender_analytics = report.get("tender_success_analytics", {})
    lines = [
        f"System status: {health.get('status', 'unknown')}",
        f"Environment: {health.get('environment', '')} / {health.get('production_mode', '')}",
        f"Workflow total: {workflow.get('total_workflows', 0)}",
        f"Refusals: {workflow.get('refusals', 0)}",
        f"Approvals pending: {workflow.get('approvals_pending', 0)}",
        f"Review ready pending: {workflow.get('review_ready_pending', 0)}",
        f"Proof capture pending: {workflow.get('proof_capture_pending', 0)}",
        f"DB available: {persistence.get('db_available', persistence.get('db_ready', False))}",
        f"Database backend: {report.get('persistence_reliability_report', {}).get('health', {}).get('database_backend', 'sqlite')}",
        f"Queue backend: {report.get('persistence_reliability_report', {}).get('health', {}).get('queue_backend', 'local')}",
        f"Backup age days: {report.get('backup_validation_summary', {}).get('latest_backup_age_days', -1)}",
        f"Observability status: {report.get('observability_summary', {}).get('status', 'fallback')}",
        f"Observability alerts: {report.get('observability_summary', {}).get('summary', {}).get('runtime_alerts', 0)}",
        f"Stability score: {report.get('stabilization_summary', {}).get('runtime_stability', {}).get('stability_score', 0.0)}",
        f"Restore readiness: {report.get('persistence_reliability_report', {}).get('restore_readiness', {}).get('status', 'blocked')}",
        f"Missing runtime directories: {len(diagnostics.get('missing_directories', []))}",
        f"Workflow failures: {metrics.get('workflow_failures', 0)}",
        f"Persistence failures: {metrics.get('persistence_failures', 0)}",
        f"Audit failures: {metrics.get('audit_failures', 0)}",
        f"Pilot mode: {pilot.get('pilot_mode', {}).get('pilot_mode', 'disabled')}",
        f"Pilot readiness score: {pilot.get('pilot_readiness_score', 0.0)}",
        f"Qualification recommendation: {report.get('qualification_result', {}).get('recommendation', 'MANUAL_REVIEW')}",
        f"Executive BI profit projection: {report.get('business_intelligence_summary', {}).get('revenue_projection', {}).get('summary', {}).get('projected_rfq_opportunity_value', 0.0)}",
        f"Executive BI governance summary: {report.get('business_intelligence_summary', {}).get('governance_summary', {}).get('summary', {}).get('governance_incidents', 0)}",
        f"Qualification readiness state: {report.get('qualification_result', {}).get('readiness_state', 'HIGH_RISK')}",
        f"Qualification GO count: {report.get('qualification_summary', {}).get('recommendation_counts', {}).get('GO', 0)}",
        f"Qualification manual review count: {report.get('qualification_summary', {}).get('recommendation_counts', {}).get('MANUAL_REVIEW', 0)}",
        f"Qualification reject count: {report.get('qualification_summary', {}).get('recommendation_counts', {}).get('REJECT', 0)}",
        f"Supplier match score: {report.get('qualification_result', {}).get('supplier_match_score', 0.0)}",
        f"Supplier evidence score: {report.get('qualification_result', {}).get('supplier_evidence_score', 0.0)}",
        f"Pricing confidence: {report.get('qualification_result', {}).get('pricing_confidence', {}).get('overall_pricing_confidence', 0.0)}",
        f"Manual pricing review required: {report.get('qualification_result', {}).get('manual_pricing_review_required', False)}",
        f"Stale quote warning: {report.get('qualification_result', {}).get('stale_quote_warning', False)}",
        f"Pricing evidence completeness: {report.get('supplier_pricing_summary', {}).get('pricing_evidence_summary', {}).get('average_evidence_completeness', 0.0)}",
        f"Pricing traceability count: {report.get('supplier_pricing_summary', {}).get('pricing_traceability_summary', {}).get('quote_count', 0)}",
        f"Operator actions recorded: {report.get('operator_actions_summary', {}).get('total', 0)}",
        f"Operator assignments active: {report.get('operator_assignments_summary', {}).get('summary', {}).get('active_assignments', 0)}",
        f"Productivity urgent items: {report.get('productivity_summary', {}).get('queue_optimization', {}).get('summary', {}).get('urgent', 0)}",
        f"Productivity throughput/hr: {report.get('productivity_summary', {}).get('review_efficiency', {}).get('rfqs_reviewed_per_hour', 0)}",
        f"Operator notifications: {len(report.get('operator_notifications_summary', {}).get('notifications', []))}",
        f"Operator capacity remaining: {report.get('operator_capacity_snapshot', {}).get('remaining_capacity', 0)}",
        f"Supervised-live RFQs processed: {report.get('supervised_live_pilot_metrics', {}).get('rfqs_processed', 0)}",
        f"Governance audit no autonomous submission: {report.get('governance_audit_summary', {}).get('no_autonomous_submission', False)}",
        f"Incident recovery events: {report.get('incident_summary', {}).get('recovery_events', 0)}",
        f"Governance compliance score: {pilot.get('governance_compliance_score', 0.0)}",
        f"Manual governance integrity score: {pilot.get('manual_governance_integrity_score', 0.0)}",
        f"Governance risk register items: {len(report.get('governance_risk_register', {}).get('risks', []))}",
        f"Pilot failures: {len(pilot.get('pilot_failures', []))}",
        f"Quote pack readiness: {quality.get('quality_score', 0.0)}",
        f"Tender quote conversion: {tender_analytics.get('quote_conversion_rate', 0.0)}",
        "Supervised-live governance: advisory only",
    ]
    return "\n".join(lines)
