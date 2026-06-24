from __future__ import annotations

import importlib


def test_production_hardening_readiness_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.production_hardening_readiness_service")
    service = module.ProductionHardeningReadinessService(runtime_dir=tmp_path / "runtime" / "staging" / "production-hardening-governance")

    latest = service.latest_production_hardening_readiness()
    history = service.production_hardening_readiness_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["production_cutover_readiness"]["ready"] is True
    assert latest["operational_runbook_readiness"]["ready"] is True
    assert latest["security_hardening_readiness"]["ready"] is True
    assert latest["release_rollback_readiness"]["ready"] is True
    assert latest["observability_readiness"]["ready"] is True
    assert latest["incident_response_readiness"]["ready"] is True
    assert latest["dr_failover_readiness"]["ready"] is True
    assert latest["secrets_access_readiness"]["ready"] is True
    assert latest["cicd_promotion_readiness"]["ready"] is True
    assert latest["production_mode_enabled"] is False
    assert latest["production_deployment_execution_enabled"] is False
    assert latest["live_credentials_present"] is False
    assert latest["live_external_alerting_enabled"] is False
    assert latest["autonomous_procurement_execution_enabled"] is False
    assert latest["autonomous_tender_submission_enabled"] is False
    assert latest["autonomous_supplier_award_enabled"] is False
    assert latest["procurement_commitment_generation_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["production_cutover_human_approval_required"] is True
    assert latest["rollback_planning_required"] is True
    assert latest["security_review_required"] is True
    assert latest["production_blocker_indicators"] is not None
    assert latest["unresolved_production_hardening_blockers"] is not None
    assert history["count"] >= 1
