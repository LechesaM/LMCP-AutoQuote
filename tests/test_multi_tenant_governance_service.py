from __future__ import annotations

import importlib
import shutil
from pathlib import Path


def _copy_k8s_scaffold(source_root: Path, target_root: Path) -> None:
    shutil.copytree(source_root / "k8s", target_root / "k8s")


def test_multi_tenant_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.multi_tenant_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    service = module.MultiTenantGovernanceService(k8s_root=test_root / "k8s")
    latest = service.latest_multi_tenant_governance()
    history = service.multi_tenant_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["multi_tenant_governance_authority"] == "GO"
    assert latest["unresolved_blockers"] == []
    assert latest["tenant_isolation_readiness"]["ready"] is True
    assert latest["namespace_segregation_readiness"]["ready"] is True
    assert latest["rbac_tenant_boundaries"]["ready"] is True
    assert latest["cross_tenant_leakage_indicators"]["cross_tenant_leakage_safe"] is True
    assert latest["recovery_rationale"]["score_impact"]["final_score"] >= 90.0
    assert history["count"] == 1
    assert history["multi_tenant_governance_history"][0]["recovery_state"] == "recovered"


def test_multi_tenant_governance_service_reports_degraded_and_blocked_paths(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.multi_tenant_governance_service")
    source_root = Path("/Users/cash/Documents")
    degraded_root = tmp_path / "degraded"
    blocked_root = tmp_path / "blocked"
    _copy_k8s_scaffold(source_root, degraded_root)
    _copy_k8s_scaffold(source_root, blocked_root)

    degraded_tenant_network = degraded_root / "k8s" / "base" / "tenant-network-policy-template.yaml"
    degraded_tenant_network.write_text(
        degraded_tenant_network.read_text(encoding="utf-8").replace("placeholder", "segmented"),
        encoding="utf-8",
    )

    blocked_tenant_namespace = blocked_root / "k8s" / "base" / "tenant-namespace-template.yaml"
    blocked_tenant_namespace.write_text(
        blocked_tenant_namespace.read_text(encoding="utf-8")
        .replace("placeholder", "real-tenant")
        .replace("template", "onboarding"),
        encoding="utf-8",
    )
    (blocked_root / "k8s" / "base" / "tenant-rbac-placeholder.yaml").unlink()

    degraded_service = module.MultiTenantGovernanceService(k8s_root=degraded_root / "k8s")
    blocked_service = module.MultiTenantGovernanceService(k8s_root=blocked_root / "k8s")

    degraded_latest = degraded_service.latest_multi_tenant_governance()
    blocked_latest = blocked_service.latest_multi_tenant_governance()

    assert degraded_latest["status"] == "watch"
    assert degraded_latest["recovery_state"] == "degraded-but-recovering"
    assert degraded_latest["unresolved_blockers"] == []
    assert degraded_latest["warnings"]
    assert degraded_latest["multi_tenant_governance_score"] < 90.0

    assert blocked_latest["status"] == "blocked"
    assert blocked_latest["recovery_state"] == "unresolved-blocked"
    assert blocked_latest["multi_tenant_governance_authority"] == "NO_GO"
    assert blocked_latest["unresolved_blockers"]
    assert any("tenant" in blocker.lower() for blocker in blocked_latest["unresolved_blockers"])
    assert blocked_latest["recovery_rationale"]["score_impact"]["final_score"] < 70.0
