from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.final_readiness_governance_service import FinalReadinessGovernanceService
from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.operational_intelligence_service import OperationalIntelligenceService
from app.services.operational_pilot_execution_service import OperationalPilotExecutionService
from app.services.operational_stability_service import OperationalStabilityService
from app.services.pilot_operations_summary_service import PilotOperationsSummaryService
from app.services.pilot_review_board_service import PilotReviewBoardService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
EVIDENCE_PACK_ROOT = PROJECT_ROOT / "runtime" / "staging" / "evidence-packs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _score_from_status(status: Any) -> float:
    normalized = _safe_str(status, "watch").lower()
    return {
        "ok": 100.0,
        "pass": 100.0,
        "ready": 100.0,
        "watch": 65.0,
        "warn": 65.0,
        "blocked": 0.0,
        "fail": 0.0,
        "not_ready_to_submit": 0.0,
        "ready_to_submit": 100.0,
        "no_go": 0.0,
    }.get(normalized, 50.0)


def _trend_from_delta(delta: float) -> str:
    if delta > 2.0:
        return "improving"
    if delta < -2.0:
        return "declining"
    return "stable"


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    return {
        "trend": _trend_from_delta(delta),
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


class ExecutiveCommandService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        evidence_pack_root: Optional[Path] = None,
    ) -> None:
        cycle_root = cycle_root or PILOT_CYCLE_ROOT
        evidence_pack_root = evidence_pack_root or EVIDENCE_PACK_ROOT
        self.cycle_root = cycle_root
        self.evidence_pack_root = evidence_pack_root
        self.lifecycle = RfqLifecycleService()
        self.intelligence = OperationalIntelligenceService(cycle_root=cycle_root, evidence_pack_root=evidence_pack_root)
        self.review_board = PilotReviewBoardService(cycle_root=cycle_root, export_root=evidence_pack_root)
        self.operations_summary = PilotOperationsSummaryService(cycle_root=cycle_root, export_root=evidence_pack_root)
        self.stability = OperationalStabilityService(cycle_root=cycle_root, export_root=evidence_pack_root)
        self.execution = OperationalPilotExecutionService(cycle_root=cycle_root, evidence_pack_root=evidence_pack_root)
        self.final_readiness = FinalReadinessGovernanceService(cycle_root=cycle_root, export_root=evidence_pack_root)

    def _lifecycle(self) -> Dict[str, Any]:
        return _safe_dict(self.lifecycle.analytics())

    def _telemetry(self) -> Dict[str, Any]:
        return _safe_dict(self.lifecycle.telemetry())

    def _items(self, limit: int = 250) -> List[Dict[str, Any]]:
        return _safe_list(self.lifecycle.list_items(limit=limit).get("items", []))

    def _intelligence(self) -> Dict[str, Any]:
        return _safe_dict(self.intelligence.latest_operational_intelligence())

    def _forecast_components(self) -> Dict[str, float]:
        intelligence = self._intelligence()
        lifecycle = self._lifecycle()
        telemetry = self._telemetry()
        review_board = _safe_dict(self.review_board.latest_review_board())
        operations = _safe_dict(self.operations_summary.latest_operations_summary())
        stability = _safe_dict(self.stability.latest_stability())
        final_readiness = _safe_dict(self.final_readiness.latest_final_readiness())
        execution = _safe_dict(self.execution.latest_operational_pilot_execution())

        queue_drain_rate = _safe_float(_safe_dict(lifecycle.get("queue_drain_rate")).get("overall"), 0.0)
        total_rfqs = _safe_int(lifecycle.get("total_rfqs"), 0)
        active_sessions = _safe_int(review_board.get("review_board_cadence", {}).get("runs_last_7_days"), 0)
        pending_approvals = len(_safe_list(_safe_dict(review_board.get("latest_session")).get("operator_workload", {}).get("pending_approval_items")))
        outstanding_actions = len(_safe_list(review_board.get("outstanding_governance_actions")))
        unresolved_exceptions = len(_safe_list(review_board.get("unresolved_operational_exceptions")))
        worker_crashes = _safe_int(lifecycle.get("worker_crash_count"), 0) + _safe_int(telemetry.get("worker_crash_count"), 0)
        stalled_tasks = _safe_int(telemetry.get("stalled_lifecycle_tasks"), 0)

        rfq_trend_score = _safe_float(intelligence.get("operational_intelligence_score"), 0.0)
        throughput_forecast_score = mean(
            [
                100.0 if total_rfqs > 0 else 0.0,
                100.0 if queue_drain_rate >= 1.0 else 60.0,
                100.0 if _safe_str(lifecycle.get("queue_trend", {}).get("trend"), "stable") in {"stable", "improving"} else 55.0,
            ]
        )
        operational_risk_forecast_score = mean(
            [
                100.0 if worker_crashes == 0 else 60.0,
                100.0 if stalled_tasks == 0 else 55.0,
                100.0 if unresolved_exceptions == 0 else 60.0,
                100.0 if _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT" else 55.0,
            ]
        )
        governance_degradation_forecast_score = mean(
            [
                100.0 if not _safe_dict(intelligence.get("governance_degradation_indicators")) else 60.0,
                100.0 if not outstanding_actions else 55.0,
                100.0 if _safe_str(_safe_dict(stability).get("status"), "watch") == "ok" else 65.0,
            ]
        )
        supervision_capacity_forecast_score = mean(
            [
                100.0 if active_sessions > 0 else 60.0,
                100.0 if pending_approvals == 0 else 60.0,
                100.0 if outstanding_actions == 0 else 60.0,
                100.0 if unresolved_exceptions == 0 else 60.0,
                100.0 if _safe_str(_safe_dict(execution).get("operational_pilot_execution_status"), "watch") == "ok" else 65.0,
            ]
        )
        strategic_readiness_score = mean(
            [
                rfq_trend_score,
                throughput_forecast_score,
                operational_risk_forecast_score,
                governance_degradation_forecast_score,
                supervision_capacity_forecast_score,
                _safe_float(_safe_dict(operations).get("summary_components", {}).get("readiness"), 0.0),
                _safe_float(_safe_dict(intelligence).get("operational_intelligence_score"), 0.0),
            ]
        )

        return {
            "procurement_throughput_forecast_score": round(throughput_forecast_score, 2),
            "operational_risk_forecast_score": round(operational_risk_forecast_score, 2),
            "governance_degradation_forecast_score": round(governance_degradation_forecast_score, 2),
            "supervision_capacity_forecast_score": round(supervision_capacity_forecast_score, 2),
            "procurement_health_score": round(strategic_readiness_score, 2),
            "procurement_trend_forecast_score": round(rfq_trend_score, 2),
            "escalation_forecast_score": round(mean([operational_risk_forecast_score, governance_degradation_forecast_score, supervision_capacity_forecast_score]), 2),
        }

    def _forecast_analysis(self) -> Dict[str, Any]:
        intelligence = self._intelligence()
        lifecycle = self._lifecycle()
        telemetry = self._telemetry()
        review_board = _safe_dict(self.review_board.latest_review_board())
        operations = _safe_dict(self.operations_summary.latest_operations_summary())
        stability = _safe_dict(self.stability.latest_stability())
        final_readiness = _safe_dict(self.final_readiness.latest_final_readiness())
        execution = _safe_dict(self.execution.latest_operational_pilot_execution())

        forecast_components = self._forecast_components()
        risk_indicators = {
            "high_risk": forecast_components["operational_risk_forecast_score"] < 70.0,
            "governance_degradation": forecast_components["governance_degradation_forecast_score"] < 70.0,
            "supervision_saturation": forecast_components["supervision_capacity_forecast_score"] < 70.0,
            "final_readiness_blocked": _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") != "READY_TO_SUBMIT",
        }
        saturation_indicators = {
            "queue_pressure": _safe_float(_safe_dict(lifecycle.get("queue_drain_rate")).get("overall"), 0.0) < 1.0,
            "worker_pressure": _safe_int(lifecycle.get("worker_crash_count"), 0) + _safe_int(telemetry.get("worker_crash_count"), 0) > 0,
            "review_backlog": len(_safe_list(review_board.get("outstanding_governance_actions"))) > 0,
        }
        readiness_indicators = {
            "ready_for_controlled_pilot": _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT",
            "intelligence_ready": _safe_str(intelligence.get("operational_intelligence_status"), "watch") == "ok",
            "stability_ready": _safe_str(stability.get("status"), "watch") == "ok",
            "execution_ready": _safe_str(execution.get("operational_pilot_execution_status"), "watch") == "ok",
        }
        operational_indicators = {
            "rfq_trend": _safe_dict(intelligence.get("rfq_trend_analysis")),
            "modality_utilization": _safe_dict(intelligence.get("submission_modality_utilization_analysis")),
            "governance_health": _safe_dict(intelligence.get("governance_degradation_indicators")),
            "throughput": _safe_dict(intelligence.get("operational_throughput_analysis")),
            "queue_trend": _safe_dict(lifecycle.get("queue_trend")),
            "cadence": _safe_dict(review_board.get("review_board_cadence")),
            "stability": _safe_dict(stability),
        }
        warnings = _safe_list(intelligence.get("warnings")) + _safe_list(operations.get("warnings")) + _safe_list(stability.get("warnings"))
        if risk_indicators["high_risk"]:
            warnings.append("Executive procurement risk forecast is elevated.")
        if saturation_indicators["queue_pressure"]:
            warnings.append("Queue pressure remains above the safe threshold.")
        if saturation_indicators["review_backlog"]:
            warnings.append("Governance review backlog requires attention.")
        if not readiness_indicators["ready_for_controlled_pilot"]:
            warnings.append("Final readiness is not yet cleared for controlled pilot operations.")

        score_components = self._forecast_components()
        executive_score = round(mean(score_components.values()), 2) if score_components else 0.0
        status = "ok" if executive_score >= 85.0 and not warnings else "watch" if executive_score >= 70.0 else "blocked"
        if not _safe_list(self._items(limit=5)):
            status = "not_found"

        return {
            "analysis_id": f"executive-command:{_safe_str(lifecycle.get('generated_at'), _now_iso())}",
            "generated_at": _now_iso(),
            "executive_governance_score": executive_score,
            "executive_governance_status": status,
            "executive_governance_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "executive_governance_decision": "support_supervised_pilot" if status == "ok" else "watch_supervised_pilot" if status == "watch" else "defer_supervised_pilot",
            "procurement_throughput_forecast": {
                "score": score_components["procurement_throughput_forecast_score"],
                "trend": _trend_from_delta(score_components["procurement_throughput_forecast_score"] - 70.0),
            },
            "operational_risk_forecast": {
                "score": score_components["operational_risk_forecast_score"],
                "trend": _trend_from_delta(score_components["operational_risk_forecast_score"] - 70.0),
            },
            "governance_degradation_forecast": {
                "score": score_components["governance_degradation_forecast_score"],
                "trend": _trend_from_delta(score_components["governance_degradation_forecast_score"] - 70.0),
            },
            "supervision_capacity_forecast": {
                "score": score_components["supervision_capacity_forecast_score"],
                "trend": _trend_from_delta(score_components["supervision_capacity_forecast_score"] - 70.0),
            },
            "procurement_trend_forecast": {
                "score": score_components["procurement_trend_forecast_score"],
                "trend": _safe_str(_safe_dict(intelligence.get("rfq_trend_analysis")).get("queue_trend", {}).get("trend"), "stable"),
            },
            "escalation_forecast": {
                "score": score_components["escalation_forecast_score"],
                "trend": _trend_from_delta(score_components["escalation_forecast_score"] - 70.0),
            },
            "procurement_health_score": score_components["procurement_health_score"],
            "institutional_risk_indicators": risk_indicators,
            "procurement_saturation_indicators": saturation_indicators,
            "strategic_readiness_indicators": readiness_indicators,
            "operational_forecasting_indicators": operational_indicators,
            "warnings": warnings,
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        intelligence_history = _safe_list(self.intelligence.latest_operational_intelligence().get("operational_intelligence_history", []))
        history: List[Dict[str, Any]] = []
        for item in intelligence_history[: max(1, int(limit))]:
            intelligence_score = _safe_float(item.get("operational_intelligence_score"), 0.0)
            executive_score = round(mean([intelligence_score, _safe_float(item.get("stability_score"), intelligence_score), _safe_float(item.get("execution_score"), intelligence_score)]), 2)
            status = _status_from_score(executive_score)
            warnings = _safe_list(item.get("warnings"))
            if executive_score < 85.0 and "executive_forecast_watch" not in warnings:
                warnings = warnings + ["executive_forecast_watch"]
            history.append(
                {
                    "analysis_id": f"{_safe_str(item.get('analysis_id'), 'unknown')}:executive",
                    "generated_at": _safe_str(item.get("generated_at"), _now_iso()),
                    "cycle_id": _safe_str(item.get("cycle_id"), "unknown"),
                    "operational_intelligence_score": intelligence_score,
                    "executive_governance_score": executive_score,
                    "executive_governance_status": status,
                    "executive_governance_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
                    "procurement_throughput_forecast_score": _safe_float(item.get("throughput_score"), intelligence_score),
                    "operational_risk_forecast_score": _safe_float(item.get("anomaly_score"), intelligence_score),
                    "governance_degradation_forecast_score": _safe_float(item.get("compliance_score"), intelligence_score),
                    "supervision_capacity_forecast_score": _safe_float(item.get("supervision_score"), intelligence_score),
                    "procurement_health_score": executive_score,
                    "strategic_readiness_indicators": {"ready_for_controlled_pilot": status == "ok"},
                    "institutional_risk_indicators": {"high_risk": status == "blocked"},
                    "procurement_saturation_indicators": {"supervision_saturation": executive_score < 70.0},
                    "operational_forecasting_indicators": {
                        "trend": _safe_str(item.get("rfq_trend_score"), "watch"),
                        "decision": _safe_str(item.get("operational_intelligence_decision"), "defer_supervised_pilot"),
                    },
                    "warnings": warnings,
                }
            )
        return history

    def list_executive_command(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        latest = history[0] if history else {}
        forecast = self._forecast_analysis()
        latest.update(forecast)
        status = forecast.get("executive_governance_status", "not_found")
        if status == "not_found":
            warnings = _safe_list(forecast.get("warnings"))
        else:
            warnings = _safe_list(forecast.get("warnings"))
        history_scores = [ _safe_float(item.get("executive_governance_score"), 0.0) for item in history ]
        return {
            "status": status,
            "generated_at": _now_iso(),
            "executive_governance_status": status,
            "executive_governance_grade": latest.get("executive_governance_grade", "blocked"),
            "executive_governance_score": forecast.get("executive_governance_score", 0.0),
            "procurement_throughput_forecast": forecast.get("procurement_throughput_forecast", {}),
            "operational_risk_forecast": forecast.get("operational_risk_forecast", {}),
            "governance_degradation_forecast": forecast.get("governance_degradation_forecast", {}),
            "supervision_capacity_forecast": forecast.get("supervision_capacity_forecast", {}),
            "procurement_trend_forecast": forecast.get("procurement_trend_forecast", {}),
            "escalation_forecast": forecast.get("escalation_forecast", {}),
            "procurement_health_score": forecast.get("procurement_health_score", 0.0),
            "institutional_risk_indicators": forecast.get("institutional_risk_indicators", {}),
            "procurement_saturation_indicators": forecast.get("procurement_saturation_indicators", {}),
            "strategic_readiness_indicators": forecast.get("strategic_readiness_indicators", {}),
            "operational_forecasting_indicators": forecast.get("operational_forecasting_indicators", {}),
            "executive_intelligence_history": history,
            "latest_executive_intelligence": latest,
            "executive_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": _safe_str(latest.get("analysis_id"), ""),
                "latest_score": forecast.get("executive_governance_score", 0.0),
                "score_history": _history_points(history_scores[: max(1, len(history_scores))]) if history_scores else _history_points([]),
            },
            "summary_components": {
                "procurement_throughput_forecast": forecast.get("procurement_throughput_forecast", {}).get("score", 0.0),
                "operational_risk_forecast": forecast.get("operational_risk_forecast", {}).get("score", 0.0),
                "governance_degradation_forecast": forecast.get("governance_degradation_forecast", {}).get("score", 0.0),
                "supervision_capacity_forecast": forecast.get("supervision_capacity_forecast", {}).get("score", 0.0),
                "procurement_trend_forecast": forecast.get("procurement_trend_forecast", {}).get("score", 0.0),
                "escalation_forecast": forecast.get("escalation_forecast", {}).get("score", 0.0),
            },
            "warnings": warnings,
        }

    def latest_executive_command(self) -> Dict[str, Any]:
        response = self.list_executive_command(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No executive procurement command history has been recorded yet.",
                "executive_command": {},
            }
        return {
            "status": response.get("status", "ok"),
            "executive_governance_status": response.get("executive_governance_status", "watch"),
            "executive_governance_grade": response.get("executive_governance_grade", "blocked"),
            "executive_governance_score": response.get("executive_governance_score", 0.0),
            "latest_executive_intelligence": response.get("latest_executive_intelligence", {}),
            "executive_intelligence_history": response.get("executive_intelligence_history", []),
            "executive_intelligence_history_summary": response.get("executive_intelligence_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }

    def executive_command_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_executive_command(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("executive_intelligence_history", [])),
            "executive_intelligence_history": response.get("executive_intelligence_history", []),
            "executive_intelligence_history_summary": response.get("executive_intelligence_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }
