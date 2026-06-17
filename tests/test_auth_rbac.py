from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from starlette.requests import Request

import app.auth.auth_service as auth_service_module
import app.auth.session_service as session_service_module
from app.auth.auth_models import AuthPermission
from app.auth.auth_service import authenticate_user, get_current_user, require_permission
from app.auth.jwt_service import decode_token
from app.auth.rbac import ROLE_PERMISSIONS
from app.auth.session_service import create_user, demo_users_enabled, find_user_by_email
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.operator_ops.operator_action_models import OperatorActionRequest
from app.operator_ops.operator_actions_service import dispatch_operator_action


def _prepare_runtime(monkeypatch, tmp_path: Path, *, production: bool = False, demo_users: bool = True) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_ENV", "production" if production else "development")
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "locked_production" if production else "manual_production")
    monkeypatch.setenv("LMCP_AUTH_ALLOW_DEMO_USERS", "1" if demo_users else "0")
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")
    monkeypatch.setenv("LMCP_AUTH_REQUIRED", "1")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()


def _request_with_token(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))],
        "client": ("testclient", 1234),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_login_succeeds_for_demo_user_in_local_dev_mode(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("admin@lmcp.local", "admin")
    assert session["access_token"]
    assert "manage_users" in session["permissions"]
    payload = decode_token(session["access_token"])
    assert payload["role"] == "admin"

    request = _request_with_token(session["access_token"])
    me = get_current_user(request)
    assert me["user"]["role"] == "admin"


def test_login_seeds_auth_users_only_once(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=False)

    create_user(
        user_id="operator",
        email="operator@lmcp.local",
        display_name="Operator",
        role="operator",
        password="operator",
        overwrite=True,
    )

    calls = {"count": 0}

    def count_seed_calls() -> None:
        calls["count"] += 1

    monkeypatch.setattr(auth_service_module, "seed_demo_users_if_needed", count_seed_calls, raising=False)
    monkeypatch.setattr(session_service_module, "seed_demo_users_if_needed", count_seed_calls, raising=False)

    session = authenticate_user("operator@lmcp.local", "operator")

    assert session["access_token"]
    assert calls["count"] == 1


def test_login_seeds_missing_demo_users_in_partial_db(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    create_user(
        user_id="operator",
        email="operator@lmcp.local",
        display_name="Operator",
        role="operator",
        password="operator",
        overwrite=True,
    )

    session = authenticate_user("supervisor@lmcp.local", "supervisor")

    assert session["access_token"]
    supervisor = find_user_by_email("supervisor@lmcp.local")
    assert supervisor is not None
    assert supervisor.user_id == "supervisor"


def test_demo_users_disabled_in_production_unless_configured(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=True, demo_users=False)

    assert demo_users_enabled() is False
    with pytest.raises(Exception):
        authenticate_user("admin@lmcp.local", "admin")


def test_token_contains_role_and_permissions(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("supervisor@lmcp.local", "supervisor")
    payload = decode_token(session["access_token"])
    assert payload["role"] == "supervisor"
    assert "run_operator_assign_supplier" in payload["permissions"]
    assert "view_operator_review" in payload["permissions"]
    assert "run_operator_mark_reviewed" in payload["permissions"]
    assert "run_operator_request_clarification" in payload["permissions"]
    assert "run_operator_reject_rfq" in payload["permissions"]
    assert "run_operator_escalate_rfq" in payload["permissions"]
    assert "run_operator_acknowledge_alert" in payload["permissions"]
    assert "run_submission_package_generate" in payload["permissions"]
    assert "view_supplier_quote_intelligence" in payload["permissions"]
    assert "run_supplier_quote_intelligence" in payload["permissions"]


def test_operator_can_view_supplier_quote_intelligence_but_cannot_run(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("operator@lmcp.local", "operator")
    payload = decode_token(session["access_token"])
    assert payload["role"] == "operator"
    assert "view_supplier_quote_intelligence" in payload["permissions"]
    assert "view_operator_review" in payload["permissions"]
    assert "view_audit" in payload["permissions"]
    assert "view_governance" in payload["permissions"]
    assert "run_operator_mark_reviewed" not in payload["permissions"]
    assert "run_operator_request_clarification" not in payload["permissions"]
    assert "run_operator_reject_rfq" not in payload["permissions"]
    assert "run_operator_escalate_rfq" not in payload["permissions"]
    assert "run_operator_assign_supplier" not in payload["permissions"]
    assert "run_operator_acknowledge_alert" not in payload["permissions"]
    assert "run_submission_package_generate" not in payload["permissions"]
    assert "run_supplier_quote_auto_ingest" not in payload["permissions"]
    assert "run_supplier_quote_ingestion" not in payload["permissions"]


def test_read_only_cannot_call_operator_post_routes(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("readonly@lmcp.local", "read_only")
    request = _request_with_token(session["access_token"])
    with pytest.raises(Exception):
        require_permission("run_operator_assign_supplier")(request)


def test_operator_cannot_assign_if_permission_missing(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("operator@lmcp.local", "operator")
    request = _request_with_token(session["access_token"])
    with pytest.raises(Exception):
        require_permission("run_operator_assign_supplier")(request)


def test_supervisor_can_assign(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("supervisor@lmcp.local", "supervisor")
    request = _request_with_token(session["access_token"])
    require_permission("run_operator_assign_supplier")(request)

    record = dispatch_operator_action(
        OperatorActionRequest.validate_payload(
            {"operator_id": "supervisor", "tender_id": "RFQ-003", "action": "assign_operator"}
        )
    )
    assert record["action"] == "assign_operator"


def test_supervisor_can_execute_and_export_submission_routes(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("supervisor@lmcp.local", "supervisor")
    request = _request_with_token(session["access_token"])
    require_permission("execute_submission")(request)
    require_permission("approve_submission")(request)
    require_permission("export_audit")(request)
    require_permission("run_operator_mark_reviewed")(request)
    require_permission("run_operator_request_clarification")(request)
    require_permission("run_operator_reject_rfq")(request)
    require_permission("run_operator_escalate_rfq")(request)
    require_permission("run_operator_assign_supplier")(request)
    require_permission("run_operator_acknowledge_alert")(request)
    require_permission("run_submission_package_generate")(request)


def test_operator_can_view_submission_pages_but_cannot_execute_submission_routes(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("operator@lmcp.local", "operator")
    request = _request_with_token(session["access_token"])
    require_permission("view_rfqs")(request)
    require_permission("view_operator_queue")(request)
    require_permission("view_operator_review")(request)
    require_permission("view_audit")(request)
    require_permission("view_governance")(request)
    with pytest.raises(Exception):
        require_permission("approve_submission")(request)
    with pytest.raises(Exception):
        require_permission("execute_submission")(request)
    with pytest.raises(Exception):
        require_permission("verify_submission")(request)
    with pytest.raises(Exception):
        require_permission("reconcile_submission")(request)
    with pytest.raises(Exception):
        require_permission("export_audit")(request)
    for permission in [
        "run_operator_mark_reviewed",
        "run_operator_request_clarification",
        "run_operator_reject_rfq",
        "run_operator_escalate_rfq",
        "run_operator_assign_supplier",
        "run_operator_acknowledge_alert",
        "run_submission_package_generate",
    ]:
        with pytest.raises(Exception):
            require_permission(permission)(request)


def test_read_only_cannot_execute_or_export_submission_routes(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("readonly@lmcp.local", "read_only")
    request = _request_with_token(session["access_token"])
    with pytest.raises(Exception):
        require_permission("execute_submission")(request)
    with pytest.raises(Exception):
        require_permission("export_audit")(request)


def test_no_role_has_autonomous_permissions() -> None:
    forbidden = {"autonomous_submit", "auto_approve", "bypass_review_ready", "bypass_proof_capture"}
    for permissions in ROLE_PERMISSIONS.values():
        assert forbidden.isdisjoint(set(permissions))


def test_legacy_review_aliases_removed_from_auth_enum_and_rbac() -> None:
    legacy_aliases = {
        "assign_operator",
        "mark_reviewed",
        "escalate_review",
        "archive_rfq",
        "acknowledge_alert",
    }
    all_permissions = {permission.value for permission in AuthPermission}

    assert legacy_aliases.isdisjoint(all_permissions)
    for permissions in ROLE_PERMISSIONS.values():
        assert legacy_aliases.isdisjoint(set(permissions))
