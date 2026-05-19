from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now
from app.pilot.pilot_metrics import calculate_readiness_score, calculate_success_rate, get_pilot_metrics
from app.pilot.pilot_run_service import get_pilot_failures, get_pilot_summary, get_pilot_successes
from app.pilot.pilot_mode import get_pilot_execution_metadata
from app.pilot.pilot_signoff import get_pilot_signoffs


class PilotReadinessReport(StrictBaseModel):
    status: str = "unknown"
    checked_at: Any = None
    pilot_mode: Dict[str, Any] = Field(default_factory=dict)
    pilot_metrics: Dict[str, Any] = Field(default_factory=dict)
    pilot_summary: Dict[str, Any] = Field(default_factory=dict)
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
    warnings: list[str] = Field(default_factory=list)


def build_pilot_readiness_report(limit: int = 100) -> Dict[str, Any]:
    metrics = get_pilot_metrics()
    summary = get_pilot_summary(limit=limit)
    failures = get_pilot_failures(limit=limit)
    successes = get_pilot_successes(limit=limit)
    signoffs = get_pilot_signoffs(limit=limit)
    readiness_score = calculate_readiness_score()
    success_rate = calculate_success_rate()
    pilot_mode = get_pilot_execution_metadata()
    operator_governance_score = 100.0 if signoffs else 50.0
    refusal_handling_score = max(0.0, 100.0 - float(metrics.get("rfqs_refused", 0)) * 5.0)
    recovery_readiness_score = max(0.0, 100.0 - float(metrics.get("persistence_failures", 0)) * 10.0)
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
            f"Pilot mode: {report.get('pilot_mode', {}).get('pilot_mode', 'disabled')}",
        ]
    )
