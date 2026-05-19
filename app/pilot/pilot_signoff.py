from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.core.runtime_paths import get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.pilot.pilot_guardrails import assert_pilot_guardrails
from app.pilot.pilot_metrics import increment_pilot_metric
from app.persistence.repositories import PilotSignoffRepository


class PilotSignoffRecord(StrictBaseModel):
    tender_id: str = ""
    workflow_stage: str = ""
    signoff_type: str = ""
    signoff_status: str = ""
    actor: str = ""
    operator: str = ""
    note: str = ""
    manual_submission_confirmed: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


def _log_path() -> Path:
    return get_runtime_paths().manual_production_file("pilot_signoffs.jsonl")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
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


def _write_jsonl(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def record_signoff(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = PilotSignoffRecord.validate_payload(record).to_jsonable_dict()
    validation = validate_signoff_requirements(payload)
    if validation["blockers"]:
        raise ValueError("; ".join(validation["blockers"]))
    assert_pilot_guardrails(
        {
            "operator": payload.get("operator") or payload.get("actor"),
            "workflow_stage": payload.get("workflow_stage"),
            "approval_confirmed": payload.get("signoff_type") == "approval",
            "review_confirmed": payload.get("signoff_type") == "review",
            "proof_confirmed": payload.get("signoff_type") == "proof",
            "final_submission_attempted": payload.get("signoff_type") == "final_submission",
        }
    )
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    payload.setdefault("updated_at", payload["created_at"])
    _write_jsonl(_log_path(), payload)
    try:
        PilotSignoffRepository(jsonl_path=_log_path()).append_signoff(payload)
    except Exception:
        increment_pilot_metric("persistence_failures")
    if payload.get("signoff_type"):
        increment_pilot_metric("manual_interventions")
    if payload.get("signoff_type") in {"approval", "review", "proof", "go_live"}:
        increment_pilot_metric("operator_overrides")
    return payload


def get_signoff_history(tender_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return [item for item in _read_jsonl(_log_path()) if str(item.get("tender_id") or "") == str(tender_id)][-max(1, int(limit or 100)) :]


def validate_signoff_requirements(record: Dict[str, Any]) -> Dict[str, Any]:
    blockers = []
    if not str(record.get("operator") or record.get("actor") or "").strip():
        blockers.append("operator is required")
    if not str(record.get("signoff_type") or "").strip():
        blockers.append("signoff type is required")
    if str(record.get("signoff_type") or "") == "final_submission":
        blockers.append("final submission sign-off is not permitted")
    if record.get("workflow_stage") == "proof_recorded" and str(record.get("signoff_type") or "") != "proof":
        blockers.append("proof sign-off required for proof_recorded")
    return {
        "status": "ok" if not blockers else "blocked",
        "blockers": blockers,
        "record": record,
    }


def get_pilot_signoffs(limit: int = 100) -> List[Dict[str, Any]]:
    return _read_jsonl(_log_path())[-max(1, int(limit or 100)) :]
