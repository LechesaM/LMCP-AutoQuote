from __future__ import annotations

from typing import Any, Dict, Optional

from app.core import workflow_state_engine
from app.orchestration.job_history import append_history_event
from app.orchestration.queue_manager import archive_job, block_job, retry_job
from app.services.audit_trail_service import record_audit_event


async def _audit(
    *,
    event_type: str,
    job_id: str,
    actor: str,
    message: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await record_audit_event(
        event_type=event_type,
        source="queue-orchestration",
        severity="info",
        title=event_type.replace("_", " ").title(),
        message=message,
        buyer_rfq_number=str((payload or {}).get("tender_id") or ""),
        payload={"job_id": job_id, "actor": actor, "payload": payload or {}},
    )


def retry_failed_job(job_id: str, actor: str = "", operator: str = "", reason: str = "") -> Dict[str, Any]:
    result = retry_job(job_id, reason=reason, actor=actor, operator=operator)
    append_history_event("operator_retry", {"job_id": job_id, "actor": actor, "operator": operator, "reason": reason})
    try:
        import asyncio

        asyncio.run(_audit(event_type="operator_retry_failed_job", job_id=job_id, actor=actor, message=reason, payload=result))
    except Exception:
        pass
    return result


def archive_failed_job(job_id: str, actor: str = "", operator: str = "", reason: str = "") -> Dict[str, Any]:
    result = archive_job(job_id, actor=actor, operator=operator, reason=reason)
    append_history_event("operator_archive", {"job_id": job_id, "actor": actor, "operator": operator, "reason": reason})
    try:
        import asyncio

        asyncio.run(_audit(event_type="operator_archive_failed_job", job_id=job_id, actor=actor, message=reason, payload=result))
    except Exception:
        pass
    return result


def mark_job_blocked(job_id: str, actor: str = "", operator: str = "", reason: str = "") -> Dict[str, Any]:
    result = block_job(job_id, reason=reason, actor=actor, operator=operator)
    append_history_event("operator_blocked", {"job_id": job_id, "actor": actor, "operator": operator, "reason": reason})
    try:
        import asyncio

        asyncio.run(
            _audit(event_type="operator_mark_job_blocked", job_id=job_id, actor=actor, message=reason, payload=result)
        )
    except Exception:
        pass
    return result


def acknowledge_queue_warning(job_id: str, actor: str = "", operator: str = "", warning: str = "") -> Dict[str, Any]:
    append_history_event("operator_warning_ack", {"job_id": job_id, "actor": actor, "operator": operator, "warning": warning})
    try:
        import asyncio

        asyncio.run(_audit(event_type="operator_ack_queue_warning", job_id=job_id, actor=actor, message=warning, payload={"job_id": job_id}))
    except Exception:
        pass
    return {"status": "ok", "job_id": job_id, "warning": warning, "operator": operator}
