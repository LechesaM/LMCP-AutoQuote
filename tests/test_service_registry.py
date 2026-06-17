from __future__ import annotations

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.core.service_contracts import (
    FailureBlocker,
    OperationResult,
    ServiceResponse,
    ServiceStatus,
    ValidationErrorDetail,
)
from app.core.service_registry import (
    SERVICE_REGISTRY,
    get_legacy_services,
    get_production_services,
    get_service,
    validate_unique_service_names,
)
from app.core.workflow_state_engine import WorkflowStage, assert_can_transition
from app.services import submission_review_service


def test_service_names_are_unique() -> None:
    validate_unique_service_names()
    names = [record.name for record in SERVICE_REGISTRY]
    assert len(names) == len(set(names))


def test_production_and_legacy_classification_is_available() -> None:
    production = get_production_services()
    legacy = get_legacy_services()

    assert production
    assert legacy
    assert all(record.status is ServiceStatus.PRODUCTION for record in production)
    assert all(record.status in {ServiceStatus.LEGACY, ServiceStatus.DEPRECATED} for record in legacy)


def test_production_services_are_accessible() -> None:
    record = get_service("manual_approval_service")
    assert record is not None
    assert record.status is ServiceStatus.PRODUCTION
    assert get_service("app.services.manual_approval_service") is record
    assert get_service("immutable_submission_lock_service") is not None
    assert get_service("controlled_validation_service") is not None


def test_no_duplicate_production_service_identifiers() -> None:
    production_names = [record.name for record in get_production_services()]
    assert len(production_names) == len(set(production_names))


def test_service_contracts_serialize_correctly() -> None:
    result = OperationResult(
        service_name="manual_approval_service",
        status="ok",
        message="approved",
        data={"tender_id": "T-001"},
        blockers=[FailureBlocker(code="none", message="none", field="")],
        errors=[ValidationErrorDetail(field="status", message="ok", value="ok")],
    )
    response = ServiceResponse(
        service_name="manual_approval_service",
        ok=True,
        result=result,
        data={"source": "manual"},
    )

    result_payload = result.to_jsonable_dict()
    response_payload = response.to_jsonable_dict()

    assert result_payload["service_name"] == "manual_approval_service"
    assert response_payload["result"]["data"]["tender_id"] == "T-001"
    assert response_payload["blockers"] == []


def test_workflow_aware_services_reject_invalid_transitions() -> None:
    try:
        assert_can_transition(WorkflowStage.QUOTE_GENERATED, WorkflowStage.REVIEW_READY)
    except ValueError as exc:
        assert "quote_generated -> review_ready" in str(exc)
    else:
        raise AssertionError("Expected workflow transition rejection")


def test_submission_review_service_does_not_bypass_workflow(monkeypatch, tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(submission_review_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(submission_review_service, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(submission_review_service, "SUBMISSION_REVIEW_LOG_FILE", manual_dir / "submission_reviews.jsonl")

    from app.core import workflow_state_engine

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)

    submission_review_service.append_submission_review(
        {
            "tender_id": "T-INVALID",
            "tender_root": str(tmp_path / "tender"),
            "operator_name": "Reviewer",
            "submission_review_ready": True,
            "status": "review_ready",
        }
    )

    current = workflow_state_engine.get_current_state("T-INVALID")
    assert current.stage is WorkflowStage.DISCOVERED
    assert not workflow_state_engine.WORKFLOW_STATE_LOG_FILE.exists()


def test_runtime_config_integration_remains_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(tmp_path / "runtime" / "manual_production"))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()

    config = get_runtime_config()
    assert config.paths.runtime_root == (tmp_path / "runtime").resolve()
    assert config.paths.manual_production_dir == (tmp_path / "runtime" / "manual_production").resolve()
    assert config.final_submission_manual_only is True
