from __future__ import annotations

from typing import Any, Dict, Optional

from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.runtime_diagnostics import get_runtime_diagnostics
from app.monitoring.workflow_monitor import find_invalid_workflows, find_stuck_workflows, get_workflow_summary
from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.quality.context import build_quality_context
from app.quality.operator_recommendations import generate_operator_recommendations
from app.quality.quote_pack_quality import build_quote_pack_quality_report
from app.quality.supplier_pricing_quality import build_supplier_comparison_summary
from app.qualification.qualification_engine import build_qualification_summary, qualify_rfq
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.persistence.repositories import get_persistence_health


def build_operational_report(*, stuck_after_minutes: int = 240, limit: int = 500) -> Dict[str, Any]:
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
        "pricing_evidence_summary": supplier_quality.get("pricing_evidence_summary", {}),
        "pricing_validation_summary": supplier_quality.get("pricing_validation_summary", {}),
        "pricing_traceability_summary": supplier_quality.get("pricing_traceability_summary", {}),
        "quote_aging_summary": supplier_quality.get("quote_aging_summary", {}),
        "pricing_confidence_summary": supplier_quality.get("pricing_confidence_summary", {}),
        "operator_actions_summary": dashboard_summary.get("operator_actions_summary", {}),
        "operator_assignments_summary": dashboard_summary.get("operator_assignments_summary", {}),
        "operator_timeline_summary": dashboard_summary.get("operator_timeline_summary", {}),
        "operator_notifications_summary": dashboard_summary.get("operator_notifications_summary", {}),
        "operator_capacity_snapshot": dashboard_summary.get("operator_capacity_snapshot", {}),
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
        f"Missing runtime directories: {len(diagnostics.get('missing_directories', []))}",
        f"Workflow failures: {metrics.get('workflow_failures', 0)}",
        f"Persistence failures: {metrics.get('persistence_failures', 0)}",
        f"Audit failures: {metrics.get('audit_failures', 0)}",
        f"Pilot mode: {pilot.get('pilot_mode', {}).get('pilot_mode', 'disabled')}",
        f"Pilot readiness score: {pilot.get('pilot_readiness_score', 0.0)}",
        f"Qualification recommendation: {report.get('qualification_result', {}).get('recommendation', 'MANUAL_REVIEW')}",
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
        f"Operator notifications: {len(report.get('operator_notifications_summary', {}).get('notifications', []))}",
        f"Operator capacity remaining: {report.get('operator_capacity_snapshot', {}).get('remaining_capacity', 0)}",
        f"Supervised-live RFQs processed: {report.get('supervised_live_pilot_metrics', {}).get('rfqs_processed', 0)}",
        f"Governance audit no autonomous submission: {report.get('governance_audit_summary', {}).get('no_autonomous_submission', False)}",
        f"Incident recovery events: {report.get('incident_summary', {}).get('recovery_events', 0)}",
        f"Governance compliance score: {pilot.get('governance_compliance_score', 0.0)}",
        f"Manual governance integrity score: {pilot.get('manual_governance_integrity_score', 0.0)}",
        f"Pilot failures: {len(pilot.get('pilot_failures', []))}",
        f"Quote pack readiness: {quality.get('quality_score', 0.0)}",
        f"Tender quote conversion: {tender_analytics.get('quote_conversion_rate', 0.0)}",
        "Supervised-live governance: advisory only",
    ]
    return "\n".join(lines)
