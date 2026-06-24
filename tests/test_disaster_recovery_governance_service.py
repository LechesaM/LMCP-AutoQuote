from __future__ import annotations

import importlib
import shutil
from pathlib import Path


class _StubBackupRestoreService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_backup_restore_governance(self):
        return self._payload


class _StubContinuityService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_continuity_governance(self):
        return self._payload


class _StubMultiTenantService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_multi_tenant_governance(self):
        return self._payload


class _StubSupervisionService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_supervision_command(self):
        return self._payload


def _copy_k8s_scaffold(source_root: Path, target_root: Path) -> None:
    shutil.copytree(source_root / "k8s", target_root / "k8s")


def _ready_payloads() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    backup_restore = {
        "status": "ok",
        "backup_restore_governance_status": "ok",
        "backup_restore_governance_authority": "GO",
        "backup_restore_governance_score": 96.0,
        "backup_restore_governance_grade": "ready",
        "recovery_state": "recovered",
        "rpo_visibility": {"ready": True, "rpo_minutes": 60},
        "rto_visibility": {"ready": True, "rto_minutes": 120},
        "latest_backup_restore_governance": {"analysis_id": "backup-restore-governance:latest"},
        "warnings": [],
    }
    continuity = {
        "disaster_recovery_rehearsal_status": [{"status": "PASS"}],
        "recovery_escalation_readiness": [{"status": "PASS"}],
        "recovery_timing_indicators": [{"status": "PASS"}],
    }
    multi_tenant = {
        "tenant_isolation_readiness": {"ready": True},
        "namespace_segregation_readiness": {"ready": True},
        "tenant_workload_separation": {"ready": True},
        "rbac_tenant_boundaries": {"ready": True},
        "storage_isolation_readiness": {"ready": True},
        "ingress_tenancy_segregation": {"ready": True},
        "supervision_tenancy_coverage": {"ready": True},
        "cross_tenant_leakage_indicators": {"cross_tenant_leakage_safe": True},
        "safety_model": {"tenant_onboarding_disabled": True},
    }
    supervision = {
        "supervision_coverage": {"distributed_supervision_coverage_ready": True, "coverage_score": 100.0},
        "operational_workload_visibility": {
            "workload_items": 0,
            "active_session_count": 1,
            "assigned_rfq_count": 0,
            "pending_approval_count": 0,
            "workload_pressure": "low",
        },
        "supervision_saturation": {"supervision_saturation_active": False, "queue_backlog_count": 0, "worker_backlog_count": 0},
    }
    return backup_restore, continuity, multi_tenant, supervision


def test_disaster_recovery_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.disaster_recovery_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    backup_restore, continuity, multi_tenant, supervision = _ready_payloads()
    service = module.DisasterRecoveryGovernanceService(
        k8s_root=test_root / "k8s",
        backup_restore_governance_service=_StubBackupRestoreService(backup_restore),
        continuity_governance_service=_StubContinuityService(continuity),
        multi_tenant_governance_service=_StubMultiTenantService(multi_tenant),
        supervision_command_service=_StubSupervisionService(supervision),
    )

    latest = service.latest_disaster_recovery_governance()
    history = service.disaster_recovery_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["disaster_recovery_governance_authority"] == "GO"
    assert latest["regional_failover_readiness"]["ready"] is True
    assert latest["warm_standby_readiness"]["ready"] is True
    assert latest["cross_region_backup_readiness"]["ready"] is True
    assert latest["dns_failover_placeholder_readiness"]["ready"] is True
    assert latest["dr_runbook_readiness"]["ready"] is True
    assert latest["dr_rehearsal_readiness"]["ready"] is True
    assert latest["rpo_rto_escalation_readiness"]["ready"] is True
    assert latest["tenant_recovery_boundary_readiness"]["ready"] is True
    assert latest["unresolved_blockers"] == []
    assert latest["recovery_state_history"][0]["recovery_state"] == "recovered"
    assert latest["recovery_rationale"]["score_impact"]["final_score"] >= 90.0
    assert history["count"] >= 1
    assert history["disaster_recovery_governance_history"][0]["recovery_state"] == "recovered"


def test_disaster_recovery_governance_service_reports_blocked_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.disaster_recovery_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    (test_root / "k8s" / "base" / "regional-failover-placeholder.yaml").unlink()
    dns_file = test_root / "k8s" / "base" / "dns-failover-placeholder.yaml"
    dns_file.write_text(
        dns_file.read_text(encoding="utf-8") + "\n  dns_api_key: real-dns\n",
        encoding="utf-8",
    )
    production_patch = test_root / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml"
    production_patch.write_text(
        production_patch.read_text(encoding="utf-8").replace('LMCP_ALLOW_FINAL_AUTOMATION: "false"', 'LMCP_ALLOW_FINAL_AUTOMATION: "true"'),
        encoding="utf-8",
    )

    backup_restore, continuity, multi_tenant, supervision = _ready_payloads()
    multi_tenant["cross_tenant_leakage_indicators"] = {"cross_tenant_leakage_safe": False}
    supervision["supervision_saturation"] = {"supervision_saturation_active": True, "queue_backlog_count": 5, "worker_backlog_count": 4}

    service = module.DisasterRecoveryGovernanceService(
        k8s_root=test_root / "k8s",
        backup_restore_governance_service=_StubBackupRestoreService(backup_restore),
        continuity_governance_service=_StubContinuityService(continuity),
        multi_tenant_governance_service=_StubMultiTenantService(multi_tenant),
        supervision_command_service=_StubSupervisionService(supervision),
    )

    latest = service.latest_disaster_recovery_governance()

    assert latest["status"] == "blocked"
    assert latest["recovery_state"] == "unresolved-blocked"
    assert latest["disaster_recovery_governance_authority"] == "NO_GO"
    assert latest["unresolved_blockers"]
    assert any(source["source"] == "regional_failover_placeholder" for source in latest["blocker_sources"])
    assert any(source["source"] == "dns_failover_placeholder" for source in latest["blocker_sources"])
    assert any(source["source"] == "production_safety_controls" for source in latest["blocker_sources"])
