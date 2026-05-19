from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from app.api.router_registry import iter_router_specs
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.deployment.deployment_profiles import deployment_profiles, get_deployment_profile
from app.deployment.production_startup import configure_production_app
from app.deployment.rate_limit import RateLimitMiddleware
from app.deployment.request_id import RequestIdMiddleware
from app.deployment.security_headers import SecurityHeadersMiddleware


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


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
    monkeypatch.setenv("LMCP_AUTH_ALLOW_DEMO_USERS", "0")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()
    get_deployment_profile.cache_clear()


def test_deployment_files_encode_production_hardening_defaults() -> None:
    root_dockerfile = _read("Dockerfile")
    frontend_dockerfile = _read("frontend/command-centre/Dockerfile")
    docker_compose = _read("docker-compose.yml")
    nginx_conf = _read("nginx/default.conf")
    env_example = _read(".env.example")

    assert "uvicorn" in root_dockerfile
    assert "app.main:app" in root_dockerfile
    assert "python:3.11-slim" in root_dockerfile
    assert "npm run build" in frontend_dockerfile
    assert "nginx" in frontend_dockerfile
    assert "backend:" in docker_compose
    assert "frontend:" in docker_compose
    assert "ports:" in docker_compose
    assert "x-content-type-options" in nginx_conf
    assert "x-frame-options" in nginx_conf
    assert "referrer-policy" in nginx_conf
    assert "permissions-policy" in nginx_conf
    assert "lmcp_auth_required=1" in env_example
    assert "lmcp_enable_legacy_routers=0" in env_example
    assert "lmcp_auth_allow_demo_users=1" in env_example
    assert "lmcp_deployment_profile=local_dev" in env_example


def test_deployment_profiles_and_startup_middleware_resolve(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    profiles = deployment_profiles()
    assert profiles["production"].demo_users_enabled is False
    assert profiles["production"].auth_required is True
    assert profiles["production"].legacy_routers_enabled is False
    assert profiles["supervised_live"].auth_required is True

    app = FastAPI()
    configure_production_app(app)

    middleware_names = {middleware.cls.__name__ for middleware in app.user_middleware}
    assert "RequestIdMiddleware" in middleware_names
    assert "SecurityHeadersMiddleware" in middleware_names
    assert "RateLimitMiddleware" in middleware_names

    limiter = RateLimitMiddleware(app, enabled=True, max_requests=1, window_seconds=60)
    assert limiter.enabled is True
    assert limiter.max_requests == 1


def test_legacy_router_specs_remain_disabled_by_default(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    loaded = [spec.name for spec in iter_router_specs()]
    assert not any(name for name in loaded if "autonomous" in name.lower())
