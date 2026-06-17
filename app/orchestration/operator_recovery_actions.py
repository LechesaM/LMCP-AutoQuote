from __future__ import annotations

import asyncio
from typing import Any, Dict

from .queue_manager import block_job, retry_job
from app.services import audit_trail_service


def mark_job_blocked(job_id: str, actor: str, operator: str, reason: str) -> Dict[str, Any]:
    return block_job(job_id, reason, actor, operator)


def retry_failed_job(job_id: str, actor: str, operator: str, reason: str) -> Dict[str, Any]:
    payload = {"job_id": job_id, "actor": actor, "operator": operator, "reason": reason}
    try:
        asyncio.run(
            audit_trail_service.record_audit_event(
                event_type="operator_retry_failed_job",
                source="operator-recovery",
                message=reason,
                payload=payload,
            )
        )
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            audit_trail_service.record_audit_event(
                event_type="operator_retry_failed_job",
                source="operator-recovery",
                message=reason,
                payload=payload,
            )
        )
    try:
        return retry_job(job_id, reason, actor, operator)
    except Exception:
        return {"status": "failed", "event_type": "operator_retry_failed_job"}
