from __future__ import annotations

import importlib


def test_automation_guardrail_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.automation_guardrail_service")
    service = module.AutomationGuardrailService(runtime_dir=tmp_path / "runtime" / "staging" / "controlled-automation-governance")

    latest = service.latest_automation_guardrail()
    history = service.automation_guardrail_history(limit=5)

    assert latest["automation_guardrail_score"] >= 0
    assert latest["guardrail_readiness"]["ready"] is True
    assert latest["supervised_step_planning_readiness"]["ready"] is True
    assert latest["final_automation_enabled"] is False
    assert latest["autonomous_procurement_execution_enabled"] is False
    assert latest["autonomous_tender_submission_enabled"] is False
    assert latest["autonomous_supplier_award_enabled"] is False
    assert latest["production_credentials_present"] is False
    assert latest["live_external_alerting_enabled"] is False
    assert latest["procurement_commitment_generation_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["human_approval_checkpoints_required"] is True
    assert latest["auditability_required"] is True
    assert latest["rollback_planning_required"] is True
    assert history["count"] >= 1

