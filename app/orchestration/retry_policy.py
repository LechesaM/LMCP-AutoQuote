from __future__ import annotations

from typing import Any, Dict

from .job_models import QueueJobType


_GOVERNED_JOB_TYPES = {
    QueueJobType.APPROVAL_TRACKING.value,
    QueueJobType.SUBMISSION_REVIEW.value,
    QueueJobType.PROOF_CAPTURE.value,
}


def should_retry(job: Dict[str, Any]) -> bool:
    job_type = str(job.get("job_type") or "")
    normalized_job_type = job_type.split(".")[-1].lower()
    if normalized_job_type in _GOVERNED_JOB_TYPES:
        return False
    return str(job.get("status")) in {"failed", "pending", "retry_pending", "running"}
