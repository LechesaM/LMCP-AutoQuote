from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.go_live_guard_service import (
    create_submission_lock,
    evaluate_pipeline_guard,
    is_rfq_rejected,
    is_source_paused,
)

RUNTIME_DIR = Path("runtime")
ENFORCEMENT_DIR = RUNTIME_DIR / "pipeline_enforcement"
ENFORCEMENT_EVENTS_FILE = ENFORCEMENT_DIR / "enforcement_events.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_events() -> list[Dict[str, Any]]:
    if not ENFORCEMENT_EVENTS_FILE.exists():
        return []
    try:
        data = json.loads(ENFORCEMENT_EVENTS_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_events(items: list[Dict[str, Any]]) -> None:
    ENFORCEMENT_EVENTS_FILE.write_text(json.dumps(items[-5000:], indent=2, default=str))


async def record_enforcement_event(
    stage: str,
    status: str,
    payload: Dict[str, Any],
    guard_result: Optional[Dict[str, Any]] = None,
    message: str = "",
) -> Dict[str, Any]:
    item = {
        "stage": stage,
        "status": status,
        "message": message,
        "buyer_rfq_number": payload.get("buyer_rfq_number") or payload.get("rfq_number") or "",
        "quote_number": payload.get("quote_number") or "",
        "source_name": payload.get("source_name") or payload.get("source") or "",
        "guard_result": guard_result or {},
        "payload": payload,
        "created_at": _now_iso(),
    }

    events = _load_events()
    events.append(item)
    _save_events(events)

    try:
        from app.services.websocket_broker import publish_dashboard_event
        await publish_dashboard_event(
            event_type="pipeline_enforcement_event",
            payload=item,
            source="pipeline-enforcement",
        )
    except Exception:
        pass

    try:
        from app.services.audit_trail_service import record_audit_event
        await record_audit_event(
            event_type="pipeline_enforcement_blocked" if status == "blocked" else "pipeline_enforcement_allowed",
            source="pipeline-enforcement",
            severity="warning" if status == "blocked" else "success",
            title=f"Pipeline enforcement {status}",
            message=message,
            buyer_rfq_number=item.get("buyer_rfq_number") or "",
            quote_number=item.get("quote_number") or "",
            payload=item,
        )
    except Exception:
        pass

    return item


async def enforce_before_quote(payload: Dict[str, Any]) -> Dict[str, Any]:
    guard = evaluate_pipeline_guard(payload)
    allowed = bool(guard.get("allowed"))
    message = "Quote generation allowed by go-live guards." if allowed else "Quote generation blocked by go-live guards."

    await record_enforcement_event(
        stage="before_quote",
        status="allowed" if allowed else "blocked",
        payload=payload,
        guard_result=guard,
        message=message,
    )

    return {"status": "ok", "stage": "before_quote", "allowed": allowed, "message": message, "guard": guard}


async def enforce_before_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    guard = evaluate_pipeline_guard(payload)

    try:
        from app.services.sbd_completion_engine import evaluate_sbd_completion
        sbd = evaluate_sbd_completion(payload)
    except Exception as exc:
        sbd = {
            "status": "error",
            "sbd_ready": False,
            "message": f"SBD completion engine unavailable: {exc}",
            "missing_fields": ["sbd_completion_engine_unavailable"],
        }

    blockers = list(guard.get("blockers") or [])

    if not bool(sbd.get("sbd_ready")):
        missing = sbd.get("missing_fields") or []
        blockers.append(
            "SBD/buyer forms are incomplete. Missing: "
            + (", ".join(missing[:12]) if missing else "unknown fields")
        )

    allowed = bool(guard.get("allowed")) and bool(sbd.get("sbd_ready"))

    combined_guard = {
        **guard,
        "allowed": allowed,
        "blockers": blockers,
        "sbd": sbd,
    }

    message = "Submission allowed by go-live and SBD guards." if allowed else "Submission blocked by go-live/SBD guards."

    await record_enforcement_event(
        stage="before_submission",
        status="allowed" if allowed else "blocked",
        payload=payload,
        guard_result=combined_guard,
        message=message,
    )

    return {
        "status": "ok",
        "stage": "before_submission",
        "allowed": allowed,
        "message": message,
        "guard": combined_guard,
        "sbd": sbd,
    }


async def enforce_before_harvest_source(source: Dict[str, Any]) -> Dict[str, Any]:
    source_name = source.get("source_name") or source.get("name") or source.get("source") or ""
    paused = is_source_paused(str(source_name))

    result = {
        "status": "ok",
        "stage": "before_harvest_source",
        "allowed": not paused,
        "source_name": source_name,
        "message": "Source harvesting allowed." if not paused else "Source harvesting blocked because source is paused.",
        "source": source,
        "checked_at": _now_iso(),
    }

    await record_enforcement_event(
        stage="before_harvest_source",
        status="allowed" if result["allowed"] else "blocked",
        payload={"source_name": source_name, **source},
        guard_result=result,
        message=result["message"],
    )

    return result


async def enforce_before_rfq_processing(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = payload.get("buyer_rfq_number") or payload.get("rfq_number") or payload.get("tender_number") or ""
    rejected = is_rfq_rejected(str(buyer_rfq_number))

    result = {
        "status": "ok",
        "stage": "before_rfq_processing",
        "allowed": not rejected,
        "buyer_rfq_number": buyer_rfq_number,
        "message": "RFQ processing allowed." if not rejected else "RFQ processing blocked because RFQ is rejected.",
        "checked_at": _now_iso(),
    }

    await record_enforcement_event(
        stage="before_rfq_processing",
        status="allowed" if result["allowed"] else "blocked",
        payload=payload,
        guard_result=result,
        message=result["message"],
    )

    return result


async def mark_submission_completed(payload: Dict[str, Any]) -> Dict[str, Any]:
    buyer_rfq_number = payload.get("buyer_rfq_number") or payload.get("rfq_number") or payload.get("tender_number") or ""
    quote_number = payload.get("quote_number") or ""

    lock = create_submission_lock(
        buyer_rfq_number=buyer_rfq_number,
        quote_number=quote_number,
        reason=payload.get("reason") or "submission_completed",
        metadata=payload,
    )

    event = await record_enforcement_event(
        stage="after_submission",
        status="locked",
        payload=payload,
        guard_result={"submission_lock": lock},
        message="Submission completed and duplicate lock created.",
    )

    return {"status": "ok", "stage": "after_submission", "message": "Submission lock created.", "lock": lock, "event": event}


def get_enforcement_summary(limit: int = 100) -> Dict[str, Any]:
    events = _load_events()

    def count(status: str) -> int:
        return len([x for x in events if x.get("status") == status])

    def count_stage(stage: str) -> int:
        return len([x for x in events if x.get("stage") == stage])

    return {
        "status": "ok",
        "summary": {
            "total_events": len(events),
            "allowed": count("allowed"),
            "blocked": count("blocked"),
            "locked": count("locked"),
            "before_quote": count_stage("before_quote"),
            "before_submission": count_stage("before_submission"),
            "before_harvest_source": count_stage("before_harvest_source"),
            "before_rfq_processing": count_stage("before_rfq_processing"),
            "after_submission": count_stage("after_submission"),
        },
        "recent_events": list(reversed(events[-limit:])),
        "history_file": str(ENFORCEMENT_EVENTS_FILE),
        "updated_at": _now_iso(),
    }
