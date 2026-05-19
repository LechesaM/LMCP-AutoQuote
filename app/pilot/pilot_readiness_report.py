from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now
from app.monitoring.metrics_service import get_metrics_snapshot
from app.pilot.pilot_metrics import calculate_readiness_score, calculate_success_rate, get_pilot_metrics
from app.pilot.pilot_run_service import get_pilot_failures, get_pilot_runs, get_pilot_summary, get_pilot_successes
from app.pilot.pilot_mode import get_pilot_execution_metadata
from app.pilot.pilot_signoff import get_pilot_signoffs
from app.analytics.tender_success_analytics import build_tender_success_analytics
from app.quality.context import build_quality_context
from app.quality.quote_pack_quality import build_quote_pack_quality_report
from app.qualification.qualification_engine import build_qualification_summary, qualify_rfq


class PilotReadinessReport(StrictBaseModel):
    status: str = "unknown"
    checked_at: Any = None
    pilot_mode: Dict[str, Any] = Field(default_factory=dict)
    pilot_metrics: Dict[str, Any] = Field(default_factory=dict)
    pilot_summary: Dict[str, Any] = Field(default_factory=dict)
    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    tender_success_analytics: Dict[str, Any] = Field(default_factory=dict)
    pilot_failures: list[Dict[str, Any]] = Field(default_factory=list)
    pilot_successes: list[Dict[str, Any]] = Field(default_factory=list)
    pilot_signoffs: list[Dict[str, Any]] = Field(default_factory=list)
    pilot_readiness_score: float = 0.0
    workflow_correctness_score: float = 0.0
    persistence_reliability_score: float = 0.0
    operational_reliability_score: float = 0.0
    operator_governance_score: float = 0.0
    refusal_handling_score: float = 0.0
    recovery_readiness_score: float = 0.0
    supervised_live_governance_summary: Dict[str, Any] = Field(default_factory=dict)
    governance_compliance_score: float = 0.0
    manual_governance_integrity_score: float = 0.0
    qualification_summary: Dict[str, Any] = Field(default_factory=dict)
    qualification_result: Dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def build_pilot_readiness_report(limit: int = 100) -> Dict[str, Any]:
    metrics = get_pilot_metrics()
    workflow_metrics = get_metrics_snapshot().get("metrics", {})
    summary = get_pilot_summary(limit=limit)
    failures = get_pilot_failures(limit=limit)
    successes = get_pilot_successes(limit=limit)
    runs = get_pilot_runs(limit=limit)
    signoffs = get_pilot_signoffs(limit=limit)
    quality_context = build_quality_context(limit=limit)
    quality_summary = build_quote_pack_quality_report(quality_context.get("quote_pack_payload") or {"artifacts": []})
    qualification_result = qualify_rfq(quality_context.get("rfq_payload")) if quality_context.get("rfq_payload") else {}
    qualification_summary = build_qualification_summary([qualification_result] if qualification_result else [])
    tender_analytics = build_tender_success_analytics(limit=limit)
    readiness_score = calculate_readiness_score()
    success_rate = calculate_success_rate()
    pilot_mode = get_pilot_execution_metadata()
    approval_signoffs = sum(1 for item in signoffs if str(item.get("signoff_type") or "").lower() == "approval")
    review_signoffs = sum(1 for item in signoffs if str(item.get("signoff_type") or "").lower() == "review")
    proof_signoffs = sum(1 for item in signoffs if str(item.get("signoff_type") or "").lower() == "proof")
    explicit_manual_submission_confirmations = sum(1 for item in signoffs if bool(item.get("manual_submission_confirmed")))
    final_submission_attempts = sum(1 for item in runs if bool(item.get("final_submission_attempted")))
    workflow_skips = sum(1 for item in runs if bool(item.get("workflow_skip")))
    governance_gaps = (
        int(metrics.get("workflow_failures", 0))
        + int(metrics.get("persistence_failures", 0))
        + int(metrics.get("blocked_workflows", 0))
        + final_submission_attempts
        + workflow_skips
    )
    governance_compliance_score = max(0.0, 100.0 - float(governance_gaps) * 10.0)
    manual_governance_integrity_score = max(0.0, 100.0 - float(final_submission_attempts + workflow_skips) * 50.0)
    operator_governance_score = 100.0 if signoffs else 50.0
    refusal_handling_score = max(0.0, 100.0 - float(metrics.get("rfqs_refused", 0)) * 5.0)
    recovery_readiness_score = max(0.0, 100.0 - float(metrics.get("persistence_failures", 0)) * 10.0)
    supervised_live_governance_summary = {
        "pilot_mode": pilot_mode.get("pilot_mode", "disabled"),
        "manual_approval_signoffs": approval_signoffs,
        "review_signoffs": review_signoffs,
        "proof_signoffs": proof_signoffs,
        "explicit_manual_submission_confirmations": explicit_manual_submission_confirmations,
        "approval_records": int(workflow_metrics.get("approvals_recorded", 0)),
        "review_records": int(workflow_metrics.get("reviews_recorded", 0)),
        "proof_records": int(workflow_metrics.get("proofs_recorded", 0)),
        "final_submission_attempts": final_submission_attempts,
        "workflow_skips": workflow_skips,
        "governance_advisory_only": True,
        "manual_submission_remains_required": True,
        "manual_only_final_submission": True,
    }
    warnings = []
    if not pilot_mode.get("pilot_enabled"):
        warnings.append("pilot mode is disabled")
    if metrics.get("workflow_failures", 0):
        warnings.append("workflow failures recorded during pilot")
    if metrics.get("persistence_failures", 0):
        warnings.append("persistence failures recorded during pilot")
    if metrics.get("blocked_workflows", 0):
        warnings.append("blocked workflows recorded during pilot")
    report = PilotReadinessReport(
        status="healthy" if pilot_mode.get("pilot_enabled") else "degraded",
        checked_at=utc_now(),
        pilot_mode=pilot_mode,
        pilot_metrics=metrics,
        pilot_summary=summary,
        quality_summary=quality_summary,
        tender_success_analytics=tender_analytics,
        pilot_failures=failures,
        pilot_successes=successes,
        pilot_signoffs=signoffs,
        pilot_readiness_score=readiness_score,
        workflow_correctness_score=round(success_rate * 100, 2),
        persistence_reliability_score=max(0.0, 100.0 - float(metrics.get("persistence_failures", 0)) * 10.0),
        operational_reliability_score=max(0.0, 100.0 - float(metrics.get("workflow_failures", 0)) * 10.0),
        operator_governance_score=operator_governance_score,
        refusal_handling_score=refusal_handling_score,
        recovery_readiness_score=recovery_readiness_score,
        supervised_live_governance_summary=supervised_live_governance_summary,
        governance_compliance_score=governance_compliance_score,
        manual_governance_integrity_score=manual_governance_integrity_score,
        qualification_summary=qualification_summary,
        qualification_result=qualification_result,
        warnings=warnings,
    )
    return report.to_jsonable_dict()


def render_pilot_readiness_text(report: Optional[Dict[str, Any]] = None) -> str:
    report = report or build_pilot_readiness_report()
    return "\n".join(
        [
            f"Pilot readiness score: {report.get('pilot_readiness_score', 0.0)}",
            f"Workflow correctness score: {report.get('workflow_correctness_score', 0.0)}",
            f"Persistence reliability score: {report.get('persistence_reliability_score', 0.0)}",
            f"Operational reliability score: {report.get('operational_reliability_score', 0.0)}",
            f"Operator governance score: {report.get('operator_governance_score', 0.0)}",
            f"Refusal handling score: {report.get('refusal_handling_score', 0.0)}",
            f"Recovery readiness score: {report.get('recovery_readiness_score', 0.0)}",
            f"Qualification GO count: {report.get('qualification_summary', {}).get('recommendation_counts', {}).get('GO', 0)}",
            f"Qualification manual review count: {report.get('qualification_summary', {}).get('recommendation_counts', {}).get('MANUAL_REVIEW', 0)}",
            f"Qualification reject count: {report.get('qualification_summary', {}).get('recommendation_counts', {}).get('REJECT', 0)}",
            f"Qualification recommendation: {report.get('qualification_result', {}).get('recommendation', 'MANUAL_REVIEW')}",
            f"Qualification readiness state: {report.get('qualification_result', {}).get('readiness_state', 'HIGH_RISK')}",
            f"Governance compliance score: {report.get('governance_compliance_score', 0.0)}",
            f"Manual governance integrity score: {report.get('manual_governance_integrity_score', 0.0)}",
            f"Supervised-live governance: advisory only",
            f"Pilot mode: {report.get('pilot_mode', {}).get('pilot_mode', 'disabled')}",
            f"Quote pack readiness: {report.get('quality_summary', {}).get('quality_score', 0.0)}",
            f"Quote conversion rate: {report.get('tender_success_analytics', {}).get('quote_conversion_rate', 0.0)}",
        ]
    )
