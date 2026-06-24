from app.services.data_residency_governance_service import (
    data_residency_governance_service,
)


def test_latest_data_residency_snapshot_is_ready() -> None:
    snapshot = data_residency_governance_service.latest()

    assert snapshot["ready"] is True
    assert snapshot["environment"] == "staging"
    assert snapshot["governance_mode"] == "read_only"


def test_data_residency_readiness_signals_are_present() -> None:
    snapshot = data_residency_governance_service.latest()

    assert snapshot["tenant_data_residency_ready"] is True
    assert snapshot["jurisdiction_boundary_ready"] is True
    assert snapshot["cross_region_movement_restricted"] is True
    assert snapshot["backup_residency_aligned"] is True
    assert snapshot["audit_log_residency_aligned"] is True
    assert snapshot["evidence_storage_residency_aligned"] is True
    assert snapshot["sovereignty_escalation_ready"] is True
    assert snapshot["restricted_region_blockers_clear"] is True


def test_data_residency_safety_boundaries_are_enforced() -> None:
    snapshot = data_residency_governance_service.latest()

    assert snapshot["dry_run_enforced"] is True
    assert snapshot["human_supervision_required"] is True
    assert snapshot["live_cloud_credentials_present"] is False
    assert snapshot["production_data_movement_enabled"] is False
    assert snapshot["autonomous_remediation_enabled"] is False


def test_data_residency_has_no_unresolved_blockers() -> None:
    snapshot = data_residency_governance_service.latest()

    assert snapshot["unresolved_blockers"] == []


def test_data_residency_history_is_available() -> None:
    history = data_residency_governance_service.history()

    assert history["environment"] == "staging"
    assert history["governance_mode"] == "read_only"
    assert len(history["history"]) >= 1
