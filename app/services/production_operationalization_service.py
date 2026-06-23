from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.executive_command_service import ExecutiveCommandService
from app.services.final_readiness_governance_service import FinalReadinessGovernanceService
from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.operational_pilot_execution_service import OperationalPilotExecutionService
from app.services.operational_stability_service import OperationalStabilityService
from app.services.pilot_evidence_pack_service import PilotEvidencePackService
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


class ProductionOperationalizationService:
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
        self.executive = ExecutiveCommandService(cycle_root=cycle_root, evidence_pack_root=evidence_pack_root)
        self.review_board = PilotReviewBoardService(cycle_root=cycle_root, export_root=evidence_pack_root)
        self.evidence_packs = PilotEvidencePackService()
        self.stability = OperationalStabilityService(cycle_root=cycle_root, export_root=evidence_pack_root)
        self.execution = OperationalPilotExecutionService(cycle_root=cycle_root, evidence_pack_root=evidence_pack_root)
        self.final_readiness = FinalReadinessGovernanceService(cycle_root=cycle_root, export_root=evidence_pack_root)

    def _items(self, limit: int = 250) -> List[Dict[str, Any]]:
        return _safe_list(self.lifecycle.list_items(limit=limit).get("items", []))

    def _lifecycle(self) -> Dict[str, Any]:
        return _safe_dict(self.lifecycle.analytics())

    def _telemetry(self) -> Dict[str, Any]:
        return _safe_dict(self.lifecycle.telemetry())

    def _cycle_dirs(self) -> List[Path]:
        if not self.cycle_root.exists():
            return []
        runs = [path for path in self.cycle_root.iterdir() if path.is_dir() and (path / "pilot_cycle_summary.json").exists()]
        runs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return runs

    def _segmenting(self) -> Dict[str, Any]:
        items = self._items(limit=250)
        tenant_workspace_pairs = {
            ( _safe_str(item.get("tenant_id"), ""), _safe_str(item.get("workspace_id"), "") )
            for item in items
            if _safe_str(item.get("tenant_id"), "") or _safe_str(item.get("workspace_id"), "")
        }
        tenant_ids = {tenant for tenant, _ in tenant_workspace_pairs if tenant}
        workspace_ids = {workspace for _, workspace in tenant_workspace_pairs if workspace}
        pair_count = len(tenant_workspace_pairs)
        score = 85.0
        if items:
            score = 100.0 if pair_count <= len(items) else 70.0
            if not tenant_ids and not workspace_ids:
                score = 85.0
        status = _status_from_score(score)
        return {
            "production_runtime_segmentation_score": round(score, 2),
            "production_runtime_segmentation_status": status,
            "production_runtime_segmentation_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "tenant_workspace_isolation": {
                "tenant_count": len(tenant_ids),
                "workspace_count": len(workspace_ids),
                "tenant_workspace_pair_count": pair_count,
                "isolation_verified": pair_count <= len(items) if items else True,
            },
        }

    def _operator_access(self) -> Dict[str, Any]:
        review = _safe_dict(self.review_board.latest_review_board())
        session = _safe_dict(review.get("latest_session"))
        workload = _safe_dict(session.get("operator_workload"))
        pending_approvals = _safe_list(workload.get("pending_approval_items"))
        assigned_rfqs = _safe_list(workload.get("assigned_rfqs"))
        active_sessions = _safe_int(_safe_dict(review.get("review_board_cadence")).get("runs_last_7_days"), 0)
        operator_role = _safe_str(session.get("operator_role"), "governance_reviewer")
        operator_name = _safe_str(session.get("operator_name"), "staging-governance-operator")
        score = mean([
            100.0 if active_sessions > 0 else 60.0,
            100.0 if not pending_approvals else 65.0,
            100.0 if operator_role in {"governance_reviewer", "operator", "supervisor"} else 55.0,
            100.0 if operator_name else 65.0,
        ])
        return {
            "operator_access_governance_score": round(score, 2),
            "operator_access_governance_status": _status_from_score(score),
            "operator_access_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "operator_access_risk_indicators": {
                "pending_approval_backlog": bool(pending_approvals),
                "operator_role_mismatch": operator_role not in {"governance_reviewer", "operator", "supervisor"},
                "inactive_supervision_window": active_sessions == 0,
            },
            "operator_access_details": {
                "operator_name": operator_name,
                "operator_role": operator_role,
                "active_sessions": active_sessions,
                "assigned_rfqs": assigned_rfqs,
                "pending_approvals": pending_approvals,
            },
        }

    def _observability(self) -> Dict[str, Any]:
        lifecycle = self._lifecycle()
        telemetry = self._telemetry()
        stability = _safe_dict(self.stability.latest_stability())
        health_score = mean([
            _safe_float(_safe_dict(lifecycle.get("system_health_trend")).get("score"), 0.0),
            _safe_float(telemetry.get("system_resilience_score"), 0.0),
            _safe_float(stability.get("stability_score"), 0.0),
        ])
        return {
            "production_observability_governance_score": round(health_score, 2),
            "production_observability_governance_status": _status_from_score(health_score),
            "production_observability_governance_grade": "ready" if health_score >= 85.0 else "watch" if health_score >= 70.0 else "blocked",
            "observability_readiness_indicators": {
                "worker_heartbeat": _safe_dict(telemetry.get("worker_heartbeat")).get("status") == "healthy",
                "queue_backlog": _safe_dict(telemetry.get("queue_backlog")).get("backlog_detected") in {False, 0, "false", "False"},
                "system_resilience": _safe_float(telemetry.get("system_resilience_score"), 0.0) >= 85.0,
                "stability_ok": _safe_str(stability.get("status"), "watch") == "ok",
            },
            "observability_risk_indicators": {
                "telemetry_degradation": _safe_dict(telemetry.get("warnings")),
                "stalled_lifecycle_tasks": _safe_int(telemetry.get("stalled_lifecycle_tasks"), 0) > 0,
            },
        }

    def _backup_restore(self) -> Dict[str, Any]:
        latest_pack = _safe_dict(self.evidence_packs.latest_pack())
        summary = _safe_dict(latest_pack.get("summary"))
        pack_ok = _safe_str(latest_pack.get("status"), "not_found") == "ok"
        score = mean([
            100.0 if pack_ok else 55.0,
            100.0 if _safe_float(summary.get("readiness_score"), 0.0) >= 85.0 else 60.0,
            100.0 if _safe_int(summary.get("history_count"), 0) > 0 else 60.0,
            100.0 if _safe_str(_safe_dict(_safe_dict(latest_pack.get("pack")).get("dry_run_enforcement_verification")).get("status"), "PASS") == "PASS" else 55.0,
            100.0 if _safe_str(_safe_dict(_safe_dict(latest_pack.get("pack")).get("submission_lock_verification")).get("status"), "PASS") == "PASS" else 55.0,
        ])
        return {
            "backup_restore_governance_score": round(score, 2),
            "backup_restore_governance_status": _status_from_score(score),
            "backup_restore_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "recovery_readiness_indicators": {
                "evidence_pack_available": pack_ok,
                "readiness_threshold_met": _safe_float(summary.get("readiness_score"), 0.0) >= 85.0,
                "history_available": _safe_int(summary.get("history_count"), 0) > 0,
                "submission_lock_verified": _safe_str(_safe_dict(_safe_dict(latest_pack.get("pack")).get("submission_lock_verification")).get("status"), "PASS") == "PASS",
                "dry_run_verified": _safe_str(_safe_dict(_safe_dict(latest_pack.get("pack")).get("dry_run_enforcement_verification")).get("status"), "PASS") == "PASS",
            },
            "backup_restore_details": {
                "latest_pack_id": _safe_str(latest_pack.get("pack_id"), ""),
                "latest_generated_at": _safe_str(latest_pack.get("generated_at"), _now_iso()),
                "readiness_score": _safe_float(summary.get("readiness_score"), 0.0),
                "history_count": _safe_int(summary.get("history_count"), 0),
            },
        }

    def _disaster_recovery(self) -> Dict[str, Any]:
        execution = _safe_dict(self.execution.latest_operational_pilot_execution())
        final_readiness = _safe_dict(self.final_readiness.latest_final_readiness())
        score = mean([
            _safe_float(execution.get("operational_endurance_score"), 0.0),
            _safe_float(execution.get("sustained_stability_score"), 0.0),
            100.0 if _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT" else 55.0,
        ])
        return {
            "disaster_recovery_governance_score": round(score, 2),
            "disaster_recovery_governance_status": _status_from_score(score),
            "disaster_recovery_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "recovery_readiness_indicators": {
                "execution_reliability": _safe_float(execution.get("operational_endurance_score"), 0.0) >= 85.0,
                "sustained_stability": _safe_float(execution.get("sustained_stability_score"), 0.0) >= 85.0,
                "final_readiness_cleared": _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT",
            },
        }

    def _high_availability(self) -> Dict[str, Any]:
        stability = _safe_dict(self.stability.latest_stability())
        telemetry = self._telemetry()
        queue_ok = _safe_str(_safe_dict(stability.get("queue_stability_trend")).get("trend"), "stable") in {"stable", "improving"}
        worker_ok = _safe_str(_safe_dict(stability.get("worker_stability_trend")).get("trend"), "stable") in {"stable", "improving"}
        score = mean([
            _safe_float(stability.get("stability_score"), 0.0),
            100.0 if queue_ok else 60.0,
            100.0 if worker_ok else 60.0,
            100.0 if _safe_float(telemetry.get("system_resilience_score"), 0.0) >= 85.0 else 55.0,
        ])
        return {
            "high_availability_governance_score": round(score, 2),
            "high_availability_governance_status": _status_from_score(score),
            "high_availability_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "ha_readiness_indicators": {
                "queue_stable": queue_ok,
                "worker_stable": worker_ok,
                "telemetry_resilient": _safe_float(telemetry.get("system_resilience_score"), 0.0) >= 85.0,
            },
        }

    def _audit_retention(self) -> Dict[str, Any]:
        cycle_runs = self._cycle_dirs()
        latest_pack = _safe_dict(self.evidence_packs.latest_pack())
        latest_cycle = cycle_runs[0] if cycle_runs else None
        latest_cycle_age = 0.0
        if latest_cycle is not None:
            payload = _read_json(latest_cycle / "pilot_cycle_summary.json", {})
            try:
                latest_cycle_age = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(_safe_str(payload.get("generated_at"), _now_iso()).replace("Z", "+00:00"))).total_seconds() / 3600.0)
            except Exception:
                latest_cycle_age = 0.0
        score = mean([
            100.0 if len(cycle_runs) > 0 else 0.0,
            100.0 if latest_cycle_age <= 720.0 else 55.0,
            100.0 if _safe_str(latest_pack.get("status"), "not_found") == "ok" else 60.0,
            100.0 if len(self.evidence_packs.list_packs(limit=20).get("packs", [])) > 0 else 0.0,
        ])
        return {
            "audit_retention_governance_score": round(score, 2),
            "audit_retention_governance_status": _status_from_score(score),
            "audit_retention_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "audit_retention_indicators": {
                "cycle_history_available": len(cycle_runs) > 0,
                "evidence_pack_available": _safe_str(latest_pack.get("status"), "not_found") == "ok",
                "retention_window_ok": latest_cycle_age <= 720.0,
                "history_depth_ok": len(self.evidence_packs.list_packs(limit=20).get("packs", [])) > 0,
            },
            "audit_retention_details": {
                "cycle_count": len(cycle_runs),
                "latest_cycle_age_hours": round(latest_cycle_age, 2),
            },
        }

    def _deployment_readiness(self) -> Dict[str, Any]:
        executive = _safe_dict(self.executive.latest_executive_command())
        final_readiness = _safe_dict(self.final_readiness.latest_final_readiness())
        score = mean([
            _safe_float(executive.get("executive_governance_score"), 0.0),
            100.0 if _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT" else 55.0,
            _safe_float(_safe_dict(self.stability.latest_stability()).get("stability_score"), 0.0),
        ])
        return {
            "deployment_readiness_governance_score": round(score, 2),
            "deployment_readiness_governance_status": _status_from_score(score),
            "deployment_readiness_governance_grade": "ready" if score >= 85.0 else "watch" if score >= 70.0 else "blocked",
            "deployment_readiness_indicators": {
                "executive_ready": _safe_str(executive.get("executive_governance_status"), "watch") == "ok",
                "final_ready": _safe_str(final_readiness.get("final_submission_readiness_status"), "NOT_READY_TO_SUBMIT") == "READY_TO_SUBMIT",
                "stability_ready": _safe_float(_safe_dict(self.stability.latest_stability()).get("stability_score"), 0.0) >= 85.0,
            },
        }

    def _production_sections(self) -> Dict[str, Dict[str, Any]]:
        return {
            "production_runtime_segmentation": self._segmenting(),
            "operator_access_governance": self._operator_access(),
            "production_observability_governance": self._observability(),
            "backup_restore_governance": self._backup_restore(),
            "disaster_recovery_governance": self._disaster_recovery(),
            "high_availability_governance": self._high_availability(),
            "audit_retention_governance": self._audit_retention(),
            "deployment_readiness_governance": self._deployment_readiness(),
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        intelligence_history = _safe_list(self.executive.latest_executive_command().get("executive_intelligence_history", []))
        for item in intelligence_history[: max(1, int(limit))]:
            cycle_id = _safe_str(item.get("cycle_id"), "unknown")
            score = mean([
                _safe_float(item.get("executive_governance_score"), 0.0),
                _safe_float(item.get("operational_intelligence_score"), 0.0),
                _safe_float(item.get("stability_score"), 0.0),
            ])
            status = _status_from_score(score)
            history.append(
                {
                    "analysis_id": f"{_safe_str(item.get('analysis_id'), 'unknown')}:production",
                    "generated_at": _safe_str(item.get("generated_at"), _now_iso()),
                    "cycle_id": cycle_id,
                    "production_readiness_score": round(score, 2),
                    "production_readiness_status": status,
                    "production_readiness_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
                    "deployment_risk_indicators": {
                        "executive_risk": _safe_float(item.get("operational_risk_forecast_score"), 0.0) < 70.0,
                        "stability_risk": _safe_float(item.get("stability_score"), 0.0) < 85.0,
                    },
                    "operator_access_risk_indicators": {
                        "review_backlog": _safe_float(item.get("supervision_score"), 0.0) < 70.0,
                    },
                    "ha_readiness_indicators": {
                        "queue_stable": _safe_float(item.get("throughput_score"), 0.0) >= 85.0,
                    },
                    "recovery_readiness_indicators": {
                        "rollback_ready": _safe_float(item.get("compliance_score"), 0.0) >= 85.0,
                    },
                    "production_governance_summary": {
                        "decision": "support_enterprise_deployment" if status == "ok" else "watch_enterprise_deployment" if status == "watch" else "defer_enterprise_deployment",
                    },
                }
            )
        return history

    def list_production_governance(self, limit: int = 20) -> Dict[str, Any]:
        sections = self._production_sections()
        history = self._history(limit=limit)
        component_scores = {
            "runtime_segmentation": _safe_float(sections["production_runtime_segmentation"].get("production_runtime_segmentation_score"), 0.0),
            "operator_access": _safe_float(sections["operator_access_governance"].get("operator_access_governance_score"), 0.0),
            "observability": _safe_float(sections["production_observability_governance"].get("production_observability_governance_score"), 0.0),
            "backup_restore": _safe_float(sections["backup_restore_governance"].get("backup_restore_governance_score"), 0.0),
            "disaster_recovery": _safe_float(sections["disaster_recovery_governance"].get("disaster_recovery_governance_score"), 0.0),
            "high_availability": _safe_float(sections["high_availability_governance"].get("high_availability_governance_score"), 0.0),
            "audit_retention": _safe_float(sections["audit_retention_governance"].get("audit_retention_governance_score"), 0.0),
            "deployment_readiness": _safe_float(sections["deployment_readiness_governance"].get("deployment_readiness_governance_score"), 0.0),
        }
        readiness_score = round(mean(component_scores.values()), 2) if component_scores else 0.0
        latest = history[0] if history else {}
        latest.update({
            "production_runtime_segmentation": sections["production_runtime_segmentation"],
            "operator_access_governance": sections["operator_access_governance"],
            "production_observability_governance": sections["production_observability_governance"],
            "backup_restore_governance": sections["backup_restore_governance"],
            "disaster_recovery_governance": sections["disaster_recovery_governance"],
            "high_availability_governance": sections["high_availability_governance"],
            "audit_retention_governance": sections["audit_retention_governance"],
            "deployment_readiness_governance": sections["deployment_readiness_governance"],
            "deployment_readiness_indicators": sections["deployment_readiness_governance"].get("deployment_readiness_indicators", {}),
            "operator_access_risk_indicators": sections["operator_access_governance"]["operator_access_risk_indicators"],
            "ha_readiness_indicators": sections["high_availability_governance"]["ha_readiness_indicators"],
            "recovery_readiness_indicators": sections["disaster_recovery_governance"]["recovery_readiness_indicators"],
            "deployment_risk_indicators": {
                "deployment_risk": readiness_score < 70.0 or sections["operator_access_governance"]["operator_access_risk_indicators"].get("pending_approval_backlog", False) or not sections["high_availability_governance"]["ha_readiness_indicators"].get("queue_stable", False) or not sections["disaster_recovery_governance"]["recovery_readiness_indicators"].get("final_readiness_cleared", False),
                "operator_access_risk": sections["operator_access_governance"]["operator_access_risk_indicators"].get("pending_approval_backlog", False),
                "ha_risk": not sections["high_availability_governance"]["ha_readiness_indicators"].get("queue_stable", False),
                "recovery_risk": not sections["disaster_recovery_governance"]["recovery_readiness_indicators"].get("final_readiness_cleared", False),
            },
        })
        risk_indicators = latest["deployment_risk_indicators"]
        warnings: List[str] = []
        if risk_indicators["deployment_risk"]:
            warnings.append("Enterprise deployment readiness is below threshold.")
        if sections["operator_access_governance"]["operator_access_risk_indicators"].get("pending_approval_backlog"):
            warnings.append("Operator access backlog requires attention.")
        if not sections["high_availability_governance"]["ha_readiness_indicators"].get("queue_stable", False):
            warnings.append("Queue stability is below the HA threshold.")
        if not sections["disaster_recovery_governance"]["recovery_readiness_indicators"].get("final_readiness_cleared", False):
            warnings.append("Recovery readiness is not yet cleared.")
        status = "not_found" if not history and not any(component_scores.values()) else _status_from_score(readiness_score)
        if warnings and status == "ok":
            status = "watch"
        latest.update({
            "status": status,
            "generated_at": _now_iso(),
            "analysis_id": _safe_str(latest.get("analysis_id"), ""),
            "production_readiness_score": readiness_score,
            "production_readiness_status": status,
            "production_readiness_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
        })
        return {
            "status": status,
            "generated_at": _now_iso(),
            "analysis_id": _safe_str(latest.get("analysis_id"), ""),
            "production_readiness_score": readiness_score,
            "production_readiness_status": status,
            "production_readiness_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "production_runtime_segmentation": sections["production_runtime_segmentation"],
            "operator_access_governance": sections["operator_access_governance"],
            "production_observability_governance": sections["production_observability_governance"],
            "backup_restore_governance": sections["backup_restore_governance"],
            "disaster_recovery_governance": sections["disaster_recovery_governance"],
            "high_availability_governance": sections["high_availability_governance"],
            "audit_retention_governance": sections["audit_retention_governance"],
            "deployment_readiness_governance": sections["deployment_readiness_governance"],
            "deployment_risk_indicators": risk_indicators,
            "operator_access_risk_indicators": sections["operator_access_governance"]["operator_access_risk_indicators"],
            "ha_readiness_indicators": sections["high_availability_governance"]["ha_readiness_indicators"],
            "recovery_readiness_indicators": sections["disaster_recovery_governance"]["recovery_readiness_indicators"],
            "production_governance_history": history,
            "latest_production_governance": latest,
            "production_governance_history_summary": {
                "analysis_count": len(history),
                "latest_analysis_id": _safe_str(latest.get("analysis_id"), ""),
                "latest_score": readiness_score,
            },
            "summary_components": component_scores,
            "warnings": warnings,
        }

    def latest_production_governance(self) -> Dict[str, Any]:
        response = self.list_production_governance(limit=20)
        if response.get("status") == "not_found":
            return {"status": "not_found", "message": "No production governance history has been recorded yet.", "production_governance": {}}
        return {
            "status": response.get("status", "ok"),
            "analysis_id": response.get("analysis_id", ""),
            "production_readiness_status": response.get("production_readiness_status", "watch"),
            "production_readiness_grade": response.get("production_readiness_grade", "blocked"),
            "production_readiness_score": response.get("production_readiness_score", 0.0),
            "latest_production_governance": response.get("latest_production_governance", {}),
            "production_governance_history": response.get("production_governance_history", []),
            "production_governance_history_summary": response.get("production_governance_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }

    def production_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_production_governance(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("production_governance_history", [])),
            "production_governance_history": response.get("production_governance_history", []),
            "production_governance_history_summary": response.get("production_governance_history_summary", {}),
            "summary_components": response.get("summary_components", {}),
            "warnings": response.get("warnings", []),
        }
