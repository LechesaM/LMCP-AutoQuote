from __future__ import annotations

import importlib
import shutil
from pathlib import Path


def _copy_k8s_scaffold(source_root: Path, target_root: Path) -> None:
    shutil.copytree(source_root / "k8s", target_root / "k8s")


def test_ingress_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.ingress_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    service = module.IngressGovernanceService(k8s_root=test_root / "k8s")
    latest = service.latest_ingress_governance()
    history = service.ingress_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["ingress_governance_authority"] == "GO"
    assert latest["unresolved_blockers"] == []
    assert latest["tls_readiness"]["ready"] is True
    assert latest["ingress_isolation_readiness"]["ready"] is True
    assert latest["certificate_governance_readiness"]["ready"] is True
    assert latest["public_attack_surface_indicators"]["attack_surface_safe"] is True
    assert latest["recovery_rationale"]["score_impact"]["final_score"] >= 90.0
    assert history["count"] == 1
    assert history["ingress_governance_history"][0]["recovery_state"] == "recovered"


def test_ingress_governance_service_reports_degraded_and_blocked_paths(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.ingress_governance_service")
    source_root = Path("/Users/cash/Documents")
    degraded_root = tmp_path / "degraded"
    blocked_root = tmp_path / "blocked"
    _copy_k8s_scaffold(source_root, degraded_root)
    _copy_k8s_scaffold(source_root, blocked_root)

    degraded_ingress = degraded_root / "k8s" / "base" / "ingress.yaml"
    degraded_ingress.write_text(
        degraded_ingress.read_text(encoding="utf-8").replace('lmcp.io/observability-access: "internal-only"', 'lmcp.io/observability-access: "segmented"'),
        encoding="utf-8",
    )

    blocked_ingress = blocked_root / "k8s" / "base" / "ingress.yaml"
    blocked_ingress.write_text(
        blocked_ingress.read_text(encoding="utf-8")
        .replace('lmcp.io/public-exposure: "disabled"', 'lmcp.io/public-exposure: "enabled"')
        .replace("placeholder.lmcp.local", "public.example.com"),
        encoding="utf-8",
    )
    (blocked_root / "k8s" / "base" / "tls-secret-placeholder.yaml").unlink()

    degraded_service = module.IngressGovernanceService(k8s_root=degraded_root / "k8s")
    blocked_service = module.IngressGovernanceService(k8s_root=blocked_root / "k8s")

    degraded_latest = degraded_service.latest_ingress_governance()
    blocked_latest = blocked_service.latest_ingress_governance()

    assert degraded_latest["status"] == "watch"
    assert degraded_latest["recovery_state"] == "degraded-but-recovering"
    assert degraded_latest["unresolved_blockers"] == []
    assert degraded_latest["warnings"]
    assert degraded_latest["ingress_governance_score"] < 90.0

    assert blocked_latest["status"] == "blocked"
    assert blocked_latest["recovery_state"] == "unresolved-blocked"
    assert blocked_latest["ingress_governance_authority"] == "NO_GO"
    assert blocked_latest["unresolved_blockers"]
    assert any("public exposure" in blocker.lower() for blocker in blocked_latest["unresolved_blockers"])
    assert blocked_latest["recovery_rationale"]["score_impact"]["final_score"] < 70.0
