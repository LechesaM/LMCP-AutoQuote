from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from starlette.requests import Request

from app.auth.auth_service import authenticate_user, get_current_user, require_permission
from app.auth.jwt_service import decode_token
from app.auth.rbac import ROLE_PERMISSIONS
from app.auth.session_service import demo_users_enabled
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
    assert "assign_operator" in payload["permissions"]


def test_read_only_cannot_call_operator_post_routes(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("readonly@lmcp.local", "read_only")
    request = _request_with_token(session["access_token"])
    with pytest.raises(Exception):
        require_permission("assign_operator")(request)


def test_operator_cannot_assign_if_permission_missing(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("operator@lmcp.local", "operator")
    request = _request_with_token(session["access_token"])
    with pytest.raises(Exception):
        require_permission("assign_operator")(request)


def test_supervisor_can_assign(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path, production=False, demo_users=True)

    session = authenticate_user("supervisor@lmcp.local", "supervisor")
    request = _request_with_token(session["access_token"])
    require_permission("assign_operator")(request)

    record = dispatch_operator_action(
        OperatorActionRequest.validate_payload(
            {"operator_id": "supervisor", "tender_id": "RFQ-003", "action": "assign_operator"}
        )
    )
    assert record["action"] == "assign_operator"


def test_no_role_has_autonomous_permissions() -> None:
    forbidden = {"autonomous_submit", "auto_approve", "bypass_review_ready", "bypass_proof_capture"}
    for permissions in ROLE_PERMISSIONS.values():
        assert forbidden.isdisjoint(set(permissions))

