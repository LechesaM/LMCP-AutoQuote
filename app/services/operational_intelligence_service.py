from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.final_readiness_governance_service import FinalReadinessGovernanceService
from app.services.operational_pilot_execution_service import OperationalPilotExecutionService
from app.services.operational_stability_service import OperationalStabilityService
from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_operations_summary_service import PilotOperationsSummaryService
from app.services.pilot_review_board_service import PilotReviewBoardService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
EVIDENCE_PACK_ROOT = PROJECT_ROOT / "runtime" / "staging" / "evidence-packs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (numerator / denominator) * 100.0)), 2)


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _status_to_score(status: Any) -> float:
    normalized = _safe_str(status, "WARN").lower()
    return {
        "pass": 100.0,
        "ok": 100.0,
        "warn": 65.0,
        "watch": 65.0,
        "fail": 0.0,
        "blocked": 0.0,
        "not_found": 0.0,
    }.get(normalized, 40.0)


class OperationalIntelligenceService:
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

    def _modality_utilization(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        counts = {"portal": 0, "email": 0, "physical": 0, "unsupported": 0}
        for item in items:
            method = _safe_str(item.get("submission_method") or item.get("submission_channel"), "").lower()
            if "portal" in method:
                counts["portal"] += 1
            elif "email" in method:
                counts["email"] += 1
            elif "physical" in method or "courier" in method or "manual" in method:
                counts["physical"] += 1
            else:
                counts["unsupported"] += 1
        total = max(1, sum(counts.values()))
        utilization = {key: _safe_ratio(value, total) for key, value in counts.items()}
        dominant = max(counts.items(), key=lambda entry: entry[1])[0] if counts else "unsupported"
        return {
            "counts": counts,
            "utilization": utilization,
            "dominant_modality": dominant,
            "supported_modalities": [key for key, value in counts.items() if value > 0 and key != "unsupported"],
            "unsupported_count": counts["unsupported"],
        }

    def _rfq_trend_analysis(self, lifecycle: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
        stage_counts: Dict[str, int] = {}
        submission_status_counts: Dict[str, int] = {}
        for item in items:
            stage = _safe_str(item.get("current_state") or item.get("lifecycle_stage"), "unknown")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            submission_status = _safe_str(item.get("submission_status"), "unknown")
            submission_status_counts[submission_status] = submission_status_counts.get(submission_status, 0) + 1
        total = _safe_int(lifecycle.get("total_rfqs"), len(items))
        queue_trend = _safe_dict(lifecycle.get("queue_trend"))
        rfq_score = mean(
            [
                100.0 if total > 0 else 0.0,
                100.0 if _safe_str(queue_trend.get("trend"), "stable") in {"stable", "improving"} else 55.0,
                100.0 if stage_counts.get("SUBMITTED", 0) or stage_counts.get("SUBMISSION_READY", 0) else 65.0,
                100.0 if submission_status_counts.get("unknown", 0) == 0 else 60.0,
            ]
        )
        return {
            "total_rfqs": total,
            "stage_counts": stage_counts,
            "submission_status_counts": submission_status_counts,
            "queue_trend": queue_trend,
            "rfq_trend_score": round(rfq_score, 2),
            "rfq_trend_status": _status_from_score(rfq_score),
        }

    def _bottleneck_analysis(self, lifecycle: Dict[str, Any]) -> Dict[str, Any]:
        slowest_stages = _safe_list(lifecycle.get("slowest_stages"))
        queue_wait_times = _safe_dict(lifecycle.get("queue_wait_times"))
        queue_drain_rate = _safe_dict(lifecycle.get("queue_drain_rate"))
        waits = [_safe_float(value, 0.0) for value in queue_wait_times.values()]
        mean_wait = round(mean(waits), 2) if waits else 0.0
        bottleneck_score = mean(
            [
                100.0 if mean_wait <= 30.0 else 55.0,
                100.0 if _safe_float(queue_drain_rate.get("overall"), 0.0) >= 1.0 else 60.0,
                100.0 if len(slowest_stages) <= 3 else 65.0,
            ]
        )
        return {
            "queue_wait_times": queue_wait_times,
            "queue_drain_rate": queue_drain_rate,
            "slowest_stages": slowest_stages,
            "mean_queue_wait_minutes": mean_wait,
            "bottleneck_score": round(bottleneck_score, 2),
            "bottleneck_status": _status_from_score(bottleneck_score),
        }

    def _compliance_drift(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        readiness_scores = [_safe_float(item.get("validation_readiness"), 0.0) for item in items if item.get("validation_readiness") is not None]
        ready_count = sum(1 for item in items if _safe_str(item.get("validation_readiness_state"), "").lower() in {"ready", "pass"})
        warn_count = sum(1 for item in items if _safe_str(item.get("validation_readiness_state"), "").lower() in {"watch", "warn"})
        fail_count = sum(1 for item in items if _safe_str(item.get("validation_readiness_state"), "").lower() in {"fail", "blocked"})
        avg_readiness = round(mean(readiness_scores), 2) if readiness_scores else 0.0
        compliance_score = mean(
            [
                100.0 if avg_readiness >= 85.0 else 60.0,
                100.0 if fail_count == 0 else 50.0,
                100.0 if ready_count >= warn_count else 65.0,
            ]
        )
        return {
            "average_validation_readiness": avg_readiness,
            "validation_state_counts": {"ready": ready_count, "warn": warn_count, "fail": fail_count},
            "compliance_drift_score": round(compliance_score, 2),
            "compliance_drift_status": _status_from_score(compliance_score),
        }

    def _governance_anomalies(self, lifecycle: Dict[str, Any], telemetry: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
        failure_histogram: Dict[str, int] = {}
        blocker_histogram: Dict[str, int] = {}
        for item in items:
            failure = _safe_str(item.get("failure_classification") or item.get("failure_reason"), "unknown")
            blocker = _safe_str(item.get("primary_blocker"), "unknown")
            failure_histogram[failure] = failure_histogram.get(failure, 0) + 1
            blocker_histogram[blocker] = blocker_histogram.get(blocker, 0) + 1
        worker_crashes = _safe_int(lifecycle.get("worker_crash_count"), 0) + _safe_int(telemetry.get("worker_crash_count"), 0)
        stalled_tasks = _safe_int(telemetry.get("stalled_lifecycle_tasks"), 0)
        anomaly_score = mean(
            [
                100.0 if worker_crashes == 0 else 60.0,
                100.0 if stalled_tasks == 0 else 55.0,
                100.0 if len([count for count in failure_histogram.values() if count > 0]) <= 5 else 65.0,
            ]
        )
        severity = "low" if anomaly_score >= 85.0 else "medium" if anomaly_score >= 70.0 else "high"
        return {
            "failure_histogram": failure_histogram,
            "blocker_histogram": blocker_histogram,
            "worker_crash_count": worker_crashes,
            "stalled_task_count": stalled_tasks,
            "governance_anomaly_score": round(anomaly_score, 2),
            "governance_anomaly_status": _status_from_score(anomaly_score),
            "anomaly_severity": severity,
            "anomaly_severity_indicators": {
                "worker_crash_indicator": worker_crashes > 0,
                "stalled_task_indicator": stalled_tasks > 0,
                "failure_concentration_indicator": len(failure_histogram) <= 2 and sum(failure_histogram.values()) > 0,
            },
        }

    def _supervision_load(self) -> Dict[str, Any]:
        review_board = _safe_dict(self.review_board.latest_review_board())
        operations = _safe_dict(self.operations_summary.latest_operations_summary())
        final_readiness = _safe_dict(self.final_readiness.latest_final_readiness())
        latest_session = _safe_dict(review_board.get("latest_session"))
        outstanding_actions = _safe_list(review_board.get("outstanding_governance_actions"))
        unresolved_exceptions = _safe_list(review_board.get("unresolved_operational_exceptions"))
        pending_approvals = _safe_list(_safe_dict(latest_session.get("operator_workload")).get("pending_approval_items"))
        assigned_rfqs = _safe_list(_safe_dict(latest_session.get("operator_workload")).get("assigned_rfqs"))
        active_sessions = _safe_int(review_board.get("review_board_cadence", {}).get("runs_last_7_days"), 0)
        load_score = mean(
            [
                100.0 if active_sessions > 0 else 60.0,
                100.0 if not outstanding_actions else 60.0,
                100.0 if not unresolved_exceptions else 60.0,
                100.0 if not pending_approvals else 65.0,
                100.0 if _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT" else 65.0,
                100.0 if _safe_str(operations.get("operations_summary_status"), "watch") == "ok" else 65.0,
            ]
        )
        saturation = {
            "supervision_load_score": round(load_score, 2),
            "supervision_load_status": _status_from_score(load_score),
            "supervision_saturation_indicator": _safe_str(latest_session.get("operator_role"), "governance_reviewer"),
            "supervision_saturation_warning": bool(pending_approvals) or bool(outstanding_actions) or bool(unresolved_exceptions),
        }
        return {
            "active_operator_sessions": active_sessions,
            "supervised_rfqs": assigned_rfqs,
            "pending_approvals": pending_approvals,
            "outstanding_governance_actions": outstanding_actions,
            "unresolved_operational_exceptions": unresolved_exceptions,
            "supervision_load": saturation,
            "supervision_load_history": review_board.get("governance_review_history", []),
        }

    def _recurring_blockers(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        blocker_histogram: Dict[str, int] = {}
        retry_histogram: Dict[str, int] = {}
        for item in items:
            blockers = _safe_list(item.get("validation_reason_codes")) or _safe_list(item.get("blocker_summary"))
            for blocker in blockers:
                key = _safe_str(blocker, "unknown")
                blocker_histogram[key] = blocker_histogram.get(key, 0) + 1
            retry = _safe_str(item.get("failure_classification") or item.get("failure_reason"), "unknown")
            retry_histogram[retry] = retry_histogram.get(retry, 0) + 1
        blocker_score = mean(
            [
                100.0 if len(blocker_histogram) <= 5 else 65.0,
                100.0 if len([count for count in retry_histogram.values() if count > 1]) <= 3 else 60.0,
            ]
        )
        return {
            "recurring_blocker_histogram": blocker_histogram,
            "retry_reason_histogram": retry_histogram,
            "recurring_blocker_score": round(blocker_score, 2),
            "recurring_blocker_status": _status_from_score(blocker_score),
        }

    def _throughput_analysis(self, lifecycle: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_rfqs = _safe_int(lifecycle.get("total_rfqs"), len(items))
        queue_drain_rate = _safe_float(_safe_dict(lifecycle.get("queue_drain_rate")).get("overall"), 0.0)
        duration_values = [_safe_float(item.get("rfq_lifecycle_duration"), 0.0) for item in items if item.get("rfq_lifecycle_duration") is not None]
        avg_duration = round(mean(duration_values), 2) if duration_values else 0.0
        throughput_score = mean(
            [
                100.0 if total_rfqs > 0 else 0.0,
                100.0 if queue_drain_rate >= 1.0 else 60.0,
                100.0 if avg_duration > 0 and avg_duration <= 72.0 else 65.0,
            ]
        )
        return {
            "total_rfqs": total_rfqs,
            "queue_drain_rate": queue_drain_rate,
            "average_lifecycle_duration_hours": avg_duration,
            "operational_throughput_score": round(throughput_score, 2),
            "operational_throughput_status": _status_from_score(throughput_score),
        }

    def _cycle_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        cycles = self.execution._cycles()[: max(1, int(limit))]
        for path in cycles:
            payload = _safe_dict(_read_json(path / "pilot_cycle_summary.json", {}))
            if not payload:
                continue
            pack_id = _safe_str(_safe_dict(payload.get("evidence_pack")).get("pack_id"), "")
            pack = _safe_dict(_read_json(self.evidence_pack_root / pack_id / "pilot_evidence_pack.json", {})) if pack_id else {}
            history.append(
                {
                    "analysis_id": f"{_safe_str(payload.get('cycle_id'), 'unknown')}:intelligence",
                    "cycle_id": _safe_str(payload.get("cycle_id"), "unknown"),
                    "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                    "rfq_trend_score": 0.0,
                    "submission_modality_utilization_score": 0.0,
                    "operational_bottleneck_score": 0.0,
                    "compliance_drift_score": 0.0,
                    "governance_anomaly_score": 0.0,
                    "supervision_load_score": 0.0,
                    "recurring_blocker_score": 0.0,
                    "operational_throughput_score": 0.0,
                    "operational_intelligence_score": 0.0,
                    "operational_intelligence_status": "watch",
                    "operational_intelligence_grade": "watch",
                    "evidence_pack_id": _safe_str(pack.get("pack_id"), pack_id),
                    "warning_indicators": {},
                    "warnings": [],
                }
            )
        return history

    def list_operational_intelligence(self, limit: int = 20) -> Dict[str, Any]:
        lifecycle = self._lifecycle()
        telemetry = self._telemetry()
        items = self._items(limit=250)
        rfq_trend = self._rfq_trend_analysis(lifecycle, items)
        modality = self._modality_utilization(items)
        bottleneck = self._bottleneck_analysis(lifecycle)
        compliance = self._compliance_drift(items)
        anomalies = self._governance_anomalies(lifecycle, telemetry, items)
        supervision = self._supervision_load()
        blockers = self._recurring_blockers(items)
        throughput = self._throughput_analysis(lifecycle, items)
        stability = _safe_dict(self.stability.latest_stability())
        operations_summary = _safe_dict(self.operations_summary.latest_operations_summary())
        review_board = _safe_dict(self.review_board.latest_review_board())
        final_readiness = _safe_dict(self.final_readiness.latest_final_readiness())
        execution = _safe_dict(self.execution.latest_operational_pilot_execution())

        component_scores = {
            "rfq_trend": rfq_trend["rfq_trend_score"],
            "modality": mean([100.0 if modality["unsupported_count"] == 0 else 65.0, 100.0 if modality["dominant_modality"] != "unsupported" else 60.0]),
            "bottleneck": bottleneck["bottleneck_score"],
            "compliance": compliance["compliance_drift_score"],
            "anomaly": anomalies["governance_anomaly_score"],
            "supervision": supervision["supervision_load"]["supervision_load_score"],
            "blocker": blockers["recurring_blocker_score"],
            "throughput": throughput["operational_throughput_score"],
            "stability": _safe_float(stability.get("stability_score"), 0.0),
            "execution": _safe_float(execution.get("sustained_stability_score"), 0.0),
        }
        intelligence_score = round(mean(component_scores.values()), 2) if component_scores else 0.0
        intelligence_status = _status_from_score(intelligence_score)
        governance_degradation_indicators = {
            "rfq_trend_warning": rfq_trend["rfq_trend_status"] != "ok",
            "modality_warning": modality["unsupported_count"] > 0,
            "bottleneck_warning": bottleneck["bottleneck_status"] != "ok",
            "compliance_warning": compliance["compliance_drift_status"] != "ok",
            "anomaly_warning": anomalies["governance_anomaly_status"] != "ok",
            "supervision_warning": supervision["supervision_load"]["supervision_load_status"] != "ok",
            "blocker_warning": blockers["recurring_blocker_status"] != "ok",
            "throughput_warning": throughput["operational_throughput_status"] != "ok",
            "stability_warning": _safe_str(stability.get("status"), "watch") != "ok",
            "execution_warning": _safe_str(execution.get("operational_pilot_execution_status"), "watch") != "ok",
            "final_readiness_warning": _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") != "READY_TO_SUBMIT",
        }
        severity_indicators = {
            "high": anomalies["anomaly_severity"] == "high",
            "medium": anomalies["anomaly_severity"] == "medium",
            "low": anomalies["anomaly_severity"] == "low",
        }
        supervision_saturation_indicators = {
            "saturation_warning": supervision["supervision_load"]["supervision_saturation_warning"],
            "pending_approvals": len(supervision["pending_approvals"]),
            "open_actions": len(supervision["outstanding_governance_actions"]),
        }
        optimization_indicators = {
            "queue_optimization_possible": bottleneck["bottleneck_score"] < 85.0,
            "modality_optimization_possible": modality["unsupported_count"] > 0,
            "throughput_optimization_possible": throughput["operational_throughput_score"] < 85.0,
            "compliance_optimization_possible": compliance["compliance_drift_score"] < 85.0,
        }
        warnings = [
            warning
            for warning in [
                "rfq_trend_warning" if governance_degradation_indicators["rfq_trend_warning"] else "",
                "modality_warning" if governance_degradation_indicators["modality_warning"] else "",
                "bottleneck_warning" if governance_degradation_indicators["bottleneck_warning"] else "",
                "compliance_warning" if governance_degradation_indicators["compliance_warning"] else "",
                "anomaly_warning" if governance_degradation_indicators["anomaly_warning"] else "",
                "supervision_warning" if governance_degradation_indicators["supervision_warning"] else "",
                "blocker_warning" if governance_degradation_indicators["blocker_warning"] else "",
                "throughput_warning" if governance_degradation_indicators["throughput_warning"] else "",
                "final_readiness_warning" if governance_degradation_indicators["final_readiness_warning"] else "",
            ]
            if warning
        ]
        status = "not_found" if not items else ("ok" if not warnings and intelligence_score >= 85.0 else "watch" if intelligence_score >= 70.0 else "blocked")
        history = self._cycle_history(limit=limit)
        latest = history[0] if history else {}
        latest.update(
            {
                "analysis_id": f"lifecycle:intelligence:{_safe_str(lifecycle.get('generated_at'), _now_iso())}",
                "generated_at": _now_iso(),
                "rfq_trend_analysis": rfq_trend,
                "submission_modality_utilization_analysis": modality,
                "operational_bottleneck_analysis": bottleneck,
                "compliance_drift_analysis": compliance,
                "governance_anomaly_analysis": anomalies,
                "supervision_load_analysis": supervision,
                "recurring_blocker_analysis": blockers,
                "operational_throughput_analysis": throughput,
                "operational_intelligence_score": intelligence_score,
                "operational_intelligence_status": status,
                "operational_intelligence_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
                "operational_intelligence_decision": "support_supervised_pilot" if status == "ok" else "watch_supervised_pilot" if status == "watch" else "defer_supervised_pilot",
                "governance_degradation_indicators": governance_degradation_indicators,
                "anomaly_severity_indicators": severity_indicators,
                "supervision_saturation_indicators": supervision_saturation_indicators,
                "operational_optimization_indicators": optimization_indicators,
                "operational_intelligence_history_entry": {
                    "analysis_id": f"lifecycle:intelligence:{_safe_str(lifecycle.get('generated_at'), _now_iso())}",
                    "generated_at": _now_iso(),
                    "status": status,
                    "operational_intelligence_score": intelligence_score,
                    "rfq_trend_score": rfq_trend["rfq_trend_score"],
                    "modality_score": component_scores["modality"],
                    "bottleneck_score": bottleneck["bottleneck_score"],
                    "compliance_score": compliance["compliance_drift_score"],
                    "anomaly_score": anomalies["governance_anomaly_score"],
                    "supervision_score": supervision["supervision_load"]["supervision_load_score"],
                    "blocker_score": blockers["recurring_blocker_score"],
                    "throughput_score": throughput["operational_throughput_score"],
                    "stability_score": _safe_float(stability.get("stability_score"), 0.0),
                    "execution_score": _safe_float(execution.get("sustained_stability_score"), 0.0),
                    "final_readiness_status": _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT"),
                    "warnings": warnings,
                },
            }
        )

        return {
            "status": status,
            "generated_at": _now_iso(),
            "operational_intelligence_status": status,
            "operational_intelligence_grade": latest.get("operational_intelligence_grade", "blocked"),
            "operational_intelligence_score": intelligence_score,
            "rfq_trend_analysis": rfq_trend,
            "submission_modality_utilization_analysis": modality,
            "operational_bottleneck_analysis": bottleneck,
            "compliance_drift_analysis": compliance,
            "governance_anomaly_analysis": anomalies,
            "supervision_load_analysis": supervision,
            "recurring_blocker_analysis": blockers,
            "operational_throughput_analysis": throughput,
            "governance_degradation_indicators": governance_degradation_indicators,
            "anomaly_severity_indicators": severity_indicators,
            "supervision_saturation_indicators": supervision_saturation_indicators,
            "operational_optimization_indicators": optimization_indicators,
            "operational_intelligence_history": history,
            "latest_operational_intelligence": latest,
            "operational_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": _safe_str(latest.get("analysis_id"), ""),
                "latest_score": intelligence_score,
                "latest_status": status,
            },
            "summary_components": component_scores,
            "warnings": warnings,
        }

    def latest_operational_intelligence(self) -> Dict[str, Any]:
        response = self.list_operational_intelligence(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No operational intelligence history has been recorded yet.",
                "operational_intelligence": {},
            }
        return {
            "status": response.get("status", "ok"),
            "operational_intelligence_status": response.get("operational_intelligence_status", "watch"),
            "operational_intelligence_grade": response.get("operational_intelligence_grade", "blocked"),
            "operational_intelligence_score": response.get("operational_intelligence_score", 0.0),
            "latest_operational_intelligence": response.get("latest_operational_intelligence", {}),
            "operational_intelligence_history": response.get("operational_intelligence_history", []),
            "operational_intelligence_history_summary": response.get("operational_intelligence_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }

    def operational_intelligence_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_operational_intelligence(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("operational_intelligence_history", [])),
            "operational_intelligence_history": response.get("operational_intelligence_history", []),
            "operational_intelligence_history_summary": response.get("operational_intelligence_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }
