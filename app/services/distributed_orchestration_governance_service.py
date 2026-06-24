from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.production_continuity_governance_service import ProductionContinuityGovernanceService
from app.services.production_incident_governance_service import ProductionIncidentGovernanceService
from app.services.runtime_remediation_governance_service import RuntimeRemediationGovernanceService
from app.services.production_supervision_command_service import ProductionSupervisionCommandService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROLLOUT_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "production-rollout-validations"
LATEST_ROLLOUT_VALIDATION_FILE = ROLLOUT_VALIDATION_ROOT / "latest_production_rollout_validation.json"
RELEASE_CERTIFICATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "release-certifications"
RUNTIME_ENDURANCE_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "runtime-endurance-validations"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _authority_from_status(status: str) -> str:
    normalized = _safe_str(status, "watch").lower()
    if normalized == "ok":
        return "GO"
    if normalized == "watch":
        return "WATCH"
    return "NO_GO"


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "trend": trend,
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified"}
    return bool(value)


def _dedupe(items: List[str]) -> List[str]:
    unique: List[str] = []
    for item in items:
        text = _safe_str(item)
        if text and text not in unique:
            unique.append(text)
    return unique


class DistributedOrchestrationGovernanceService:
    def __init__(
        self,
        validation_root: Optional[Path] = None,
        release_certification_root: Optional[Path] = None,
        runtime_endurance_root: Optional[Path] = None,
        continuity_service: Optional[ProductionContinuityGovernanceService] = None,
        incident_service: Optional[ProductionIncidentGovernanceService] = None,
        remediation_service: Optional[RuntimeRemediationGovernanceService] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
    ) -> None:
        self.validation_root = validation_root or ROLLOUT_VALIDATION_ROOT
        self.release_certification_root = release_certification_root or RELEASE_CERTIFICATION_ROOT
        self.runtime_endurance_root = runtime_endurance_root or RUNTIME_ENDURANCE_VALIDATION_ROOT
        self.continuity_service = continuity_service or ProductionContinuityGovernanceService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.incident_service = incident_service or ProductionIncidentGovernanceService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )
        self.remediation_service = remediation_service or RuntimeRemediationGovernanceService(
            validation_root=self.runtime_endurance_root,
        )
        self.supervision_command_service = supervision_command_service or ProductionSupervisionCommandService(
            validation_root=self.validation_root,
            release_certification_root=self.release_certification_root,
        )

    def _bundle_files(self) -> List[Path]:
        if not self.validation_root.exists():
            return []
        bundles = [
            path / "production_rollout_validation.json"
            for path in self.validation_root.iterdir()
            if path.is_dir() and (path / "production_rollout_validation.json").exists()
        ]
        bundles.sort(
            key=lambda path: (
                _parse_iso((_read_json(path, {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                path.name,
            ),
            reverse=True,
        )
        return bundles

    def _load_rollout_payloads(self, limit: int = 20) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        for bundle_path in self._bundle_files()[: max(1, int(limit))]:
            payload = _read_json(bundle_path, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(bundle_path)
                payloads.append(payload)
        if not payloads and LATEST_ROLLOUT_VALIDATION_FILE.exists():
            payload = _read_json(LATEST_ROLLOUT_VALIDATION_FILE, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(LATEST_ROLLOUT_VALIDATION_FILE)
                payloads.append(payload)
        return payloads

    def _latest_rollout_payload(self) -> Dict[str, Any]:
        payloads = self._load_rollout_payloads(limit=1)
        return payloads[0] if payloads else {}

    @staticmethod
    def _source_snapshot(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
        return _safe_dict(payload.get(key))

    @staticmethod
    def _field_ready(snapshot: Dict[str, Any], key: str, fallback: bool = False) -> bool:
        if key in snapshot:
            return _truthy(snapshot.get(key))
        return fallback

    @staticmethod
    def _missing_snapshot_blocker(source: str) -> str:
        return f"{source.replace('_', ' ')} unavailable"

    def _rollout_blockers(self, snapshot: Dict[str, Any]) -> List[str]:
        if not snapshot:
            return [self._missing_snapshot_blocker("rollout_recovery_snapshot")]
        blockers = _safe_list(snapshot.get("unresolved_blockers")) + _safe_list(snapshot.get("blockers"))
        if not _truthy(_safe_dict(snapshot.get("governance_override_indicators")).get("human_supervision_required", True)):
            blockers.append("human supervision is not explicitly required")
        return _dedupe(blockers)

    def _continuity_blockers(self, snapshot: Dict[str, Any]) -> List[str]:
        if not snapshot:
            return [self._missing_snapshot_blocker("continuity_recovery_snapshot")]
        blockers = _safe_list(snapshot.get("unresolved_blockers")) + _safe_list(snapshot.get("blockers"))
        if any(_truthy(item.get("freeze_active")) for item in _safe_list(snapshot.get("continuity_freeze_indicators"))):
            blockers.append("continuity freeze indicators remain active")
        return _dedupe(blockers)

    def _escalation_blockers(self, rollout_snapshot: Dict[str, Any], incident_snapshot: Dict[str, Any]) -> List[str]:
        escalation_snapshot = _safe_dict(rollout_snapshot.get("escalation_recovery_snapshot"))
        if not escalation_snapshot and not incident_snapshot:
            return [self._missing_snapshot_blocker("escalation_recovery_snapshot")]
        blockers: List[str] = []
        if escalation_snapshot:
            blockers.extend(_safe_list(escalation_snapshot.get("unresolved_blockers")))
            blockers.extend(_safe_list(escalation_snapshot.get("blockers")))
            if not _truthy(escalation_snapshot.get("escalation_chain_ready", False)):
                blockers.append("escalation chain readiness is not confirmed")

        if incident_snapshot:
            blockers.extend(_safe_list(incident_snapshot.get("unresolved_blockers")))
            blockers.extend(_safe_list(incident_snapshot.get("blockers")))

        return _dedupe(blockers)

    def _remediation_blockers(self, snapshot: Dict[str, Any]) -> List[str]:
        if not snapshot:
            return [self._missing_snapshot_blocker("remediation_recovery_snapshot")]
        summary = _safe_dict(snapshot.get("runtime_remediation_summary"))
        governance = _safe_dict(snapshot.get("governance_recovery_tracking"))
        escalation = _safe_dict(snapshot.get("remediation_escalation_indicators"))
        warnings = _safe_dict(snapshot.get("warning_indicators"))
        unresolved = _safe_list(snapshot.get("unresolved_remediation_blockers"))

        blockers: List[str] = []
        blockers.extend(_safe_list(snapshot.get("unresolved_blockers")))
        blockers.extend(unresolved)
        if _safe_int(summary.get("open_remediation_count"), 0) > 0:
            blockers.append("open remediation items remain unresolved")
        if not _truthy(governance.get("governance_recovery_ready")):
            blockers.append("governance recovery tracking is not ready")
        if any(_truthy(value) for value in escalation.values()):
            blockers.append("remediation escalation indicators remain active")
        if any(_truthy(value) for value in warnings.values()):
            blockers.append("remediation warning indicators remain active")
        return _dedupe(blockers)

    def _workload_saturation_indicators(self, supervision_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        workload = _safe_dict(supervision_snapshot.get("operational_workload_visibility"))
        saturation = _safe_dict(supervision_snapshot.get("supervision_saturation"))
        active_sessions = _safe_int(workload.get("active_session_count"), 0)
        assigned_rfq_count = _safe_int(workload.get("assigned_rfq_count"), 0)
        pending_approval_count = _safe_int(workload.get("pending_approval_count"), 0)
        workload_items = _safe_int(workload.get("workload_items"), assigned_rfq_count + pending_approval_count)
        saturation_active = _truthy(saturation.get("supervision_saturation_active")) or active_sessions > 1 or workload_items > 2
        return {
            "supervision_saturation_active": saturation_active,
            "workload_pressure": _safe_str(workload.get("workload_pressure"), "low"),
            "active_session_count": active_sessions,
            "assigned_rfq_count": assigned_rfq_count,
            "pending_approval_count": pending_approval_count,
            "workload_items": workload_items,
            "queue_backlog_count": _safe_int(saturation.get("queue_backlog_count"), 0),
            "worker_backlog_count": _safe_int(saturation.get("worker_backlog_count"), 0),
        }

    def _component_status(self, ready: bool, *, degraded: bool = False) -> Dict[str, Any]:
        score = 100.0 if ready else 0.0
        status = "PASS" if ready else "WARN" if degraded else "FAIL"
        return {"ready": ready, "status": status, "score": score}

    def _history_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rollout_snapshot = self._source_snapshot(payload, "rollout_recovery_snapshot")
        continuity_snapshot = self._source_snapshot(payload, "continuity_recovery_snapshot")
        escalation_snapshot = self._source_snapshot(payload, "escalation_recovery_snapshot")
        remediation_snapshot = self._source_snapshot(payload, "remediation_recovery_snapshot")

        continuity_latest = continuity_snapshot or _safe_dict(self.continuity_service.latest_continuity_governance())
        incident_latest = escalation_snapshot or _safe_dict(self.incident_service.latest_incident_governance())
        remediation_latest = remediation_snapshot or _safe_dict(self.remediation_service.latest_runtime_remediation())
        supervision_latest = _safe_dict(self.supervision_command_service.latest_supervision_command())

        queue_partition_readiness = _safe_dict(rollout_snapshot.get("queue_partition_readiness"))
        worker_shard_readiness = _safe_dict(rollout_snapshot.get("worker_shard_readiness"))
        autoscaling_readiness = _safe_dict(rollout_snapshot.get("autoscaling_readiness"))
        failover_orchestration_readiness = _safe_dict(rollout_snapshot.get("failover_orchestration_readiness"))
        distributed_supervision_coverage = _safe_dict(
            rollout_snapshot.get("distributed_supervision_coverage") or _safe_dict(supervision_latest.get("supervision_coverage"))
        )
        workload_saturation_indicators = self._workload_saturation_indicators(supervision_latest)
        orchestration_degradation_indicators = _safe_dict(rollout_snapshot.get("orchestration_degradation_indicators"))

        rollout_blockers = self._rollout_blockers(rollout_snapshot)
        continuity_blockers = self._continuity_blockers(continuity_latest)
        escalation_blockers = self._escalation_blockers(rollout_snapshot, incident_latest)
        remediation_blockers = self._remediation_blockers(remediation_latest)
        unresolved_blockers = _dedupe(rollout_blockers + continuity_blockers + escalation_blockers + remediation_blockers)

        queue_ready = self._field_ready(queue_partition_readiness, "queue_partition_ready")
        worker_ready = self._field_ready(worker_shard_readiness, "worker_shard_ready")
        autoscaling_ready = self._field_ready(autoscaling_readiness, "autoscaling_ready")
        failover_ready = self._field_ready(failover_orchestration_readiness, "failover_orchestration_ready")
        supervision_ready = self._field_ready(distributed_supervision_coverage, "distributed_supervision_coverage_ready")
        saturation_active = _truthy(workload_saturation_indicators.get("supervision_saturation_active"))
        if not orchestration_degradation_indicators:
            orchestration_degradation_indicators = {
                "queue_partition_degradation": not queue_ready,
                "worker_shard_degradation": not worker_ready,
                "autoscaling_degradation": not autoscaling_ready,
                "failover_orchestration_degradation": not failover_ready,
                "distributed_supervision_degradation": not supervision_ready,
                "saturation_degradation": saturation_active,
            }
        degradation_active = any(_truthy(value) for value in orchestration_degradation_indicators.values())

        warnings = _dedupe(
            _safe_list(payload.get("warnings"))
            + _safe_list(rollout_snapshot.get("warnings"))
            + _safe_list(continuity_latest.get("warnings"))
            + _safe_list(incident_latest.get("warnings"))
            + _safe_list(remediation_latest.get("warnings"))
        )

        component_scores = [
            100.0 if queue_ready else 0.0,
            100.0 if worker_ready else 0.0,
            100.0 if autoscaling_ready else 0.0,
            100.0 if failover_ready else 0.0,
            100.0 if supervision_ready else 0.0,
            100.0 if not saturation_active else 40.0,
            100.0 if not degradation_active else 35.0,
        ]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = (len(unresolved_blockers) * 5.0) + (len(warnings) * 2.0)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))

        if unresolved_blockers:
            recovery_state = "unresolved-blocked"
            distributed_score = min(score_after_deductions, 69.99)
        elif warnings or saturation_active or degradation_active or not all(
            [queue_ready, worker_ready, autoscaling_ready, failover_ready, supervision_ready]
        ):
            recovery_state = "degraded-but-recovering"
            distributed_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            distributed_score = max(score_after_deductions, 90.0)

        distributed_score = round(min(distributed_score, 100.0), 2)
        distributed_status = _status_from_score(distributed_score)
        if recovery_state == "unresolved-blocked":
            distributed_status = "blocked"
        elif recovery_state == "degraded-but-recovering":
            distributed_status = "watch"
        else:
            distributed_status = "ok"
        distributed_authority = _authority_from_status(distributed_status)
        distributed_grade = "ready" if recovery_state == "recovered" else "watch" if recovery_state == "degraded-but-recovering" else "blocked"

        recovery_state_history = [
            {
                "analysis_id": _safe_str(payload.get("validation_id"), "distributed-orchestration"),
                "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
                "recovery_state": recovery_state,
                "distributed_orchestration_score": distributed_score,
                "distributed_orchestration_status": distributed_status,
                "distributed_orchestration_authority": distributed_authority,
                "unresolved_blocker_count": len(unresolved_blockers),
            }
        ]

        blocker_sources = [
            {
                "source": "rollout_recovery_snapshot",
                "ready": not bool(rollout_blockers),
                "blockers": rollout_blockers,
            },
            {
                "source": "continuity_recovery_snapshot",
                "ready": not bool(continuity_blockers),
                "blockers": continuity_blockers,
            },
            {
                "source": "escalation_recovery_snapshot",
                "ready": not bool(escalation_blockers),
                "blockers": escalation_blockers,
            },
            {
                "source": "remediation_recovery_snapshot",
                "ready": not bool(remediation_blockers),
                "blockers": remediation_blockers,
            },
        ]

        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "All distributed orchestration readiness signals are recovered."
                if recovery_state == "recovered"
                else "Recovery is progressing but one or more staging signals remain degraded."
                if recovery_state == "degraded-but-recovering"
                else "One or more recovery blockers remain unresolved."
            ),
            "score_impact": {
                "base_score": round(base_score, 2),
                "deductions": round(deduction, 2),
                "final_score": distributed_score,
            },
            "state_basis": {
                "queue_partition_ready": queue_ready,
                "worker_shard_ready": worker_ready,
                "autoscaling_ready": autoscaling_ready,
                "failover_orchestration_ready": failover_ready,
                "distributed_supervision_coverage_ready": supervision_ready,
                "workload_saturation_active": saturation_active,
                "orchestration_degradation_active": degradation_active,
                "unresolved_blocker_count": len(unresolved_blockers),
            },
        }

        latest_rollout_recovery = {
            "rollout_recovery_snapshot": rollout_snapshot,
            "continuity_recovery_snapshot": continuity_latest,
            "escalation_recovery_snapshot": incident_latest,
            "remediation_recovery_snapshot": remediation_latest,
            "queue_partition_readiness": queue_partition_readiness,
            "worker_shard_readiness": worker_shard_readiness,
            "autoscaling_readiness": autoscaling_readiness,
            "failover_orchestration_readiness": failover_orchestration_readiness,
            "distributed_supervision_coverage": distributed_supervision_coverage,
            "workload_saturation_indicators": workload_saturation_indicators,
            "orchestration_degradation_indicators": orchestration_degradation_indicators,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": unresolved_blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "analysis_id": f"{_safe_str(payload.get('validation_id'), 'distributed-orchestration')}:distributed-orchestration",
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
        }
        latest_rollout_recovery["orchestration_governance_history"] = recovery_state_history
        return {
            "analysis_id": latest_rollout_recovery["analysis_id"],
            "generated_at": latest_rollout_recovery["generated_at"],
            "status": distributed_status,
            "distributed_orchestration_status": distributed_status,
            "distributed_orchestration_authority": distributed_authority,
            "distributed_orchestration_score": distributed_score,
            "distributed_orchestration_grade": distributed_grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": unresolved_blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "queue_partition_readiness": queue_partition_readiness,
            "worker_shard_readiness": worker_shard_readiness,
            "autoscaling_readiness": autoscaling_readiness,
            "failover_orchestration_readiness": failover_orchestration_readiness,
            "distributed_supervision_coverage": distributed_supervision_coverage,
            "workload_saturation_indicators": workload_saturation_indicators,
            "orchestration_degradation_indicators": orchestration_degradation_indicators,
            "orchestration_governance_history": recovery_state_history,
            "latest_rollout_recovery": latest_rollout_recovery,
            "latest_continuity_recovery": continuity_latest,
            "latest_escalation_recovery": incident_latest,
            "latest_remediation_recovery": remediation_latest,
            "summary_counts": {
                "PASS": 1 if recovery_state == "recovered" else 0,
                "WARN": 1 if recovery_state == "degraded-but-recovering" else 0,
                "FAIL": 1 if recovery_state == "unresolved-blocked" else 0,
            },
            "warnings": warnings + unresolved_blockers,
        }

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for payload in self._load_rollout_payloads(limit=limit):
            entry = self._history_entry(payload)
            entries.append(
                {
                    "analysis_id": entry["analysis_id"],
                    "generated_at": entry["generated_at"],
                    "distributed_orchestration_status": entry["distributed_orchestration_status"],
                    "distributed_orchestration_authority": entry["distributed_orchestration_authority"],
                    "distributed_orchestration_score": entry["distributed_orchestration_score"],
                    "distributed_orchestration_grade": entry["distributed_orchestration_grade"],
                    "recovery_state": entry["recovery_state"],
                    "recovery_state_history": entry["recovery_state_history"],
                    "unresolved_blockers": entry["unresolved_blockers"],
                    "recovery_rationale": entry["recovery_rationale"],
                    "blocker_sources": entry["blocker_sources"],
                    "summary_counts": entry["summary_counts"],
                }
            )
        return entries

    def list_distributed_orchestration(self, limit: int = 20) -> Dict[str, Any]:
        history = self._history(limit=limit)
        latest_payload = self._latest_rollout_payload()
        latest = self._history_entry(latest_payload) if latest_payload else self._history_entry({})
        scores = [float(item.get("distributed_orchestration_score", 0.0)) for item in history] or [latest["distributed_orchestration_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["distributed_orchestration_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["status"],
            "distributed_orchestration_status": latest["distributed_orchestration_status"],
            "distributed_orchestration_authority": latest["distributed_orchestration_authority"],
            "distributed_orchestration_score": latest["distributed_orchestration_score"],
            "distributed_orchestration_grade": latest["distributed_orchestration_grade"],
            **latest,
            "latest_distributed_orchestration": latest,
            "distributed_orchestration_history": history[: max(1, int(limit))],
            "distributed_orchestration_history_summary": summary,
            "summary_counts": latest.get("summary_counts", {}),
            "warnings": latest.get("warnings", []),
        }

    def latest_distributed_orchestration(self) -> Dict[str, Any]:
        return self.list_distributed_orchestration(limit=1)

    def distributed_orchestration_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_distributed_orchestration(limit=limit)
        history = latest["distributed_orchestration_history"]
        return {
            "status": latest["status"],
            "distributed_orchestration_status": latest["distributed_orchestration_status"],
            "distributed_orchestration_authority": latest["distributed_orchestration_authority"],
            "distributed_orchestration_score": latest["distributed_orchestration_score"],
            "distributed_orchestration_grade": latest["distributed_orchestration_grade"],
            "count": len(history),
            "distributed_orchestration_history": history,
            "distributed_orchestration_history_summary": latest["distributed_orchestration_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
