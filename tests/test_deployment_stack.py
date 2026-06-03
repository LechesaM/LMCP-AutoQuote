from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def test_deployment_files_encode_production_hardening_defaults() -> None:
    root_dockerfile = _read("Dockerfile")
    frontend_dockerfile = _read("frontend/command-centre/Dockerfile")
    docker_compose = _read("docker-compose.yml")
    production_compose = _read("docker-compose.production.yml")
    nginx_conf = _read("nginx/default.conf")
    production_nginx_conf = _read("nginx/production.conf")
    env_example = _read(".env.example")
    production_env_example = _read(".env.production.example")
    systemd_unit = _read("deploy/systemd/lmcp-autoquote.service")
    backup_runtime_script = _read("scripts/ops/backup_runtime.sh")
    restore_verify_script = _read("scripts/ops/restore_verify.sh")
    production_workers_script = _read("scripts/start_production_workers.sh")
    browser_workflow_script = _read("scripts/operator_workflow_browser_check.mjs")
    review_debug_script = _read("scripts/debug_review_page.mjs")

    assert "uvicorn" in root_dockerfile
    assert "app.main:app" in root_dockerfile
    assert "python:3.11-slim" in root_dockerfile
    assert "npm run build" in frontend_dockerfile
    assert "nginx" in frontend_dockerfile
    assert "arg nginx_conf" in frontend_dockerfile
    assert "backend:" in docker_compose
    assert "frontend:" in docker_compose
    assert "ports:" in docker_compose
    assert "restart: unless-stopped" in production_compose
    assert "healthcheck" in production_compose
    assert "worker:" in production_compose
    assert "operations-worker:" in production_compose
    assert "beat:" in production_compose
    assert "prometheus:" in production_compose
    assert "grafana:" in production_compose
    assert "443:443" in production_compose
    assert "x-content-type-options" in nginx_conf
    assert "x-frame-options" in nginx_conf
    assert "referrer-policy" in nginx_conf
    assert "permissions-policy" in nginx_conf
    assert "listen 443 ssl" in production_nginx_conf
    assert "ssl_certificate" in production_nginx_conf
    assert "lmcp_auth_required=1" in env_example
    assert "lmcp_enable_legacy_routers=0" in env_example
    assert "lmcp_auth_allow_demo_users=1" in env_example
    assert "lmcp_deployment_profile=local_dev" in env_example
    assert "lmcp_env=production" in production_env_example
    assert "lmcp_database_url" in production_env_example
    assert "celery_broker_url" in production_env_example
    assert "docker-compose.production.yml" in systemd_unit
    assert "restart=on-failure" in systemd_unit
    assert "script_dir" in backup_runtime_script
    assert "cd \"$script_dir/../..\"" in backup_runtime_script
    assert "script_dir" in restore_verify_script
    assert "cd \"$script_dir/../..\"" in restore_verify_script
    assert "script_dir" in production_workers_script
    assert "cd \"$script_dir/..\"" in production_workers_script
    assert "operations_queue" in production_workers_script
    assert "require_operations_worker_ready" in production_workers_script
    assert "operations_worker_ready_timeout_seconds" in production_workers_script
    assert "operations_worker_ready_poll_interval_seconds" in production_workers_script
    assert "new url(\"../frontend/command-centre/node_modules/playwright/index.mjs\", import.meta.url)" in browser_workflow_script
    assert "monthly_quotes" in browser_workflow_script
    assert "/users/cash" not in browser_workflow_script
    assert "lmcp_playwright_chromium_path" in browser_workflow_script or "playwright_chromium_path" in browser_workflow_script
    assert "/users/cash" not in review_debug_script
    assert "project_root" in review_debug_script
    assert "new url(\"../frontend/command-centre/node_modules/playwright/index.mjs\", import.meta.url)" in review_debug_script
    assert "lmcp_playwright_executable_path" in review_debug_script or "lmcp_playwright_chromium_path" in review_debug_script


def test_local_manual_production_start_script_targets_command_centre_frontend() -> None:
    script = _read("scripts/start_local_manual_production.sh")

    assert "lmcp_project_root" in script
    assert "lmcp_runtime_dir" in script
    assert "lmcp_allow_degraded_startup" in script
    assert "lmcp_local_backend_host" in script
    assert "lmcp_local_frontend_host" in script
    assert "python3 -m uvicorn" in script
    assert "npm run dev" in script
    assert "--strictport" in script
