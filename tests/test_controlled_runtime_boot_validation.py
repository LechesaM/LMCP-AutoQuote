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
        "LMCP_ALLOW_FINAL_AUTOMATION=false",
        "LMCP_DRY_RUN_MODE=true",
        "LMCP_REQUIRE_HUMAN_SUPERVISION=true",
        "LMCP_PRODUCTION_MODE=locked_production",
        "LMCP_DEPLOYMENT_PROFILE=production",
        "STRICT_PRODUCTION_STARTUP=1",
        "LMCP_ALLOW_DEGRADED_STARTUP=false",
        "LMCP_RUNTIME_SAFETY_ENABLED=1",
        "LMCP_OBSERVABILITY_ENABLED=1",
        "LMCP_SECRET_KEY=change-me-production-secret",
        "LMCP_GRAFANA_ADMIN_PASSWORD=change-me-grafana",
        "POSTGRES_PASSWORD=change-me-production-db",
        "LMCP_PRODUCTION_SUBMISSION_USERNAME=",
        "LMCP_PRODUCTION_SUBMISSION_PASSWORD=",
        "LMCP_PRODUCTION_PORTAL_USERNAME=",
        "LMCP_PRODUCTION_PORTAL_PASSWORD=",
        "LMCP_SUBMISSION_LOCK_FILE=/app/runtime/production/go_live_guards/submission_locks.json",
        "LMCP_RUNTIME_DIR=/app/runtime/production",
    ]
    if bad:
        lines[0] = "LMCP_ALLOW_FINAL_AUTOMATION=true"
        lines[1] = "LMCP_DRY_RUN_MODE=false"
        lines[2] = "LMCP_REQUIRE_HUMAN_SUPERVISION=false"
        lines[9] = "LMCP_SECRET_KEY=real-secret"
        lines[10] = "LMCP_GRAFANA_ADMIN_PASSWORD=real-grafana"
        lines[11] = "POSTGRES_PASSWORD=real-db"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_compose(path: Path, *, bad: bool = False) -> None:
    if bad:
        path.write_text("services:\n  backend:\n    image: example/backend\n", encoding="utf-8")
        return
    path.write_text(
        "\n".join(
            [
                "services:",
                "  backend:",
                "    healthcheck:",
                "      test: [\"CMD-SHELL\", \"curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1\"]",
                "  frontend:",
                "  postgres:",
                "  redis:",
                "  worker:",
                "  prometheus:",
                "  grafana:",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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


def _compose_config_ok(*args, **kwargs):
    return True, "services:\n  backend:\n  frontend:\n  postgres:\n  redis:\n  worker:\n  prometheus:\n  grafana:\n", ""


def _compose_config_bad(*args, **kwargs):
    return False, "", "compose failed"


def _compose_up_ok(project_name: str, *args, **kwargs):
    return _CompletedProcess(0, stdout="started")


def _compose_down_ok(project_name: str, *args, **kwargs):
    return _CompletedProcess(0, stdout="stopped")


def _compose_ps_ok(project_name: str, *args, **kwargs):
    services = [
        {"Service": "backend", "State": "running", "Health": "healthy"},
        {"Service": "frontend", "State": "running", "Health": "healthy"},
        {"Service": "postgres", "State": "running", "Health": "healthy"},
        {"Service": "redis", "State": "running", "Health": "healthy"},
        {"Service": "worker", "State": "running", "Health": "healthy"},
        {"Service": "prometheus", "State": "running", "Health": "running"},
        {"Service": "grafana", "State": "running", "Health": "running"},
    ]
    return _CompletedProcess(0, stdout=json.dumps(services))


def _probe_http_ok(url: str, timeout: float = 10.0):
    if "8001/health" in url:
        return {"status_code": 200, "payload": {"status": "ok"}}
    if "4176" in url:
        return {"status_code": 200, "payload": {"body": "<html></html>"}}
    raise AssertionError(f"unexpected URL {url}")


def _probe_http_bad(url: str, timeout: float = 10.0):
    raise RuntimeError("endpoint unavailable")


def test_controlled_runtime_boot_validation_generates_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_controlled_runtime_boot_validation.py"), "run_controlled_runtime_boot_validation_repo")
    env_file = tmp_path / ".env.production.example"
    compose_file = tmp_path / "docker-compose.production.example.yml"
    lock_file = tmp_path / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-boot-validations"

    _write_env(env_file)
    _write_compose(compose_file)
    _write_lock(lock_file)

    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(module, "COMPOSE_FILE", compose_file)
    monkeypatch.setattr(module, "LOCK_FILE", lock_file)
    monkeypatch.setattr(module, "_build_package_report", lambda: {"overall_status": "PASS", "production_governance_summary": {"production_governance_score": 100.0}})
    monkeypatch.setattr(module, "_build_access_report", lambda: {"overall_status": "PASS", "production_access_governance_summary": {"access_governance_score": 100.0}})
    monkeypatch.setattr(module, "_compose_config", _compose_config_ok)
    monkeypatch.setattr(module, "_run_compose", lambda project_name, *args, **kwargs: _compose_up_ok(project_name) if "up" in args else _compose_ps_ok(project_name) if "ps" in args else _compose_down_ok(project_name))
    monkeypatch.setattr(module, "_wait_for_http", lambda url, timeout_seconds=120, interval=2.0: _probe_http_ok(url))

    payload = module.build_runtime_boot_validation_report(
        env_file=env_file,
        compose_file=compose_file,
        lock_file=lock_file,
        output_root=output_root,
        compose_timeout_seconds=1,
        boot_timeout_seconds=1,
    )
    assert payload["overall_status"] == "PASS"
    assert payload["summary_counts"]["FAIL"] == 0
    assert payload["boot_readiness_summary"]["backend_started"] is True
    assert payload["boot_readiness_summary"]["frontend_started"] is True
    assert payload["boot_readiness_summary"]["dry_run_mode_enabled"] is True
    assert payload["boot_readiness_summary"]["human_supervision_required"] is True

    exit_code = module.main(["--output-root", str(output_root)])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Runtime boot validation:" in output
    assert (output_root / "latest_runtime_boot_validation.json").exists()
    assert (output_root / "latest_runtime_boot_validation.md").exists()


def test_controlled_runtime_boot_validation_detects_bad_defaults(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_controlled_runtime_boot_validation.py"), "run_controlled_runtime_boot_validation_bad")
    env_file = tmp_path / ".env.production.example"
    compose_file = tmp_path / "docker-compose.production.example.yml"
    lock_file = tmp_path / "runtime" / "production" / "go_live_guards" / "submission_locks.json"
    output_root = tmp_path / "runtime" / "staging" / "runtime-boot-validations"

    _write_env(env_file, bad=True)
    _write_compose(compose_file, bad=True)
    _write_lock(lock_file, bad=True)

    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(module, "COMPOSE_FILE", compose_file)
    monkeypatch.setattr(module, "LOCK_FILE", lock_file)
    monkeypatch.setattr(module, "_build_package_report", lambda: {"overall_status": "FAIL", "production_governance_summary": {"production_governance_score": 60.0}})
    monkeypatch.setattr(module, "_build_access_report", lambda: {"overall_status": "FAIL", "production_access_governance_summary": {"access_governance_score": 50.0}})
    monkeypatch.setattr(module, "_compose_config", _compose_config_bad)
    monkeypatch.setattr(module, "_run_compose", lambda project_name, *args, **kwargs: _compose_up_ok(project_name) if "down" in args else _CompletedProcess(1, stderr="failed"))
    monkeypatch.setattr(module, "_wait_for_http", lambda url, timeout_seconds=120, interval=2.0: _probe_http_bad(url))

    payload = module.build_runtime_boot_validation_report(
        env_file=env_file,
        compose_file=compose_file,
        lock_file=lock_file,
        output_root=output_root,
        compose_timeout_seconds=1,
        boot_timeout_seconds=1,
    )
    assert payload["overall_status"] == "FAIL"
    assert payload["summary_counts"]["FAIL"] >= 1
    assert any(check["level"] == "FAIL" for check in payload["checks"])
