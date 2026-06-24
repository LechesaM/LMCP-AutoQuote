from __future__ import annotations

import importlib
import shutil
from pathlib import Path


def _copy_k8s_scaffold(source_root: Path, target_root: Path) -> None:
    shutil.copytree(source_root / "k8s", target_root / "k8s")


class _StubProductionOperationalizationService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_production_governance(self):
        return self._payload


class _StubSupervisionService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_supervision_command(self):
        return self._payload


class _StubMultiTenantService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def latest_multi_tenant_governance(self):
        return self._payload


def _ready_payload() -> dict[str, object]:
    return {
        "production_runtime_segmentation": {
            "tenant_workspace_isolation": {"isolation_verified": True},
        },
        "production_observability_governance": {
            "production_observability_governance_score": 96.0,
            "production_observability_governance_status": "ok",
            "observability_readiness_indicators": {"worker_heartbeat": True, "system_resilience": True},
            "observability_risk_indicators": {"telemetry_degradation": []},
        },
        "high_availability_governance": {"ha_readiness_indicators": {"queue_stable": True}},
        "disaster_recovery_governance": {"recovery_readiness_indicators": {"final_readiness_cleared": True}},
    }


def _supervision_payload() -> dict[str, object]:
    return {
        "supervision_coverage": {"active_supervision_coverage_ready": True, "coverage_score": 95.0},
        "operational_workload_visibility": {"active_session_count": 1, "assigned_rfq_count": 0, "pending_approval_count": 0, "workload_pressure": "low"},
        "supervision_saturation": {"supervision_saturation_active": False, "queue_backlog_count": 0, "worker_backlog_count": 0},
    }


def _multi_tenant_payload() -> dict[str, object]:
    return {
        "cross_tenant_leakage_indicators": {"cross_tenant_leakage_safe": True},
        "tenant_isolation_readiness": {"ready": True},
    }


def test_distributed_observability_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.distributed_observability_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    service = module.DistributedObservabilityGovernanceService(
        k8s_root=test_root / "k8s",
        production_operationalization_service=_StubProductionOperationalizationService(_ready_payload()),
        supervision_command_service=_StubSupervisionService(_supervision_payload()),
        multi_tenant_governance_service=_StubMultiTenantService(_multi_tenant_payload()),
    )
    latest = service.latest_distributed_observability()
    history = service.distributed_observability_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["distributed_observability_authority"] == "GO"
    assert latest["telemetry_aggregation_readiness"]["ready"] is True
    assert latest["distributed_metrics_readiness"]["ready"] is True
    assert latest["centralized_log_governance_readiness"]["ready"] is True
    assert latest["tracing_readiness"]["ready"] is True
    assert latest["alert_governance_readiness"]["ready"] is True
    assert history["count"] == 1
    assert history["distributed_observability_history"][0]["distributed_observability_status"] in {"ok", "watch"}


def test_distributed_observability_governance_service_reports_degraded_and_blocked_paths(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.distributed_observability_governance_service")
    source_root = Path("/Users/cash/Documents")
    degraded_root = tmp_path / "degraded"
    blocked_root = tmp_path / "blocked"
    _copy_k8s_scaffold(source_root, degraded_root)
    _copy_k8s_scaffold(source_root, blocked_root)

    degraded_loki = degraded_root / "k8s" / "base" / "loki-placeholder.yaml"
    degraded_loki.write_text(
        degraded_loki.read_text(encoding="utf-8").replace("placeholder", "segmented"),
        encoding="utf-8",
    )

    blocked_alertmanager = blocked_root / "k8s" / "base" / "alertmanager-placeholder.yaml"
    blocked_alertmanager.write_text(
        blocked_alertmanager.read_text(encoding="utf-8")
        .replace("placeholder", "external")
        + "\nwebhook_configs:\n  - url: https://example.com/alerts\n",
        encoding="utf-8",
    )
    (blocked_root / "k8s" / "base" / "tempo-placeholder.yaml").unlink()

    degraded_service = module.DistributedObservabilityGovernanceService(
        k8s_root=degraded_root / "k8s",
        production_operationalization_service=_StubProductionOperationalizationService(_ready_payload()),
        supervision_command_service=_StubSupervisionService(_supervision_payload()),
        multi_tenant_governance_service=_StubMultiTenantService(_multi_tenant_payload()),
    )
    blocked_service = module.DistributedObservabilityGovernanceService(
        k8s_root=blocked_root / "k8s",
        production_operationalization_service=_StubProductionOperationalizationService(_ready_payload()),
        supervision_command_service=_StubSupervisionService(_supervision_payload()),
        multi_tenant_governance_service=_StubMultiTenantService(_multi_tenant_payload()),
    )

    degraded_latest = degraded_service.latest_distributed_observability()
    blocked_latest = blocked_service.latest_distributed_observability()

    assert degraded_latest["status"] == "watch"
    assert degraded_latest["recovery_state"] == "degraded-but-recovering"
    assert degraded_latest["warnings"]
    assert degraded_latest["unresolved_blockers"] == []

    assert blocked_latest["status"] == "blocked"
    assert blocked_latest["recovery_state"] == "unresolved-blocked"
    assert blocked_latest["distributed_observability_authority"] == "NO_GO"
    assert blocked_latest["unresolved_blockers"]
    assert any("alert" in blocker.lower() for blocker in blocked_latest["unresolved_blockers"])
