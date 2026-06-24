from __future__ import annotations

import importlib


def test_automation_readiness_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.automation_readiness_service")
    service = module.AutomationReadinessService(runtime_dir=tmp_path / "runtime" / "staging" / "controlled-automation-governance")

    latest = service.latest_automation_readiness()
    history = service.automation_readiness_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["automation_readiness_score"] >= 0
    assert latest["orchestration_plan_readiness"]["ready"] is True
    assert latest["guardrail_readiness"]["ready"] is True
    assert latest["supervised_step_planning_readiness"]["ready"] is True
    assert latest["dry_run_enforcement_readiness"]["ready"] is True
    assert latest["human_approval_checkpoint_readiness"]["ready"] is True
    assert latest["safety_boundaries"]["lmcp_allow_final_automation"] is False
    assert latest["safety_boundaries"]["no_autonomous_procurement_execution"] is True
    assert latest["safety_boundaries"]["no_autonomous_tender_submission"] is True
    assert latest["safety_boundaries"]["no_autonomous_supplier_award"] is True
    assert latest["safety_boundaries"]["no_live_external_alerting"] is True
    assert latest["safety_boundaries"]["no_production_credentials"] is True
    assert latest["safety_boundaries"]["no_procurement_commitment_generation"] is True
    assert latest["dry_run_enforcement_readiness"]["ready"] is True
    assert history["count"] >= 1
