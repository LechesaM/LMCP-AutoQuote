from __future__ import annotations

import importlib
import shutil
from pathlib import Path


def _copy_k8s_scaffold(source_root: Path, target_root: Path) -> None:
    shutil.copytree(source_root / "k8s", target_root / "k8s")


def test_compliance_regulatory_governance_service_reports_recovered_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.compliance_regulatory_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    service = module.ComplianceRegulatoryGovernanceService(k8s_root=test_root / "k8s")
    latest = service.latest_compliance_regulatory_governance()
    history = service.compliance_regulatory_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recovery_state"] == "recovered"
    assert latest["compliance_regulatory_governance_authority"] == "GO"
    assert latest["regulatory_framework_readiness"] is True
    assert latest["procurement_compliance_readiness"] is True
    assert latest["audit_retention_readiness"] is True
    assert latest["governance_evidence_completeness"] is True
    assert latest["policy_exception_escalation_readiness"] is True
    assert latest["compliance_review_supervision"] is True
    assert latest["regulatory_blocker_visibility"] is True
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["autonomous_approvals_enabled"] is False
    assert latest["production_authority_enabled"] is False
    assert latest["live_regulator_integrations_present"] is False
    assert latest["unresolved_blockers"] == []
    assert latest["compliance_regulatory_governance_score"] >= 90.0
    assert latest["recovery_state_history"][0]["recovery_state"] == "recovered"
    assert latest["recovery_rationale"]["score_impact"]["final_score"] >= 90.0
    assert history["count"] >= 1
    assert history["history"][0]["status"] == "ready"


def test_compliance_regulatory_governance_service_reports_blocked_path(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.compliance_regulatory_governance_service")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    _copy_k8s_scaffold(source_root, test_root)

    blocked_framework = test_root / "k8s" / "base" / "compliance-regulatory" / "regulatory-framework-placeholder.yaml"
    blocked_framework.write_text(
        blocked_framework.read_text(encoding="utf-8") + "\nregulator_endpoint: https://example.com/regulator\n",
        encoding="utf-8",
    )
    (test_root / "k8s" / "base" / "compliance-regulatory" / "policy-exception-escalation-placeholder.yaml").unlink()

    service = module.ComplianceRegulatoryGovernanceService(k8s_root=test_root / "k8s")
    latest = service.latest_compliance_regulatory_governance()
    history = service.compliance_regulatory_governance_history(limit=5)

    assert latest["status"] == "blocked"
    assert latest["recovery_state"] == "unresolved-blocked"
    assert latest["compliance_regulatory_governance_authority"] == "NO_GO"
    assert latest["compliance_regulatory_governance_score"] < 90.0
    assert latest["unresolved_blockers"]
    assert any(source["source"] == "regulatory_framework_readiness" for source in latest["blocker_sources"])
    assert any(source["source"] == "policy_exception_escalation_readiness" for source in latest["blocker_sources"])
    assert any(source.get("issue") == "live_or_autonomous_control_detected" for source in latest["blocker_sources"])
    assert history["count"] == len(history["history"])
    assert history["count"] >= 1
    assert history["history"][0]["status"] == "blocked"
