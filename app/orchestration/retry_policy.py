from __future__ import annotations

from typing import Any, Dict

from app.orchestration.job_models import QueueJob, QueueJobStatus, QueueJobType


_RETRYABLE_TEXT = {
    "temporary",
    "timeout",
    "unavailable",
    "network",
    "transient",
    "lock",
    "busy",
}


def max_retry_limit(job: QueueJob | Dict[str, Any] | None = None) -> int:
    if isinstance(job, dict):
        return int(job.get("max_attempts") or 3)
    if job is not None:
        return int(getattr(job, "max_attempts", 3) or 3)
    return 3


def classify_retryable_failure(failure: str, job: QueueJob | Dict[str, Any] | None = None) -> bool:
    text = str(failure or "").lower()
    if any(token in text for token in _RETRYABLE_TEXT):
        return True
    if job is not None:
        job_type = getattr(job, "job_type", None) if not isinstance(job, dict) else job.get("job_type")
        if str(job_type) in {QueueJobType.INTEGRITY_CHECK.value, QueueJobType.WORKFLOW_RECOVERY.value}:
            return True
    return False


def should_retry(job: QueueJob | Dict[str, Any]) -> bool:
    status = str(job.get("status") if isinstance(job, dict) else getattr(job, "status", "")).lower()
    if status in {QueueJobStatus.COMPLETED.value, QueueJobStatus.ARCHIVED.value, QueueJobStatus.BLOCKED.value}:
        return False
    job_type = str(job.get("job_type") if isinstance(job, dict) else getattr(job, "job_type", ""))
    if job_type in {
        QueueJobType.APPROVAL_TRACKING.value,
        QueueJobType.SUBMISSION_REVIEW.value,
        QueueJobType.PROOF_CAPTURE.value,
    }:
        return False
    attempt_count = int(job.get("attempt_count") if isinstance(job, dict) else getattr(job, "attempt_count", 0) or 0)
    return attempt_count < max_retry_limit(job)


def calculate_retry_delay(attempt_count: int) -> int:
    attempts = max(1, int(attempt_count or 1))
    return min(900, 5 * (2 ** (attempts - 1)))
