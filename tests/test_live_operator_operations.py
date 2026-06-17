from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DIR", "/Users/cash/Documents/runtime/manual_production")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DB_PATH", "/Users/cash/Documents/runtime/manual_production/lmcp_operations.db")

from app.api import operator_ops_contracts as contracts
from app.api import operator_ops_routes
from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.main import app
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import assign_operator, mark_reviewed, request_clarification
from app.operator_ops.operator_assignment_service import get_operator_assignments, recommend_operator_assignments
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.operator_ops.operator_notifications import get_operator_notifications
from app.operator_ops.operator_activity_feed import get_operator_timeline
from app.operator_ops.supervised_live_rollout_profile import get_supervised_live_rollout_profile
from app.persistence.repositories import WorkflowRepository
from app.services import audit_trail_service
from app.qualification.opportunity_viability import assess_opportunity_viability


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    audit_dir = runtime_dir / "audit_trail"
    manual_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    monkeypatch.setattr(workflow_state_engine, "_emit_audit_event", lambda **_: None)

    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", audit_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", audit_dir / "audit_events.json")


def _seed_workflow_state() -> None:
    workflow_state_engine.record_transition("T-OPS-LIVE-1", WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "op", "discover")
    workflow_state_engine.record_transition("T-OPS-LIVE-1", WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "op", "evaluate")
    workflow_state_engine.record_transition("T-OPS-LIVE-1", WorkflowStage.EVALUATED, WorkflowStage.PRICED, "op", "price")


def _operator_paths() -> set[str]:
    return {route.path for route in app.routes if route.path.startswith("/operator/")}


def test_operator_routes_exist_and_do_not_expose_autonomy() -> None:
    paths = _operator_paths()
    expected = {
        "/operator/actions",
        "/operator/assignments",
        "/operator/timeline",
        "/operator/notifications",
        "/operator/capacity",
        "/operator/action/assign",
        "/operator/action/reviewed",
        "/operator/action/escalate",
        "/operator/action/archive",
        "/operator/action/request-clarification",
        "/operator/action/acknowledge-alert",
    }

    assert expected <= paths
    assert all(route.methods <= {"GET", "POST"} for route in app.routes if route.path.startswith("/operator/"))
    assert not any("submit" in path.lower() for path in paths)
    assert not any("approve" in path.lower() for path in paths)
    assert not any("proof" in path.lower() for path in paths)
    assert not any("bypass" in path.lower() for path in paths)


def test_operator_actions_require_operator_id_and_create_audit_events(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_state()

    with pytest.raises(Exception):
        OperatorActionRequest.validate_payload({"action": "mark_reviewed", "tender_id": "RFQ-001"})

    request = OperatorActionRequest.validate_payload(
        {
            "operator_id": "operator-1",
            "tender_id": "RFQ-001",
            "action": "mark_reviewed",
            "note": "Review completed manually",
            "details": {"source": "test"},
        }
    )
    record = mark_reviewed(request)

    assert record["operator_id"] == "operator-1"
    assert record["tender_id"] == "RFQ-001"
    assert record["reversible"] is True
    assert record["reviewable"] is True

    audit_events = audit_trail_service.get_audit_events(limit=20)
    assert any(item.get("event_type") == "operator_mark_reviewed" for item in audit_events["items"])

    timeline = get_operator_timeline(limit=20)
    assert timeline["events"]
    assert any(item.get("event_type") == "operator_mark_reviewed" for item in timeline["events"])


def test_operator_timeline_is_append_only(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_state()

    request = OperatorActionRequest.validate_payload(
        {"operator_id": "operator-2", "tender_id": "RFQ-002", "action": "request_clarification", "note": "Need a missing page"}
    )
    before = get_operator_timeline(limit=50)["events"]
    request_clarification(request)
    after_first = get_operator_timeline(limit=50)["events"]
    mark_reviewed(OperatorActionRequest.validate_payload({"operator_id": "operator-3", "tender_id": "RFQ-003", "action": "mark_reviewed"}))
    after_second = get_operator_timeline(limit=50)["events"]

    assert len(after_first) >= len(before) + 1
    assert len(after_second) >= len(after_first) + 1
    assert all(item in after_second for item in after_first)


def test_operator_notifications_and_capacity_are_json_safe(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_state()

    payloads = [
        contracts.build_operator_actions_response(),
        contracts.build_operator_assignments_response(),
        contracts.build_operator_timeline_response(),
        contracts.build_operator_notifications_response(),
        contracts.build_operator_capacity_response(),
    ]
    for payload in payloads:
        json.dumps(payload, default=str)
        assert payload["generated_at"]
        assert payload["data_source"]

    notifications = get_operator_notifications(limit=20)
    capacity = get_operator_capacity_snapshot()
    assignments = get_operator_assignments(limit=20)

    json.dumps(notifications, default=str)
    json.dumps(capacity, default=str)
    json.dumps(assignments, default=str)

    assert capacity["total_daily_capacity"] == 1000
    assert capacity["team_size"] == 10
    assert assignments["summary"]["operators"] == 10
    assert assignments["summary"]["capacity"] == 1000


def test_assignments_preserve_governance_and_pricing_thresholds(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_state()

    recommendations = recommend_operator_assignments(limit=20)["recommended"]
    assert all(item.get("recommendation") == "manual" for item in recommendations)
    assert all(item.get("source") in {"manual", "operator_action"} for item in recommendations)

    viability = assess_opportunity_viability(
        {
            "tender_id": "RFQ-LOW",
            "title": "Low value RFQ",
            "buyer_name": "Buyer",
            "estimated_profit": 29999,
            "gross_margin_ratio": 0.249,
            "estimated_contract_value": 150000,
        },
        {"category": "consumables", "excluded_category": False, "manual_review_required": False},
        {"blockers": [], "compliance_complexity_score": 10},
        {"method": "email"},
    )
    assert viability["profit_gate"] is False
    assert viability["margin_gate"] is False
    assert viability["final_recommendation"] == "REJECT"


def test_operator_actions_do_not_mutate_workflow_state(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_state()

    repo = WorkflowRepository(jsonl_path=workflow_state_engine.WORKFLOW_STATE_LOG_FILE)
    before = repo.fetch_recent(limit=20)

    assign_operator(
        OperatorActionRequest.validate_payload(
            {"operator_id": "operator-4", "tender_id": "RFQ-004", "action": "assign_operator", "note": "Operator assignment"}
        )
    )
    mark_reviewed(OperatorActionRequest.validate_payload({"operator_id": "operator-5", "tender_id": "RFQ-005", "action": "mark_reviewed"}))
    request_clarification(OperatorActionRequest.validate_payload({"operator_id": "operator-6", "tender_id": "RFQ-006", "action": "request_clarification"}))

    after = repo.fetch_recent(limit=20)
    assert after == before


def test_supervised_live_rollout_profile_is_visible_and_conservative(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    _seed_workflow_state()

    profile = get_supervised_live_rollout_profile()
    capacity = get_operator_capacity_snapshot()
    assignments = get_operator_assignments(limit=20)

    assert profile["name"] == "initial_supervised_live_rollout"
    assert profile["scale_status"] == "not_scaling_yet"
    assert profile["phases"][0]["operators"] == 3
    assert profile["phases"][0]["target_rfqs_per_day"] == "25-50"
    assert profile["phases"][-1]["operators"] == 7
    assert "queue stability" in profile["focus"]
    assert capacity["rollout_profile"]["name"] == profile["name"]
    assert assignments["rollout_profile"]["name"] == profile["name"]


def test_missing_runtime_data_returns_safe_fallback(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(contracts, "get_operator_actions", _raise)
    monkeypatch.setattr(contracts, "get_operator_assignments", _raise)
    monkeypatch.setattr(contracts, "get_operator_timeline", _raise)
    monkeypatch.setattr(contracts, "get_operator_notifications", _raise)
    monkeypatch.setattr(contracts, "get_operator_capacity_snapshot", _raise)

    assert contracts.build_operator_actions_response()["data_source"] == "fallback"
    assert contracts.build_operator_assignments_response()["data_source"] == "fallback"
    assert contracts.build_operator_timeline_response()["data_source"] == "fallback"
    assert contracts.build_operator_notifications_response()["data_source"] == "fallback"
    assert contracts.build_operator_capacity_response()["data_source"] == "fallback"
