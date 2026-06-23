from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _CompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_env(path: Path, *, bad: bool = False) -> None:
    lines = [
        "LMCP_ENV=production",
        "LMCP_PRODUCTION_MODE=locked_production",
        "LMCP_DEPLOYMENT_PROFILE=production",
        "STRICT_PRODUCTION_STARTUP=1",
        "LMCP_ALLOW_DEGRADED_STARTUP=false",
        "LMCP_ALLOW_FINAL_AUTOMATION=false",
        "LMCP_DRY_RUN_MODE=true",
        "LMCP_REQUIRE_HUMAN_SUPERVISION=true",
        "LMCP_RUNTIME_SAFETY_ENABLED=1",
        "LMCP_OBSERVABILITY_ENABLED=1",
        "LMCP_SECRET_KEY=change-me-production-secret",
        "LMCP_CORS_ORIGINS=https://lmcp.example.com",
        "LMCP_OPERATOR_SESSION_COOKIE_SECURE=true",
        "LMCP_OPERATOR_AUTH_ALLOW_DEV_FALLBACK=false",
        "PORTAL_ISOLATION_ENABLED=true",
        "LMCP_AUDIT_RETENTION_DAYS=3650",
        "LMCP_ALLOW_FINAL_AUTOMATION=false",
        "LMCP_PRODUCTION_SUBMISSION_USERNAME=",
        "LMCP_PRODUCTION_SUBMISSION_PASSWORD=",
        "LMCP_PRODUCTION_PORTAL_USERNAME=",
        "LMCP_PRODUCTION_PORTAL_PASSWORD=",
        "LMCP_DATABASE_URL=postgresql://lmcp_production:change-me-production-db@postgres:5432/lmcp_production",
        "DATABASE_URL=postgresql://lmcp_production:change-me-production-db@postgres:5432/lmcp_production",
        "REDIS_URL=redis://redis:6379/0",
        "CELERY_BROKER_URL=redis://redis:6379/0",
        "CELERY_RESULT_BACKEND=redis://redis:6379/0",
        "LMCP_RUNTIME_DIR=/app/runtime/production",
        "LMCP_LOG_DIR=/app/runtime/production/logs",
        "LMCP_HEALTH_DIR=/app/runtime/production/health",
        "LMCP_EXPORTS_DIR=/app/runtime/production/exports",
        "LMCP_TEMP_DIR=/app/runtime/production/tmp",
        "LMCP_BACKUPS_DIR=/app/runtime/production/backups",
        "LMCP_AUDIT_TRAIL_DIR=/app/runtime/production/audit_trail",
        "LMCP_SUBMISSION_HISTORY_DIR=/app/runtime/production/submission_history",
        "LMCP_LOCKS_DIR=/app/runtime/production/locks",
        "LMCP_SUBMISSION_PROOFS_DIR=/app/runtime/production/submission_proofs",
        "LMCP_PORTAL_SUBMISSION_DIR=/app/runtime/production/portal_submission",
        "LMCP_FINAL_SUBMISSION_DIR=/app/runtime/production/final_submission_v47_5",
        "LMCP_PROOF_CENTER_DIR=/app/runtime/production/proof_center",
        "LMCP_MANUAL_PRODUCTION_DIR=/app/runtime/production/manual_production",
        "LMCP_MANUAL_PRODUCTION_DB_PATH=/app/runtime/production/manual_production/lmcp_operations.db",
        "LMCP_SUBMISSION_LOCK_FILE=/app/runtime/production/go_live_guards/submission_locks.json",
        "LMCP_OPERATOR_AUTH_DIR=/app/runtime/production/operator_auth",
        "LMCP_OPERATOR_AUTH_DB_PATH=/app/runtime/production/operator_auth/operator_auth.sqlite3",
        "LMCP_HANDWRITING_RUNTIME_DIR=/app/runtime/production/handwriting_simulation",
        "LMCP_TENDER_FORM_RUNTIME_DIR=/app/runtime/production/tender_form_intelligence",
        "LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR=/app/runtime/production/clickable_navigation_v40",
        "PORTAL_ISOLATION_STATE_FILE=/app/runtime/production/portal_isolation_state.json",
        "POSTGRES_USER=lmcp_production",
        "POSTGRES_PASSWORD=change-me-production-db",
    ]
    if bad:
        lines[5] = "LMCP_ALLOW_FINAL_AUTOMATION=true"
        lines[6] = "LMCP_DRY_RUN_MODE=false"
        lines[7] = "LMCP_REQUIRE_HUMAN_SUPERVISION=false"
        lines[10] = "LMCP_SECRET_KEY=real-secret"
        lines[18] = "LMCP_PRODUCTION_SUBMISSION_USERNAME=real-user"
        lines[19] = "LMCP_PRODUCTION_SUBMISSION_PASSWORD=real-pass"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_compose(path: Path, *, bad: bool = False) -> None:
    services = [
        "services:",
        "  backend:",
        "    healthcheck:",
        "      test: [\"CMD-SHELL\", \"curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1\"]",
        "  frontend:",
        "  redis:",
        "  postgres:",
        "  worker:",
        "  prometheus:",
        "  grafana:",
    ]
    if bad:
        services = [
            "services:",
            "  backend:",
            "    healthcheck:",
            "      test: [\"CMD-SHELL\", \"echo missing-health\"]",
            "  frontend:",
            "  redis:",
            "  postgres:",
            "  worker:",
        ]
    path.write_text("\n".join(services) + "\n", encoding="utf-8")


def _write_lock(path: Path, *, bad: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "final_automation_disabled": True,
        "live_portal_submission_disabled": True,
        "production_credentials_disabled": True,
        "dry_run_mode_required": True,
        "submission_execution_allowed": False,
        "human_supervision_required": True,
    }
    if bad:
        payload.update(
            {
                "final_automation_disabled": False,
                "live_portal_submission_disabled": False,
                "production_credentials_disabled": False,
                "dry_run_mode_required": False,
                "submission_execution_allowed": True,
                "human_supervision_required": False,
            }
        )
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_production_smoke_test_generates_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_production_smoke_test.py"), "run_production_smoke_test_repo")
    env_file = tmp_path / ".env.production.example"
    compose_file = tmp_path / "docker-compose.production.example.yml"
    lock_file = tmp_path / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "production-smoke-tests"

    _write_env(env_file)
    _write_compose(compose_file)
    _write_lock(lock_file)

    monkeypatch.setattr(module, "_build_package_report", lambda: {"overall_status": "PASS", "production_governance_summary": {"production_governance_score": 100.0}})
    monkeypatch.setattr(module, "_build_access_report", lambda: {"overall_status": "PASS", "production_access_governance_summary": {"access_governance_score": 100.0}})
    monkeypatch.setattr(module, "_compose_config", lambda _: (True, "services:\n  backend:\n    healthcheck:\n      test: [\"CMD-SHELL\", \"curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1\"]\n  frontend:\n  redis:\n  postgres:\n  worker:\n  prometheus:\n  grafana:\n", ""))

    payload = module.build_production_smoke_test_report(
        env_file=env_file,
        compose_file=compose_file,
        lock_file=lock_file,
        output_root=output_root,
    )
    assert payload["overall_status"] == "PASS"
    assert payload["summary_counts"]["FAIL"] == 0
    assert payload["compose_validation"]["compose_parsed"] is True
    assert payload["compose_validation"]["service_expectations"]["backend"] is True
    assert payload["compose_validation"]["service_expectations"]["frontend"] is True
    assert payload["compose_validation"]["service_expectations"]["redis"] is True
    assert payload["compose_validation"]["service_expectations"]["postgres"] is True
    assert payload["compose_validation"]["service_expectations"]["worker"] is True
    assert payload["compose_validation"]["service_expectations"]["prometheus"] is True
    assert payload["compose_validation"]["service_expectations"]["grafana"] is True
    assert payload["safety_guarantees"]["dry_run_protections_active"] is True

    exit_code = module.main(["--output-root", str(output_root)])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Production smoke test:" in output
    assert (output_root / "latest_production_smoke_test.json").exists()
    assert (output_root / "latest_production_smoke_test.md").exists()


def test_production_smoke_test_detects_bad_defaults(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_production_smoke_test.py"), "run_production_smoke_test_bad")
    env_file = tmp_path / ".env.production.example"
    compose_file = tmp_path / "docker-compose.production.example.yml"
    lock_file = tmp_path / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "production-smoke-tests"

    _write_env(env_file, bad=True)
    _write_compose(compose_file, bad=True)
    _write_lock(lock_file, bad=True)

    monkeypatch.setattr(module, "_build_package_report", lambda: {"overall_status": "FAIL", "production_governance_summary": {"production_governance_score": 60.0}})
    monkeypatch.setattr(module, "_build_access_report", lambda: {"overall_status": "FAIL", "production_access_governance_summary": {"access_governance_score": 50.0}})
    monkeypatch.setattr(module, "_compose_config", lambda _: (True, "services:\n  backend:\n    healthcheck:\n      test: [\"CMD-SHELL\", \"echo missing-health\"]\n  frontend:\n  redis:\n  postgres:\n  worker:\n", ""))

    payload = module.build_production_smoke_test_report(
        env_file=env_file,
        compose_file=compose_file,
        lock_file=lock_file,
        output_root=output_root,
    )
    assert payload["overall_status"] == "FAIL"
    assert payload["summary_counts"]["FAIL"] >= 1
    assert any(check["level"] == "FAIL" for check in payload["checks"])
