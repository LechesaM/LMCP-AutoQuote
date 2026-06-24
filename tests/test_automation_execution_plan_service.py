from __future__ import annotations

import importlib


def test_automation_execution_plan_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.automation_execution_plan_service")
    service = module.AutomationExecutionPlanService(runtime_dir=tmp_path / "runtime" / "staging" / "controlled-automation-governance")

    latest = service.latest_automation_execution_plan()
    history = service.automation_execution_plan_history(limit=5)

    assert latest["automation_execution_plan_score"] >= 0
    assert latest["orchestration_plan_readiness"]["ready"] is True
    assert latest["dry_run_execution_plan_readiness"]["ready"] is True
    assert latest["human_approval_checkpoint_readiness"]["ready"] is True
    assert latest["rollback_planning_readiness"]["ready"] is True
    assert latest["auditability_readiness"]["ready"] is True
    assert latest["final_automation_enabled"] is False
    assert latest["autonomous_procurement_execution_enabled"] is False
    assert latest["autonomous_tender_submission_enabled"] is False
    assert latest["autonomous_supplier_award_enabled"] is False
    assert latest["production_credentials_present"] is False
    assert latest["live_external_alerting_enabled"] is False
    assert latest["procurement_commitment_generation_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert history["count"] >= 1

