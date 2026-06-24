from __future__ import annotations

import importlib


def test_security_hardening_readiness_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.security_hardening_readiness_service")
    service = module.SecurityHardeningReadinessService(runtime_dir=tmp_path / "runtime" / "staging" / "production-hardening-governance")

    latest = service.latest_security_hardening_readiness()
    history = service.security_hardening_readiness_history(limit=5)

    assert latest["security_hardening_readiness"]["ready"] is True
    assert latest["secrets_access_readiness"]["ready"] is True
    assert latest["credential_hygiene_readiness"]["ready"] is True
    assert latest["access_isolation_readiness"]["ready"] is True
    assert latest["network_isolation_readiness"]["ready"] is True
    assert latest["production_mode_enabled"] is False
    assert latest["production_deployment_execution_enabled"] is False
    assert latest["live_credentials_present"] is False
    assert latest["live_external_alerting_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["production_cutover_human_approval_required"] is True
    assert latest["rollback_planning_required"] is True
    assert latest["security_review_required"] is True
    assert history["count"] >= 1

