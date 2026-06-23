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


def test_production_access_governance_validation_passes_with_repo_files(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_production_access_governance.py"), "validate_production_access_governance_repo")
    report = module.build_production_access_governance_report()
    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["PASS"] >= 10
    assert report["summary_counts"]["WARN"] == 0
    assert report["summary_counts"]["FAIL"] == 0
    assert report["production_access_governance_summary"]["credentials_placeholder_only"] is True
    assert report["production_access_governance_summary"]["rbac_roles_defined"] is True
    assert report["production_access_governance_summary"]["supervision_roles_isolated"] is True
    assert report["production_access_governance_summary"]["executive_override_roles_isolated"] is True
    assert report["production_access_governance_summary"]["deployment_access_segregation"] is True
    assert report["production_access_governance_summary"]["observability_access_segregation"] is True
    assert report["production_access_governance_summary"]["admin_escalation_paths"] is True
    assert report["production_access_governance_summary"]["production_lock_enforced"] is True
    assert report["production_access_governance_summary"]["audit_retention_enforced"] is True

    exit_code = module.main([])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Production access governance validation: PASS" in output
    assert "PASS: production env example exists" in output
    assert "PASS: access governance placeholder structure" in output

    json_output = module.main(["--json"])
    assert json_output == 0


def test_production_access_governance_validation_detects_bad_defaults(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_production_access_governance.py"), "validate_production_access_governance_bad")
    env_file = tmp_path / ".env.production.example"
    compose_file = tmp_path / "docker-compose.production.example.yml"
    lock_file = tmp_path / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
    access_readme = tmp_path / "runtime" / "production" / "access_governance" / "README.md"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    access_readme.parent.mkdir(parents=True, exist_ok=True)

    env_file.write_text(
        "\n".join(
            [
                "LMCP_ENV=production",
                "LMCP_PRODUCTION_MODE=manual_production",
                "LMCP_DEPLOYMENT_PROFILE=production",
                "LMCP_ALLOW_FINAL_AUTOMATION=true",
                "LMCP_DRY_RUN_MODE=false",
                "LMCP_REQUIRE_HUMAN_SUPERVISION=false",
                "LMCP_SECRET_KEY=supersecretvalue",
                "POSTGRES_PASSWORD=supersecret-db",
                "LMCP_GRAFANA_ADMIN_PASSWORD=real-grafana-pass",
                "LMCP_PRODUCTION_SUBMISSION_USERNAME=real-user",
                "LMCP_PRODUCTION_SUBMISSION_PASSWORD=real-pass",
                "LMCP_PRODUCTION_PORTAL_USERNAME=real-portal",
                "LMCP_PRODUCTION_PORTAL_PASSWORD=real-portal-pass",
                "LMCP_RBAC_ROLES=operator,supervisor",
                "LMCP_SUPERVISION_ROLES=operator,executive_override",
                "LMCP_EXECUTIVE_OVERRIDE_ROLES=supervisor",
                "LMCP_DEPLOYMENT_ACCESS_SEGREGATION=false",
                "LMCP_OBSERVABILITY_ACCESS_SEGREGATION=false",
                "LMCP_ADMIN_ESCALATION_ROLES=operator",
                "LMCP_PRODUCTION_LOCK_ENFORCED=false",
                "LMCP_AUDIT_RETENTION_ENFORCED=false",
                "LMCP_AUDIT_RETENTION_DAYS=30",
                "LMCP_SUBMISSION_LOCK_FILE=/app/runtime/staging/go_live_guards/submission_locks.json",
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
                "      LMCP_ACCESS_GOVERNANCE_PROFILE: manual_production",
                "      LMCP_RBAC_ROLES: operator,supervisor",
                "      LMCP_DEPLOYMENT_ACCESS_SEGREGATION: \"false\"",
                "      LMCP_OBSERVABILITY_ACCESS_SEGREGATION: \"false\"",
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
    access_readme.write_text("No secrets? not enough.\n", encoding="utf-8")

    report = module.build_production_access_governance_report(
        env_file=env_file,
        compose_file=compose_file,
        lock_file=lock_file,
        access_readme=access_readme,
    )
    assert report["overall_status"] == "FAIL"
    assert report["summary_counts"]["FAIL"] >= 1
    assert any(check["level"] == "FAIL" for check in report["checks"])
