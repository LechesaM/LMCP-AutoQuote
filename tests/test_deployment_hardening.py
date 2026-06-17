from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.deployment import (
    backup_service,
    deployment_report,
    environment_validator,
    graceful_shutdown,
    recovery_service,
    runtime_integrity,
    startup_validator,
)
from app.persistence import db as persistence_db
from app.persistence.repositories import reset_persistence_health


def _prepare_runtime(monkeypatch, tmp_path: Path) -> RuntimePaths:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "backups").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "health").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_DEPLOYMENT_HARDENING_ENABLED", "1")
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    reset_persistence_health()
    persistence_db._INITIALIZED = False
    persistence_db._INITIALIZED_PATH = None
    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")
    return get_runtime_paths()


def test_startup_validation_succeeds(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)

    report = startup_validator.validate_startup(paths=paths)

    assert report["status"] in {"healthy", "degraded"}
    assert report["valid"] is True
    assert report["fatal_issues"] == []


def test_missing_runtime_dir_detected(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    broken = replace(paths, health_dir=tmp_path / "runtime" / "missing-health-dir")

    report = startup_validator.validate_startup(paths=broken)

    assert report["status"] == "unhealthy"
    assert any(issue["code"] == "missing_directory" for issue in report["fatal_issues"])


def test_invalid_env_detected_safely(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    report = environment_validator.validate_environment(
        environ={
            "LMCP_PROJECT_ROOT": str(tmp_path),
            "LMCP_RUNTIME_DIR": str(paths.runtime_root),
            "LMCP_MANUAL_PRODUCTION_DIR": str(paths.manual_production_dir),
            "LMCP_PRODUCTION_MODE": "not-a-mode",
        },
        paths=paths,
    )

    assert report["status"] == "unhealthy"
    assert any(issue["code"] == "invalid_production_mode" for issue in report["issues"])


def test_runtime_integrity_detects_corruption(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    event_path = paths.manual_production_file("workflow_events.jsonl")
    event_path.write_text(
        json.dumps(
            {
                "tender_id": "T-BAD",
                "from_stage": "discovered",
                "to_stage": "not-a-stage",
                "actor": "tester",
                "reason": "corrupt event",
                "details": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = runtime_integrity.run_integrity_checks(paths=paths)

    assert report["status"] == "unhealthy"
    assert report["workflow_issues"]


def test_backup_creation_and_verification(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.record_transition(
        "T-BACKUP",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "tester",
        "seed",
    )

    backup = backup_service.create_backup(paths=paths)
    backup_dir = Path(backup["backup_dir"])
    verification = backup_service.verify_backup(backup_dir)

    assert backup_dir.exists()
    assert verification["verified"] is True
    assert any(path.endswith("metadata.json") for path in backup["files"])


def test_recovery_validation_works(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.record_transition(
        "T-RECOVER",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "tester",
        "seed",
    )
    backup = backup_service.create_backup(paths=paths)
    backup_dir = Path(backup["backup_dir"])

    validation = recovery_service.validate_recovery(backup_dir, paths=paths)
    blocked = recovery_service.restore_backup(backup_dir, confirm_overwrite=False, paths=paths)

    assert validation["verified"] is True
    assert blocked["status"] == "blocked"


def test_graceful_shutdown_executes(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)

    snapshot = graceful_shutdown.run_graceful_shutdown(paths=paths)

    assert snapshot["status"] == "ok"
    assert snapshot["deployment_report"]["status"] in {"healthy", "degraded", "unhealthy"}


def test_deployment_report_generates(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)

    report = deployment_report.build_deployment_report(paths=paths)
    text = deployment_report.render_deployment_report_text(report)

    assert report["status"] in {"healthy", "degraded"}
    assert "Deployment status" in text


def test_degraded_startup_still_works(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    broken = replace(paths, health_dir=tmp_path / "runtime" / "missing-health-dir-2")

    report = startup_validator.validate_startup(paths=broken, allow_degraded_startup=True)

    assert report["status"] == "degraded"
    assert report["valid"] is False


def test_no_workflow_corruption_occurs(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)
    workflow_state_engine.record_transition(
        "T-SAFE",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "tester",
        "seed",
    )
    before = workflow_state_engine.get_current_state("T-SAFE").stage.value

    startup_validator.validate_startup(paths=paths)

    after = workflow_state_engine.get_current_state("T-SAFE").stage.value
    assert before == after == workflow_state_engine.WorkflowStage.EXTRACTED.value


def test_jsonl_fallback_preserved(monkeypatch, tmp_path: Path) -> None:
    paths = _prepare_runtime(monkeypatch, tmp_path)

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(persistence_db, "get_connection", _raise)

    state = workflow_state_engine.record_transition(
        "T-FALLBACK",
        workflow_state_engine.WorkflowStage.DISCOVERED,
        workflow_state_engine.WorkflowStage.EXTRACTED,
        "tester",
        "seed",
    )

    assert state.stage.value == workflow_state_engine.WorkflowStage.EXTRACTED.value
    assert paths.manual_production_file("workflow_events.jsonl").exists()
    assert paths.manual_production_file("workflow_state.jsonl").exists()
