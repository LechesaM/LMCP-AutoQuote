from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.core.runtime_paths import get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.pilot.pilot_mode import PilotMode, get_pilot_mode
from app.pilot.pilot_metrics import increment_pilot_metric
from app.persistence.repositories import PilotRunRepository


class PilotRunRecord(StrictBaseModel):
    tender_id: str = ""
    workflow_stage: str = ""
    pilot_mode: str = ""
    operator: str = ""
    actor: str = ""
    outcome: str = ""
    status: str = ""
    approval_confirmed: bool = False
    review_confirmed: bool = False
    proof_confirmed: bool = False
    workflow_skip: bool = False
    operator_override: bool = False
    warnings: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    recovery_events: List[str] = Field(default_factory=list)
    manual_intervention_required: bool = False
    final_submission_attempted: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


def _log_path() -> Path:
    return get_runtime_paths().manual_production_file("pilot_runs.jsonl")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(payload)
    except Exception:
        return []
    return items


def _write_jsonl(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def record_pilot_run(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = PilotRunRecord.validate_payload(record).to_jsonable_dict()
    pilot_mode = get_pilot_mode()
    if pilot_mode is PilotMode.DISABLED:
        raise ValueError("pilot mode is disabled")
    if not str(payload.get("operator") or payload.get("actor") or "").strip():
        raise ValueError("operator is required")
    if payload.get("final_submission_attempted") or payload.get("workflow_skip"):
        raise ValueError("autonomous execution is prohibited")
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    payload.setdefault("updated_at", payload["created_at"])
    _write_jsonl(_log_path(), payload)
    try:
        PilotRunRepository(jsonl_path=_log_path()).append_run(payload)
    except Exception:
        increment_pilot_metric("persistence_failures")
    increment_pilot_metric("rfqs_processed")
    terminal_state = str(payload.get("outcome") or payload.get("status") or "").lower()
    if terminal_state == "refused":
        increment_pilot_metric("rfqs_refused")
        increment_pilot_metric("blocked_workflows")
    if terminal_state in {"passed", "successful", "completed", "recorded", "approved"}:
        increment_pilot_metric("successful_workflow_completions")
    if payload.get("workflow_stage") in {"quote_generated", "approval_required", "approved", "review_ready", "proof_recorded"} and terminal_state in {
        "passed",
        "successful",
        "completed",
        "recorded",
        "approved",
    }:
        increment_pilot_metric("quote_generation_successes")
    if terminal_state in {"failed", "blocked"}:
        increment_pilot_metric("workflow_failures")
    if payload.get("manual_intervention_required"):
        increment_pilot_metric("manual_interventions")
    if payload.get("recovery_events"):
        increment_pilot_metric("recovery_events", len(payload.get("recovery_events") or []))
    if payload.get("warnings"):
        increment_pilot_metric("manual_interventions")
    if payload.get("operator_override"):
        increment_pilot_metric("operator_overrides")
    return payload


def get_pilot_summary(limit: int = 100) -> Dict[str, Any]:
    items = _read_jsonl(_log_path())[-max(1, int(limit or 100)) :]
    by_status: Dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or item.get("outcome") or "")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "status": "ok",
        "total_runs": len(items),
        "by_status": by_status,
        "runs": items,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_pilot_failures(limit: int = 100) -> List[Dict[str, Any]]:
    return [item for item in _read_jsonl(_log_path()) if str(item.get("outcome") or item.get("status") or "").lower() in {"failed", "refused"}][-max(1, int(limit or 100)) :]


def get_pilot_successes(limit: int = 100) -> List[Dict[str, Any]]:
    return [item for item in _read_jsonl(_log_path()) if str(item.get("outcome") or item.get("status") or "").lower() in {"passed", "successful", "completed"}][-max(1, int(limit or 100)) :]


def get_pilot_runs(limit: int = 100) -> List[Dict[str, Any]]:
    return _read_jsonl(_log_path())[-max(1, int(limit or 100)) :]
