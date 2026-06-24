from __future__ import annotations

import importlib
import shutil
from pathlib import Path


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


def _ready_payloads() -> tuple[dict[str, object], dict[str, object]]:
    multi_tenant = {
        "tenant_isolation_readiness": {"ready": True},
        "namespace_segregation_readiness": {"ready": True},
        "tenant_workload_separation": {"ready": True},
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
    return multi_tenant, supervision


def test_backup_restore_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.backup_restore_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    shutil.copytree(source_root / "k8s", test_root / "k8s")
    multi_tenant, supervision = _ready_payloads()

    service = module.BackupRestoreGovernanceService(
        k8s_root=test_root / "k8s",
        multi_tenant_governance_service=_StubMultiTenantService(multi_tenant),
        supervision_command_service=_StubSupervisionService(supervision),
    )

    latest = service.latest_backup_restore_governance()
    history = service.backup_restore_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["backup_restore_governance_authority"] == "GO"
    assert latest["unresolved_blockers"] == []
    assert latest["postgres_backup_readiness"]["ready"] is True
    assert latest["redis_persistence_readiness"]["ready"] is True
    assert latest["restore_rehearsal_readiness"]["ready"] is True
    assert latest["backup_retention_governance"]["ready"] is True
    assert latest["tenant_aware_backup_boundaries"]["ready"] is True
    assert latest["rpo_visibility"]["ready"] is True
    assert latest["rto_visibility"]["ready"] is True
    assert latest["backup_restore_governance_score"] >= 90.0
    assert latest["recovery_state_history"][0]["recovery_state"] == "recovered"
    assert latest["recovery_rationale"]["score_impact"]["final_score"] >= 90.0
    assert any(source["source"] == "postgres_backup_cronjob_placeholder" for source in latest["blocker_sources"])
    assert history["count"] >= 1
    assert history["backup_governance_history"][0]["recovery_state"] == "recovered"


def test_backup_restore_governance_service_reports_blocked_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.backup_restore_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    shutil.copytree(source_root / "k8s", test_root / "k8s")

    backup_secret = test_root / "k8s" / "base" / "backup-storage-secret-placeholder.yaml"
    backup_secret.write_text(
        backup_secret.read_text(encoding="utf-8").replace("placeholder", "real-password"),
        encoding="utf-8",
    )
    restore_job = test_root / "k8s" / "base" / "restore-rehearsal-job-placeholder.yaml"
    restore_job.unlink()

    multi_tenant = {
        "tenant_isolation_readiness": {"ready": False},
        "namespace_segregation_readiness": {"ready": False},
        "tenant_workload_separation": {"ready": False},
        "storage_isolation_readiness": {"ready": False},
        "ingress_tenancy_segregation": {"ready": False},
        "supervision_tenancy_coverage": {"ready": False},
        "cross_tenant_leakage_indicators": {"cross_tenant_leakage_safe": False},
        "safety_model": {"tenant_onboarding_disabled": False},
    }
    supervision = {
        "supervision_coverage": {"distributed_supervision_coverage_ready": False, "coverage_score": 60.0},
        "operational_workload_visibility": {
            "workload_items": 5,
            "active_session_count": 2,
            "assigned_rfq_count": 3,
            "pending_approval_count": 2,
            "workload_pressure": "high",
        },
        "supervision_saturation": {"supervision_saturation_active": True, "queue_backlog_count": 4, "worker_backlog_count": 3},
    }

    service = module.BackupRestoreGovernanceService(
        k8s_root=test_root / "k8s",
        multi_tenant_governance_service=_StubMultiTenantService(multi_tenant),
        supervision_command_service=_StubSupervisionService(supervision),
    )

    latest = service.latest_backup_restore_governance()
    history = service.backup_restore_governance_history(limit=5)

    assert latest["status"] == "blocked"
    assert latest["recovery_state"] == "unresolved-blocked"
    assert latest["backup_restore_governance_authority"] == "NO_GO"
    assert latest["backup_restore_governance_score"] < 70.0
    assert latest["unresolved_blockers"]
    assert any(source["source"] == "backup_storage_secret_placeholder" for source in latest["blocker_sources"])
    assert any(source["source"] == "restore_rehearsal_job_placeholder" for source in latest["blocker_sources"])
    assert any(source["source"] == "tenant_aware_backup_boundaries" for source in latest["blocker_sources"])
    assert history["count"] == 1
    assert history["backup_governance_history"][0]["recovery_state"] == "unresolved-blocked"
