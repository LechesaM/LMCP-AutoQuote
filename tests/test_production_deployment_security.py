from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

from app.api.router_registry import iter_router_specs
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.deployment.cors_policy import get_cors_origins
from app.deployment.deployment_profiles import deployment_profiles, get_deployment_profile
from app.deployment.rate_limit import RateLimitMiddleware
from app.deployment.request_id import RequestIdMiddleware
from app.deployment.security_headers import SecurityHeadersMiddleware


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_ENV", "production")
    monkeypatch.setenv("LMCP_PRODUCTION_MODE", "locked_production")
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")
    monkeypatch.setenv("LMCP_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("LMCP_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("LMCP_CORS_ORIGINS", "https://example.one,https://example.two")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()
    get_deployment_profile.cache_clear()


def _make_request(path: str = "/ping", *, request_id: str | None = None) -> Request:
    headers = []
    if request_id:
        headers.append((b"x-request-id", request_id.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers,
        "client": ("testclient", 1234),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_security_headers_and_request_id_and_rate_limit(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict:
        return {"status": "ok"}

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, enabled=True, max_requests=1, window_seconds=60)

    async def call_once(request: Request) -> Response:
        return Response(content="ok", media_type="text/plain")

    middleware = RequestIdMiddleware(app)
    response = asyncio.run(middleware.dispatch(_make_request("/ping"), call_once))
    assert response.headers["X-Request-ID"]

    security_middleware = SecurityHeadersMiddleware(app)
    response = asyncio.run(security_middleware.dispatch(_make_request("/ping"), call_once))
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

    limiter = RateLimitMiddleware(app, enabled=True, max_requests=1, window_seconds=60)
    first = asyncio.run(limiter.dispatch(_make_request("/ping"), call_once))
    second = asyncio.run(limiter.dispatch(_make_request("/ping"), call_once))
    assert first.status_code == 200
    assert second.status_code == 429


def test_cors_policy_loads_from_env(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    assert get_cors_origins() == ("https://example.one", "https://example.two")


def test_deployment_profiles_resolve_and_disable_demo_users_in_production(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    profiles = deployment_profiles()
    assert profiles["production"].demo_users_enabled is False
    assert profiles["production"].auth_required is True
    assert profiles["production"].legacy_routers_enabled is False
    assert get_deployment_profile("supervised_live").auth_required is True


def test_legacy_routers_disabled_by_default(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    specs = list(iter_router_specs())
    assert not any(spec.status != "production" for spec in specs)

