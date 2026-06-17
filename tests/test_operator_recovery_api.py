from __future__ import annotations

from app.api.operator_actions_api import (
    operator_queue_recovery,
    operator_queue_recovery_acknowledge,
    operator_queue_recovery_archive,
    operator_queue_recovery_block,
    operator_queue_recovery_retry,
    router as operator_actions_router,
)


def test_operator_actions_router_exposes_recovery_paths() -> None:
    paths = {route.path for route in operator_actions_router.routes}
    assert {"/operator-actions/recovery", "/operator-actions/recovery/retry", "/operator-actions/recovery/archive", "/operator-actions/recovery/block", "/operator-actions/recovery/acknowledge"} <= paths


def test_operator_recovery_wrappers_return_expected_shapes(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.operator_actions_api.build_queue_recovery_response",
        lambda: {"status": "degraded", "queue_recovery": {"status": "degraded"}, "stalled_jobs": [], "blocked_jobs": 0},
    )
    monkeypatch.setattr(
        "app.api.operator_actions_api.retry_failed_job",
        lambda job_id, actor="", operator="", reason="": {"job_id": job_id, "status": "retry_pending"},
    )
    monkeypatch.setattr(
        "app.api.operator_actions_api.archive_failed_job",
        lambda job_id, actor="", operator="", reason="": {"job_id": job_id, "status": "archived"},
    )
    monkeypatch.setattr(
        "app.api.operator_actions_api.mark_job_blocked",
        lambda job_id, actor="", operator="", reason="": {"job_id": job_id, "status": "blocked"},
    )
    monkeypatch.setattr(
        "app.api.operator_actions_api.acknowledge_queue_warning",
        lambda job_id, actor="", operator="", warning="": {"job_id": job_id, "warning": warning},
    )

    recovery = operator_queue_recovery()
    retry = operator_queue_recovery_retry({"job_id": "JOB-1"})
    archive = operator_queue_recovery_archive({"job_id": "JOB-2"})
    block = operator_queue_recovery_block({"job_id": "JOB-3"})
    ack = operator_queue_recovery_acknowledge({"job_id": "JOB-4", "warning": "stalled"})

    assert recovery["status"] == "degraded"
    assert retry["item"]["status"] == "retry_pending"
    assert archive["item"]["status"] == "archived"
    assert block["item"]["status"] == "blocked"
    assert ack["item"]["warning"] == "stalled"
