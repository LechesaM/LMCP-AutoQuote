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


def test_production_package_validation_passes_with_repo_files(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_production_package.py"), "validate_production_package_repo")
    report = module.build_production_package_report()
    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["PASS"] >= 20
    assert report["summary_counts"]["WARN"] == 0
    assert report["summary_counts"]["FAIL"] == 0
    assert report["production_governance_summary"]["runtime_separation"] is True
    assert report["production_governance_summary"]["observability_defined"] is True
    assert report["production_governance_summary"]["database_isolated"] is True
    assert report["production_governance_summary"]["production_credentials_unset"] is True

    exit_code = module.main([])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Production package validation: PASS" in output
    assert "PASS: production env example exists" in output
    assert "PASS: production compose file exists" in output
    assert "PASS: submission lock file contents" in output

    json_output = module.main(["--json"])
    assert json_output == 0


def test_production_package_validation_detects_bad_defaults(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_production_package.py"), "validate_production_package_bad")
    env_file = tmp_path / ".env.production.example"
    compose_file = tmp_path / "docker-compose.production.example.yml"
    lock_file = tmp_path / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    env_file.write_text(
        "\n".join(
            [
                "LMCP_ENV=production",
                "LMCP_PRODUCTION_MODE=manual_production",
                "LMCP_DEPLOYMENT_PROFILE=production",
                "STRICT_PRODUCTION_STARTUP=0",
                "LMCP_ALLOW_DEGRADED_STARTUP=true",
                "LMCP_ALLOW_FINAL_AUTOMATION=true",
                "LMCP_DRY_RUN_MODE=false",
                "LMCP_REQUIRE_HUMAN_SUPERVISION=false",
                "LMCP_RUNTIME_SAFETY_ENABLED=0",
                "LMCP_ENABLE_LEGACY_ROUTERS=1",
                "LMCP_OBSERVABILITY_ENABLED=0",
                "LMCP_AUDIT_RETENTION_DAYS=30",
                "LMCP_SUBMISSION_LOCK_FILE=/app/runtime/staging/go_live_guards/submission_locks.json",
                "LMCP_PRODUCTION_SUBMISSION_USERNAME=real-user",
                "LMCP_PRODUCTION_SUBMISSION_PASSWORD=real-pass",
                "LMCP_PRODUCTION_PORTAL_USERNAME=real-portal",
                "LMCP_PRODUCTION_PORTAL_PASSWORD=real-portal-pass",
                "LMCP_DATABASE_URL=postgresql://prod:prod@localhost:5432/prod",
                "DATABASE_URL=postgresql://prod:prod@localhost:5432/prod",
                "REDIS_URL=redis://localhost:6379/0",
                "CELERY_BROKER_URL=redis://localhost:6379/0",
                "CELERY_RESULT_BACKEND=redis://localhost:6379/0",
                "LMCP_RUNTIME_DIR=/app/runtime/staging",
                "LMCP_LOG_DIR=/app/runtime/staging/logs",
            ]
        ),
        encoding="utf-8",
    )
    compose_file.write_text(
        "\n".join(
            [
                "services:",
                "  backend:",
                "    environment:",
                "      LMCP_RUNTIME_DIR: /app/runtime/staging",
                "  redis:",
                "    image: redis:7-alpine",
            ]
        ),
        encoding="utf-8",
    )
    lock_file.write_text(
        json.dumps(
            {
                "final_automation_disabled": False,
                "live_portal_submission_disabled": False,
                "production_credentials_disabled": False,
                "dry_run_mode_required": False,
                "submission_execution_allowed": True,
                "human_supervision_required": False,
            }
        ),
        encoding="utf-8",
    )

    report = module.build_production_package_report(env_file=env_file, compose_file=compose_file, lock_file=lock_file)
    assert report["overall_status"] == "FAIL"
    assert report["summary_counts"]["FAIL"] >= 1
    assert any(check["level"] == "FAIL" for check in report["checks"])
