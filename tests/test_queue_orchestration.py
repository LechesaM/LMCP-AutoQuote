from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core import workflow_state_engine
from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.dashboard import dashboard_service, operator_actions_service, workflow_queue_service
from app.domain.workflow import WorkflowStage
from app.monitoring.metrics_service import reset_test_metrics
from app.monitoring.workflow_monitor import find_stuck_workflows, get_workflow_summary
from app.orchestration import job_history, operator_recovery_actions, queue_manager, queue_monitor, retry_policy, workflow_recovery
from app.orchestration.job_models import QueueJobStatus, QueueJobType
from app.persistence import db as persistence_db
from app.persistence.repositories import get_persistence_health
from app.services import audit_trail_service


def _prepare_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    manual_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "audit_trail").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "submission_history").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "locks").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_OBSERVABILITY_ENABLED", "1")
    monkeypatch.setenv("LMCP_DEPLOYMENT_HARDENING_ENABLED", "1")

    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    reset_test_metrics()
    persistence_db._INITIALIZED = False
    persistence_db._INITIALIZED_PATH = None

    monkeypatch.setattr(workflow_state_engine, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(workflow_state_engine, "MANUAL_PRODUCTION_DIR", manual_dir)
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_EVENT_LOG_FILE", manual_dir / "workflow_events.jsonl")
    monkeypatch.setattr(workflow_state_engine, "WORKFLOW_STATE_LOG_FILE", manual_dir / "workflow_state.jsonl")

    monkeypatch.setattr(audit_trail_service, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(audit_trail_service, "AUDIT_DIR", runtime_dir / "audit_trail")
    monkeypatch.setattr(audit_trail_service, "AUDIT_FILE", runtime_dir / "audit_trail" / "audit_events.json")
    audit_trail_service.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    async def _noop_publish_dashboard_event(**_: object) -> None:
        return None

    monkeypatch.setattr(audit_trail_service, "publish_dashboard_event", _noop_publish_dashboard_event)
    return runtime_dir


def _append_jsonl_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _count_rows(db_path: Path, table: str) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0] if row else 0)
    finally:
        connection.close()


def _stale_timestamp(minutes: int = 360) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _create_job(job_type: QueueJobType, tender_id: str = "T-QUEUE", max_attempts: int = 3) -> dict[str, object]:
    return queue_manager.enqueue_job(
        tender_id=tender_id,
        job_type=job_type,
        actor="tester",
        operator="tester",
        workflow_stage=WorkflowStage.DISCOVERED.value,
        payload={"tender_id": tender_id},
        max_attempts=max_attempts,
    )


def test_enqueue_start_complete_flow(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)

    job = _create_job(QueueJobType.RFQ_EXTRACTION, tender_id="T-100")
    started = queue_manager.start_job(str(job["job_id"]), actor="operator", operator="operator")
    completed = queue_manager.complete_job(str(job["job_id"]), actor="operator", operator="operator")

    assert started["status"] == QueueJobStatus.RUNNING.value
    assert completed["status"] == QueueJobStatus.COMPLETED.value
    assert queue_manager.get_jobs_by_status(status=QueueJobStatus.COMPLETED, job_id=str(job["job_id"]))


def test_failed_job_handling(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    job = _create_job(QueueJobType.PRICING, tender_id="T-101")

    failed = queue_manager.fail_job(str(job["job_id"]), reason="temporary timeout", actor="operator", operator="operator")

    assert failed["status"] == QueueJobStatus.FAILED.value
    assert queue_manager.get_jobs_by_status(status=QueueJobStatus.FAILED, job_id=str(job["job_id"]))
    assert get_persistence_health()["write_successes"] >= 1
    assert (runtime_dir / "manual_production" / "queue_history.jsonl").exists()


@pytest.mark.parametrize(
    "job_type",
    [
        QueueJobType.APPROVAL_TRACKING,
        QueueJobType.SUBMISSION_REVIEW,
        QueueJobType.PROOF_CAPTURE,
    ],
)
def test_retry_policy_enforcement_for_governed_jobs(monkeypatch, tmp_path: Path, job_type: QueueJobType) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = _create_job(job_type, tender_id=f"T-{job_type.value}")
    queue_manager.fail_job(str(job["job_id"]), reason="temporary timeout", actor="operator", operator="operator")

    current = queue_manager.get_jobs_by_status(job_id=str(job["job_id"]))[0]
    assert retry_policy.should_retry(current) is False
    with pytest.raises(ValueError):
        queue_manager.retry_job(str(job["job_id"]), reason="retry", actor="operator", operator="operator")


def test_no_infinite_retries(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = _create_job(QueueJobType.PRICING, tender_id="T-102", max_attempts=1)
    queue_manager.fail_job(str(job["job_id"]), reason="temporary timeout", actor="operator", operator="operator")

    retry = queue_manager.retry_job(str(job["job_id"]), reason="retry once", actor="operator", operator="operator")
    assert retry["status"] == QueueJobStatus.RETRY_PENDING.value
    with pytest.raises(ValueError):
        queue_manager.retry_job(str(job["job_id"]), reason="retry twice", actor="operator", operator="operator")


def test_blocked_job_handling(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = _create_job(QueueJobType.WORKFLOW_RECOVERY, tender_id="T-103")

    blocked = operator_recovery_actions.mark_job_blocked(str(job["job_id"]), actor="operator", operator="operator", reason="manual hold")

    assert blocked["status"] == QueueJobStatus.BLOCKED.value
    assert queue_manager.get_jobs_by_status(status=QueueJobStatus.BLOCKED, job_id=str(job["job_id"]))
    assert queue_monitor.get_queue_summary()["blocked_jobs"] >= 1


def test_queue_monitor_summary_and_stalled_detection(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = _create_job(QueueJobType.INTEGRITY_CHECK, tender_id="T-104")
    stale = dict(job)
    stale["updated_at"] = _stale_timestamp()
    monkeypatch.setattr("app.orchestration.queue_monitor.get_jobs_by_status", lambda limit=500: [stale])

    summary = queue_monitor.get_queue_summary(limit=50)
    stalled = queue_monitor.find_stalled_jobs(limit=50, stalled_after_minutes=1)

    assert summary["total_jobs"] >= 1
    assert stalled["count"] >= 1
    assert stalled["items"][0]["job_id"] == job["job_id"]


def test_workflow_recovery_detection_and_report(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    manual_dir = runtime_dir / "manual_production"
    tender_id = "T-105"
    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "tester", "discover")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EXTRACTED, WorkflowStage.EVALUATED, "tester", "evaluate")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.EVALUATED, WorkflowStage.PRICED, "tester", "price")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.PRICED, WorkflowStage.QUOTE_GENERATED, "tester", "quote")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.QUOTE_GENERATED, WorkflowStage.APPROVAL_REQUIRED, "tester", "approval")
    workflow_state_engine.record_transition(tender_id, WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.APPROVED, "tester", "approved")

    stale_state = workflow_state_engine.get_transition_history(tender_id)["items"][-1]
    stale_state = dict(stale_state)
    stale_state["updated_at"] = _stale_timestamp()
    stale_state["created_at"] = datetime.now(timezone.utc).isoformat()
    _append_jsonl_record(manual_dir / "workflow_state.jsonl", stale_state)

    def _raise_connection(*_: object, **__: object) -> object:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(persistence_db, "get_connection", _raise_connection)
    candidates = workflow_recovery.scan_for_recovery_candidates(stuck_after_minutes=1, limit=50)
    report = workflow_recovery.generate_recovery_report(limit=50)
    recovered = workflow_recovery.recover_workflow(tender_id, actor="operator", operator="operator", reason="resume review")

    assert any(item["tender_id"] == tender_id for item in candidates["recovery_candidates"])
    assert report["recovery_candidates"]
    assert recovered["stage"] == WorkflowStage.APPROVED.value
    assert "persistence_mismatch" in candidates
    assert "orphaned_workflows" in candidates


def test_operator_recovery_actions_emit_audit_events(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    tender_id = "T-106"
    job = _create_job(QueueJobType.PRICING, tender_id=tender_id)
    queue_manager.fail_job(str(job["job_id"]), reason="temporary timeout", actor="operator", operator="operator")

    result = operator_recovery_actions.retry_failed_job(str(job["job_id"]), actor="operator", operator="operator", reason="retry")

    assert result["status"] in {QueueJobStatus.RETRY_PENDING.value, QueueJobStatus.FAILED.value}
    audit_file = runtime_dir / "audit_trail" / "audit_events.json"
    events = json.loads(audit_file.read_text(encoding="utf-8"))
    assert any(item.get("event_type") == "operator_retry_failed_job" for item in events)
    assert job_history.get_job_history(str(job["job_id"]))


def test_queue_history_persistence(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = _prepare_runtime(monkeypatch, tmp_path)
    db_path = runtime_dir / "manual_production" / "lmcp_operations.db"
    job = _create_job(QueueJobType.RFQ_EXTRACTION, tender_id="T-107")
    queue_manager.start_job(str(job["job_id"]), actor="operator", operator="operator")
    queue_manager.complete_job(str(job["job_id"]), actor="operator", operator="operator")

    history_file = runtime_dir / "manual_production" / "queue_history.jsonl"
    assert history_file.exists()
    assert _count_rows(db_path, "queue_history_records") >= 3
    assert _count_rows(db_path, "queue_job_records") >= 3


def test_dashboard_integration_reflects_queue_state(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = _create_job(QueueJobType.PRICING, tender_id="T-108")
    queue_manager.fail_job(str(job["job_id"]), reason="temporary timeout", actor="operator", operator="operator")
    operator_recovery_actions.mark_job_blocked(str(job["job_id"]), actor="operator", operator="operator", reason="manual hold")

    summary = dashboard_service.get_dashboard_summary(limit=50)
    queue_summary = workflow_queue_service.get_queue_overview(limit=50)
    workflow_summary = get_workflow_summary(limit=50)

    assert summary["queue_summary"]["blocked_jobs"] >= 1
    assert queue_summary["summary"]["blocked_jobs"] >= 1
    assert workflow_summary["queue_summary"]["blocked_jobs"] >= 1


def test_workflow_state_recovery_helpers_remain_read_only(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    tender_id = "T-109"
    workflow_state_engine.record_transition(tender_id, WorkflowStage.DISCOVERED, WorkflowStage.EXTRACTED, "tester", "discover")

    history = workflow_state_engine.get_transition_history(tender_id)

    assert history["status"] == "ok"
    assert history["tender_id"] == tender_id
    assert history["items"]


def test_no_autonomous_final_submission_jobs_created() -> None:
    assert "final_submission" not in {item.value for item in QueueJobType}


def test_approval_review_proof_jobs_remain_governed(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    governed_types = [
        QueueJobType.APPROVAL_TRACKING,
        QueueJobType.SUBMISSION_REVIEW,
        QueueJobType.PROOF_CAPTURE,
    ]
    for index, job_type in enumerate(governed_types, start=1):
        job = _create_job(job_type, tender_id=f"T-11{index}")
        queue_manager.fail_job(str(job["job_id"]), reason="temporary timeout", actor="operator", operator="operator")
        assert retry_policy.should_retry(queue_manager.get_jobs_by_status(job_id=str(job["job_id"]))[0]) is False


def test_queue_health_reflects_persistence_status(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    health = queue_monitor.get_queue_health(limit=20)

    assert health["status"] in {"healthy", "degraded"}
    assert get_persistence_health()["status"] in {"healthy", "degraded"}
