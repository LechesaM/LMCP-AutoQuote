from __future__ import annotations

import importlib
import json
from pathlib import Path


class _StubContinuityService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_continuity_governance(self):
        return self._payload


class _StubIncidentService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_incident_governance(self):
        return self._payload


class _StubRemediationService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_runtime_remediation(self):
        return self._payload


class _StubSupervisionService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_supervision_command(self):
        return self._payload


def _write_rollout_bundle(
    root: Path,
    validation_id: str,
    generated_at: str,
    *,
    rollout_recovery_snapshot: dict[str, object],
    continuity_recovery_snapshot: dict[str, object],
    escalation_recovery_snapshot: dict[str, object],
    remediation_recovery_snapshot: dict[str, object],
    warnings: list[str] | None = None,
) -> None:
    bundle_dir = root / validation_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "validation_id": validation_id,
        "generated_at": generated_at,
        "warnings": warnings or [],
        "rollout_recovery_snapshot": rollout_recovery_snapshot,
        "continuity_recovery_snapshot": continuity_recovery_snapshot,
        "escalation_recovery_snapshot": escalation_recovery_snapshot,
        "remediation_recovery_snapshot": remediation_recovery_snapshot,
    }
    (bundle_dir / "production_rollout_validation.json").write_text(json.dumps(payload), encoding="utf-8")


def _ready_snapshots() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    rollout = {
        "queue_partition_readiness": {"queue_partition_ready": True, "partition_count": 4},
        "worker_shard_readiness": {"worker_shard_ready": True, "shard_count": 8},
        "autoscaling_readiness": {"autoscaling_ready": True, "min_replicas": 2, "max_replicas": 8},
        "failover_orchestration_readiness": {"failover_orchestration_ready": True, "active_failover_path": "staging-secondary"},
        "distributed_supervision_coverage": {"distributed_supervision_coverage_ready": True, "coverage_ratio": 1.0},
        "workload_saturation_indicators": {"supervision_saturation_active": False, "workload_pressure": "low"},
        "orchestration_degradation_indicators": {"queue_partition_degradation": False, "worker_shard_degradation": False},
        "unresolved_blockers": [],
        "warnings": [],
        "governance_override_indicators": {"human_supervision_required": True},
    }
    continuity = {
        "continuity_governance_status": "ok",
        "continuity_governance_score": 96.0,
        "continuity_freeze_indicators": [{"freeze_active": False}],
        "operational_continuity_scoring": {"score": 96.0},
        "unresolved_blockers": [],
        "warnings": [],
    }
    escalation = {
        "incident_governance_status": "ok",
        "operational_recovery_coordination": {"recovery_ready": True},
        "freeze_escalation_indicators": {"freeze_active": False},
        "unresolved_blockers": [],
        "warnings": [],
    }
    remediation = {
        "runtime_remediation_status": "ok",
        "runtime_remediation_summary": {"remediation_readiness_status": "PASS", "open_remediation_count": 0},
        "governance_recovery_tracking": {"governance_recovery_ready": True},
        "remediation_escalation_indicators": {},
        "warning_indicators": {},
        "unresolved_remediation_blockers": [],
        "warnings": [],
    }
    supervision = {
        "supervision_coverage": {"distributed_supervision_coverage_ready": True, "coverage_score": 100.0},
        "operational_workload_visibility": {"workload_items": 0, "active_session_count": 1, "assigned_rfq_count": 0, "pending_approval_count": 0, "workload_pressure": "low"},
        "supervision_saturation": {"supervision_saturation_active": False, "queue_backlog_count": 0, "worker_backlog_count": 0},
    }
    return rollout, continuity, escalation, remediation, supervision


def test_distributed_orchestration_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.distributed_orchestration_governance_service")
    validation_root = tmp_path / "runtime" / "staging" / "production-rollout-validations"
    rollout, continuity, escalation, remediation, supervision = _ready_snapshots()
    _write_rollout_bundle(
        validation_root,
        "20260624T110000Z-distributed-orchestration-ready",
        "2026-06-24T11:00:00+00:00",
        rollout_recovery_snapshot=rollout,
        continuity_recovery_snapshot=continuity,
        escalation_recovery_snapshot=escalation,
        remediation_recovery_snapshot=remediation,
    )

    service = module.DistributedOrchestrationGovernanceService(
        validation_root=validation_root,
        continuity_service=_StubContinuityService(continuity),
        incident_service=_StubIncidentService(escalation),
        remediation_service=_StubRemediationService(remediation),
        supervision_command_service=_StubSupervisionService(supervision),
    )

    latest = service.latest_distributed_orchestration()
    history = service.distributed_orchestration_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["distributed_orchestration_authority"] == "GO"
    assert latest["unresolved_blockers"] == []
    assert latest["recovery_state_history"][0]["recovery_state"] == "recovered"
    assert latest["recovery_rationale"]["score_impact"]["final_score"] >= 90.0
    assert latest["blocker_sources"][0]["source"] == "rollout_recovery_snapshot"
    assert history["count"] >= 1
    assert history["distributed_orchestration_history"][0]["recovery_state"] == "recovered"


def test_distributed_orchestration_governance_service_reports_degraded_and_blocked_paths(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.distributed_orchestration_governance_service")
    validation_root = tmp_path / "runtime" / "staging" / "production-rollout-validations"
    rollout_ready, continuity_ready, escalation_ready, remediation_ready, supervision_ready = _ready_snapshots()
    degraded_rollout = dict(rollout_ready)
    degraded_rollout["worker_shard_readiness"] = {"worker_shard_ready": False, "shard_count": 8}
    degraded_rollout["warnings"] = ["worker shard recovery in progress"]
    degraded_rollout["orchestration_degradation_indicators"] = {"worker_shard_degradation": True}

    blocked_rollout = dict(rollout_ready)
    blocked_rollout["unresolved_blockers"] = ["queue partition recovery blocked"]
    blocked_continuity = dict(continuity_ready)
    blocked_continuity["unresolved_blockers"] = ["continuity recovery still frozen"]
    blocked_escalation = dict(escalation_ready)
    blocked_escalation["unresolved_blockers"] = ["escalation recovery review pending"]
    blocked_remediation = dict(remediation_ready)
    blocked_remediation["unresolved_remediation_blockers"] = [{"remediation_id": "remediation-1"}]
    blocked_remediation["runtime_remediation_summary"] = {"remediation_readiness_status": "FAIL", "open_remediation_count": 1}

    _write_rollout_bundle(
        validation_root,
        "20260624T111000Z-distributed-orchestration-degraded",
        "2026-06-24T11:10:00+00:00",
        rollout_recovery_snapshot=degraded_rollout,
        continuity_recovery_snapshot=continuity_ready,
        escalation_recovery_snapshot=escalation_ready,
        remediation_recovery_snapshot=remediation_ready,
    )
    _write_rollout_bundle(
        validation_root,
        "20260624T111500Z-distributed-orchestration-blocked",
        "2026-06-24T11:15:00+00:00",
        rollout_recovery_snapshot=blocked_rollout,
        continuity_recovery_snapshot=blocked_continuity,
        escalation_recovery_snapshot=blocked_escalation,
        remediation_recovery_snapshot=blocked_remediation,
        warnings=["blocked recovery path requires supervision"],
    )

    service = module.DistributedOrchestrationGovernanceService(
        validation_root=validation_root,
        continuity_service=_StubContinuityService(blocked_continuity),
        incident_service=_StubIncidentService(blocked_escalation),
        remediation_service=_StubRemediationService(blocked_remediation),
        supervision_command_service=_StubSupervisionService(supervision_ready),
    )

    latest = service.latest_distributed_orchestration()
    history = service.distributed_orchestration_history(limit=5)

    assert latest["status"] == "blocked"
    assert latest["recovery_state"] == "unresolved-blocked"
    assert latest["distributed_orchestration_authority"] == "NO_GO"
    assert latest["distributed_orchestration_score"] < 70.0
    assert latest["unresolved_blockers"]
    assert any(source["source"] == "rollout_recovery_snapshot" for source in latest["blocker_sources"])
    assert any(source["source"] == "continuity_recovery_snapshot" for source in latest["blocker_sources"])
    assert any(source["source"] == "escalation_recovery_snapshot" for source in latest["blocker_sources"])
    assert any(source["source"] == "remediation_recovery_snapshot" for source in latest["blocker_sources"])
    assert history["count"] == 2
    assert history["distributed_orchestration_history"][0]["recovery_state"] == "unresolved-blocked"
    assert history["distributed_orchestration_history"][1]["recovery_state"] == "degraded-but-recovering"
