from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional

from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowEvent, WorkflowStage, WorkflowState

RUNTIME_DIR = get_runtime_paths().runtime_root
MANUAL_PRODUCTION_DIR = get_runtime_paths().manual_production_dir
MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOW_EVENT_LOG_FILE = get_runtime_paths().manual_production_file("workflow_events.jsonl")
WORKFLOW_STATE_LOG_FILE = get_runtime_paths().manual_production_file("workflow_state.jsonl")

_LOCK = Lock()

_ACTIVE_STAGES = {
    WorkflowStage.DISCOVERED,
    WorkflowStage.EXTRACTED,
    WorkflowStage.EVALUATED,
    WorkflowStage.PRICED,
    WorkflowStage.QUOTE_GENERATED,
    WorkflowStage.APPROVAL_REQUIRED,
    WorkflowStage.APPROVED,
    WorkflowStage.REVIEW_READY,
    WorkflowStage.PROOF_RECORDED,
}

_ALLOWED_TRANSITIONS = {
    WorkflowStage.DISCOVERED: {WorkflowStage.EXTRACTED, WorkflowStage.REFUSED},
    WorkflowStage.EXTRACTED: {WorkflowStage.EVALUATED, WorkflowStage.REFUSED},
    WorkflowStage.EVALUATED: {WorkflowStage.PRICED, WorkflowStage.REFUSED},
    WorkflowStage.PRICED: {WorkflowStage.QUOTE_GENERATED, WorkflowStage.REFUSED},
    WorkflowStage.QUOTE_GENERATED: {WorkflowStage.APPROVAL_REQUIRED, WorkflowStage.REFUSED},
    WorkflowStage.APPROVAL_REQUIRED: {WorkflowStage.APPROVED, WorkflowStage.REFUSED},
    WorkflowStage.APPROVED: {WorkflowStage.REVIEW_READY, WorkflowStage.REFUSED},
    WorkflowStage.REVIEW_READY: {WorkflowStage.PROOF_RECORDED, WorkflowStage.REFUSED},
    WorkflowStage.PROOF_RECORDED: {WorkflowStage.ARCHIVED, WorkflowStage.REFUSED},
    WorkflowStage.REFUSED: {WorkflowStage.ARCHIVED},
    WorkflowStage.ARCHIVED: set(),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _coerce_stage(value: Any) -> WorkflowStage:
    if isinstance(value, WorkflowStage):
        return value
    return WorkflowStage(_clean(value))


def _safe_details(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _append_jsonl(path: Path, item: Dict[str, Any]) -> Dict[str, Any]:
    MANUAL_PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(item, ensure_ascii=False, default=str)
    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return item


def _latest_state_record(tender_id: str) -> Dict[str, Any]:
    for record in reversed(_read_jsonl(WORKFLOW_STATE_LOG_FILE)):
        if _clean(record.get("tender_id")) == _clean(tender_id):
            return record
    return {}


def _persist_transition(
    *,
    tender_id: str,
    from_stage: WorkflowStage,
    to_stage: WorkflowStage,
    actor: str,
    reason: str,
    details: Dict[str, Any],
) -> WorkflowState:
    transitioned_at = _now_iso()
    event = WorkflowEvent.validate_payload(
        {
            "tender_id": _clean(tender_id),
            "from_stage": from_stage,
            "to_stage": to_stage,
            "actor": _clean(actor),
            "reason": _clean(reason),
            "details": _safe_details(details),
            "transitioned_at": transitioned_at,
        }
    ).to_jsonable_dict()
    state_details = _safe_details(details)
    state_details.update(
        {
            "actor": _clean(actor),
            "reason": _clean(reason),
            "from_stage": from_stage.value,
            "to_stage": to_stage.value,
            "transitioned_at": transitioned_at,
        }
    )
    state = WorkflowState.validate_payload(
        {
            "tender_id": _clean(tender_id),
            "stage": to_stage,
            "updated_at": transitioned_at,
            "details": state_details,
        }
    ).to_jsonable_dict()

    _append_jsonl(WORKFLOW_EVENT_LOG_FILE, event)
    _append_jsonl(WORKFLOW_STATE_LOG_FILE, state)
    _emit_audit_event(tender_id=_clean(tender_id), from_stage=from_stage, to_stage=to_stage, actor=_clean(actor), reason=_clean(reason), details=state_details)
    return WorkflowState.validate_payload(state)


def _emit_audit_event(
    *,
    tender_id: str,
    from_stage: WorkflowStage,
    to_stage: WorkflowStage,
    actor: str,
    reason: str,
    details: Dict[str, Any],
) -> None:
    try:
        from app.services.audit_trail_service import record_audit_event

        async def _record() -> None:
            await record_audit_event(
                event_type="workflow_transition",
                source="workflow-state-engine",
                severity="info",
                title=f"Workflow transition {from_stage.value} -> {to_stage.value}",
                message=reason,
                buyer_rfq_number=tender_id,
                payload={
                    "tender_id": tender_id,
                    "from_stage": from_stage.value,
                    "to_stage": to_stage.value,
                    "actor": actor,
                    "reason": reason,
                    "details": details,
                },
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_record())
            return
        loop.create_task(_record())
    except Exception:
        return


def assert_can_transition(from_stage: Any, to_stage: Any) -> None:
    source = _coerce_stage(from_stage)
    target = _coerce_stage(to_stage)
    if source == target:
        raise ValueError(f"Transition {source.value} -> {target.value} is not allowed")
    allowed_targets = _ALLOWED_TRANSITIONS.get(source, set())
    if target not in allowed_targets:
        raise ValueError(f"Transition {source.value} -> {target.value} is not allowed")


def get_current_state(tender_id: str) -> WorkflowState:
    latest = _latest_state_record(tender_id)
    if latest:
        return WorkflowState.validate_payload(latest)
    return WorkflowState.validate_payload(
        {
            "tender_id": _clean(tender_id),
            "stage": WorkflowStage.DISCOVERED,
            "updated_at": _now_iso(),
            "details": {},
        }
    )


def record_transition(
    tender_id: str,
    from_stage: Any,
    to_stage: Any,
    actor: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    source = _coerce_stage(from_stage)
    target = _coerce_stage(to_stage)
    assert_can_transition(source, target)

    latest = _latest_state_record(tender_id)
    if latest:
        current_stage = _coerce_stage(latest.get("stage"))
        if current_stage != source:
            raise ValueError(
                f"Current workflow stage for tender {tender_id} is {current_stage.value}, not {source.value}"
            )
    elif source != WorkflowStage.DISCOVERED:
        raise ValueError(f"Cannot transition tender {tender_id} from {source.value} without a current state")

    return _persist_transition(
        tender_id=tender_id,
        from_stage=source,
        to_stage=target,
        actor=actor,
        reason=reason,
        details=_safe_details(details),
    )


def refuse_workflow(
    tender_id: str,
    actor: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    current = get_current_state(tender_id)
    if current.stage not in _ACTIVE_STAGES:
        raise ValueError(f"Cannot refuse workflow for tender {tender_id} from {current.stage.value}")
    return record_transition(
        tender_id=tender_id,
        from_stage=current.stage,
        to_stage=WorkflowStage.REFUSED,
        actor=actor,
        reason=reason,
        details=details,
    )


def archive_workflow(
    tender_id: str,
    actor: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    current = get_current_state(tender_id)
    return record_transition(
        tender_id=tender_id,
        from_stage=current.stage,
        to_stage=WorkflowStage.ARCHIVED,
        actor=actor,
        reason=reason,
        details=details,
    )


def list_recent_states(limit: int = 100) -> Dict[str, Any]:
    records = _read_jsonl(WORKFLOW_STATE_LOG_FILE)
    recent = list(reversed(records[-max(1, int(limit or 100)) :]))
    return {
        "status": "ok",
        "items": recent,
        "total": len(records),
        "log_file": str(WORKFLOW_STATE_LOG_FILE),
        "event_log_file": str(WORKFLOW_EVENT_LOG_FILE),
        "updated_at": _now_iso(),
    }
