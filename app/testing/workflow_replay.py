from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.core.runtime_paths import get_runtime_paths
from app.core.workflow_state_engine import assert_can_transition
from app.domain.base import StrictBaseModel, utc_now
from app.domain.workflow import WorkflowStage
from app.persistence.repositories import WorkflowRepository


class WorkflowReplayResult(StrictBaseModel):
    tender_id: str = ""
    passed: bool = False
    invalid_transitions: List[str] = Field(default_factory=list)
    skipped_stages: List[str] = Field(default_factory=list)
    missing_audit_events: List[str] = Field(default_factory=list)
    persistence_mismatch: List[str] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: Any = None


def _workflow_repo() -> WorkflowRepository:
    paths = get_runtime_paths()
    return WorkflowRepository(jsonl_path=paths.manual_production_file("workflow_state.jsonl"))


def _read_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        records: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                records.append(item)
        return records
    except Exception:
        try:
            records: List[Dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
            return records
        except Exception:
            return []


def replay_workflow_history(tender_id: str) -> Dict[str, Any]:
    repo = _workflow_repo()
    history = repo.fetch_history(tender_id, limit=500)
    event_records = _read_records(get_runtime_paths().manual_production_file("workflow_events.jsonl"))
    audit_records = _read_records(get_runtime_paths().audit_trail_dir / "audit_events.json")
    tender_events = [item for item in event_records if str(item.get("tender_id") or "") == str(tender_id)]
    tender_audits = [
        item
        for item in audit_records
        if str(item.get("buyer_rfq_number") or item.get("payload", {}).get("tender_id") or "") == str(tender_id)
    ]
    invalid_transitions: List[str] = []
    skipped_stages: List[str] = []
    expected_stages = [
        WorkflowStage.EXTRACTED,
        WorkflowStage.EVALUATED,
        WorkflowStage.PRICED,
        WorkflowStage.QUOTE_GENERATED,
        WorkflowStage.APPROVAL_REQUIRED,
        WorkflowStage.APPROVED,
        WorkflowStage.REVIEW_READY,
        WorkflowStage.PROOF_RECORDED,
    ]
    seen_stages: List[WorkflowStage] = []
    for record in tender_events:
        try:
            from_stage = WorkflowStage(str(record.get("from_stage") or ""))
            to_stage = WorkflowStage(str(record.get("to_stage") or record.get("stage") or record.get("workflow_stage") or ""))
        except Exception as exc:
            invalid_transitions.append(f"malformed workflow event: {exc}")
            continue
        try:
            assert_can_transition(from_stage, to_stage)
        except Exception as exc:
            invalid_transitions.append(str(exc))
        seen_stages.append(to_stage)
    for stage in expected_stages:
        if stage not in seen_stages:
            skipped_stages.append(stage.value)
    missing_audit_events: List[str] = []
    for event in tender_events:
        stage = str(event.get("to_stage") or event.get("stage") or event.get("workflow_stage") or "")
        if not any(stage in json.dumps(audit, default=str) for audit in tender_audits):
            missing_audit_events.append(stage)
    persistence_mismatch: List[str] = []
    raw_state_records = [
        record
        for record in _read_records(get_runtime_paths().manual_production_file("workflow_state.jsonl"))
        if str(record.get("tender_id") or "") == str(tender_id)
    ]
    if len(raw_state_records) != len(history):
        persistence_mismatch.append("workflow history count mismatch")
    if raw_state_records and history:
        latest_raw = raw_state_records[-1]
        latest_history = history[-1]
        if str(latest_raw.get("stage") or latest_raw.get("workflow_stage") or "") != str(latest_history.get("stage") or ""):
            persistence_mismatch.append("latest workflow state mismatch")
    passed = not invalid_transitions and not skipped_stages and not missing_audit_events and not persistence_mismatch
    return WorkflowReplayResult(
        tender_id=tender_id,
        passed=passed,
        invalid_transitions=invalid_transitions,
        skipped_stages=skipped_stages,
        missing_audit_events=missing_audit_events,
        persistence_mismatch=persistence_mismatch,
        history=history,
        updated_at=utc_now(),
    ).to_jsonable_dict()
