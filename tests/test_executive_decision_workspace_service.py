from __future__ import annotations

import importlib


def test_executive_decision_workspace_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.executive_decision_workspace_service")
    service = module.ExecutiveDecisionWorkspaceService(runtime_dir=tmp_path / "runtime" / "staging" / "executive-governance")

    latest = service.latest_executive_decision_workspace()
    history = service.executive_decision_workspace_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["executive_review_readiness"]["ready"] is True
    assert latest["executive_decision_queue_readiness"]["ready"] is True
    assert latest["strategic_alignment_readiness"]["ready"] is True
    assert latest["financial_exposure_indicators"] is not None
    assert latest["pricing_escalation_indicators"] is not None
    assert latest["supplier_escalation_indicators"] is not None
    assert latest["compliance_escalation_indicators"] is not None
    assert latest["risk_escalation_indicators"] is not None
    assert latest["executive_human_approval_required"] is True
    assert latest["autonomous_executive_approval_enabled"] is False
    assert latest["production_submission_authority_enabled"] is False
    assert latest["procurement_commitment_generation_enabled"] is False
    assert latest["autonomous_tender_authorization_enabled"] is False
    assert history["count"] >= 1
