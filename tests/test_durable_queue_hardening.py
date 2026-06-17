from __future__ import annotations

from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.orchestration.dead_letter_queue import archive_dlq_item, list_dlq, move_to_dlq, retry_from_dlq
from app.orchestration.durable_queue import acknowledge_job, dequeue_job, enqueue_job, fail_job, get_queue_depth, get_queue_health
from app.orchestration.queue_recovery_service import detect_queue_recovery_needs
from app.orchestration.queue_state_service import build_queue_restart_recovery_report, capture_queue_state, load_queue_state_snapshot
from app.orchestration.worker_supervision import detect_stale_workers, record_worker_heartbeat
from app.orchestration.job_models import QueueJobType


def _prepare_runtime(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")
    monkeypatch.setenv("LMCP_DEPLOYMENT_PROFILE", "local_dev")
    get_runtime_config.cache_clear()
    get_runtime_paths.cache_clear()


def test_local_durable_queue_enqueue_dequeue_ack(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = enqueue_job(
        tender_id="RFQ-1",
        job_type=QueueJobType.SUBMISSION_REVIEW,
        actor="tester",
        operator="op1",
        workflow_stage="review",
        idempotency_key="rfq-1-review",
    )
    dequeued = dequeue_job()
    assert dequeued["job_id"] == job["job_id"]
    completed = acknowledge_job(job["job_id"])
    assert completed["status"].lower() == "completed"


def test_queue_recovers_from_missing_jsonl_shadow(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = enqueue_job(
        tender_id="RFQ-RECOVER",
        job_type=QueueJobType.SUBMISSION_REVIEW,
        actor="tester",
        operator="op1",
        workflow_stage="review",
        idempotency_key="recover-shadow",
    )
    shadow = tmp_path / "runtime" / "manual_production" / "durable_queue.jsonl"
    if shadow.exists():
        shadow.unlink()

    depth = get_queue_depth()
    dequeued = dequeue_job()

    assert depth["counts"].get("queued", 0) >= 1
    assert dequeued["job_id"] == job["job_id"]


def test_queue_enqueue_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    first = enqueue_job(
        tender_id="RFQ-IDEMP",
        job_type=QueueJobType.PRICING,
        actor="tester",
        operator="op1",
        workflow_stage="pricing",
        payload={"rfq": "RFQ-IDEMP"},
        idempotency_key="pricing-rfq-idemp",
    )
    second = enqueue_job(
        tender_id="RFQ-IDEMP",
        job_type=QueueJobType.PRICING,
        actor="tester",
        operator="op1",
        workflow_stage="pricing",
        payload={"rfq": "RFQ-IDEMP"},
        idempotency_key="pricing-rfq-idemp",
    )
    assert second["job_id"] == first["job_id"]
    assert second["idempotent_replay"] is True


def test_fail_and_retry_job(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = enqueue_job(tender_id="RFQ-2", job_type=QueueJobType.INTEGRITY_CHECK, actor="tester", operator="op1", workflow_stage="review")
    failed = fail_job(job["job_id"], reason="test failure")
    assert failed["status"].lower() == "failed"
    health = get_queue_health()
    assert health["status"] in {"healthy", "degraded"}


def test_dlq_move_list_retry_archive(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    record = move_to_dlq({"job_id": "job-1", "tender_id": "RFQ-3", "job_type": "review", "payload": {}}, reason="test")
    listing = list_dlq()
    assert listing["count"] == 1
    retried = retry_from_dlq(record["dlq_id"])
    assert retried["retried"] is True
    archived = archive_dlq_item(record["dlq_id"])
    assert archived["archived"] is True


def test_no_infinite_retry_loops(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = enqueue_job(tender_id="RFQ-4", job_type=QueueJobType.INTEGRITY_CHECK, actor="tester", operator="op1", workflow_stage="review", max_attempts=1)
    fail_job(job["job_id"], reason="first failure")
    assert list_dlq()["count"] >= 1
    depth = get_queue_depth()
    assert depth["depth"] >= 0


def test_queue_recovery_detects_stuck_job(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr("app.orchestration.queue_recovery_service.get_queue_depth", lambda: {"depth": 2, "counts": {"running": 1, "retry_pending": 1, "queued": 0, "failed": 0}})
    monkeypatch.setattr("app.orchestration.queue_recovery_service.list_dlq", lambda: {"count": 1})
    monkeypatch.setattr("app.orchestration.queue_recovery_service.get_worker_supervision_report", lambda: {"stale_worker_count": 1})
    payload = detect_queue_recovery_needs()
    assert payload["status"] == "degraded"
    assert payload["blocked_operator_jobs"] >= 0


def test_queue_restart_snapshot_and_report(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    job = enqueue_job(
        tender_id="RFQ-RESTART",
        job_type=QueueJobType.QUOTE_GENERATION,
        actor="tester",
        operator="op1",
        workflow_stage="quote_generation",
        idempotency_key="restart-proof",
    )
    snapshot = capture_queue_state(limit=20)
    loaded = load_queue_state_snapshot()
    report = build_queue_restart_recovery_report(limit=20)

    assert snapshot["snapshot"]["jobs"]
    assert loaded["snapshot"]["jobs"]
    assert report["snapshot_path"].endswith("queue_state_snapshot.json")
    assert report["queued_jobs"] >= 0
    assert (tmp_path / "runtime" / "manual_production" / "queue_state_snapshot.json").exists()
    assert job["job_id"]


def test_worker_supervision_detects_stale_heartbeat(monkeypatch, tmp_path: Path) -> None:
    _prepare_runtime(monkeypatch, tmp_path)
    heartbeat = record_worker_heartbeat("worker-1")
    assert heartbeat["worker_id"] == "worker-1"
    monkeypatch.setattr(
        "app.orchestration.worker_supervision._read",
        lambda: [{"worker_id": "worker-1", "created_at": "2000-01-01T00:00:00+00:00", "status": "healthy"}],
    )
    stale = detect_stale_workers(stale_after_minutes=1)
    assert stale
