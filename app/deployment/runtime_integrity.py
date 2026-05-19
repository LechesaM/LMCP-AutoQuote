from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.core import workflow_state_engine
from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.domain.workflow import WorkflowStage
from app.persistence import db


class IntegrityIssue(StrictBaseModel):
    level: str = "warning"
    code: str = ""
    message: str = ""


class IntegrityReport(StrictBaseModel):
    status: str = "healthy"
    healthy: bool = True
    degraded: bool = False
    checked_at: Any = None
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_issues: List[Dict[str, Any]] = Field(default_factory=list)
    audit_issues: List[Dict[str, Any]] = Field(default_factory=list)
    db_integrity: Dict[str, Any] = Field(default_factory=dict)
    directory_consistency: Dict[str, Any] = Field(default_factory=dict)
    orphaned_workflows: List[str] = Field(default_factory=list)
    corrupted_states: List[str] = Field(default_factory=list)


def _issue(level: str, code: str, message: str) -> Dict[str, Any]:
    return IntegrityIssue(level=level, code=code, message=message).to_jsonable_dict()


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


def _audit_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
    except Exception:
        return []
    return []


def _stage(value: Any) -> Optional[WorkflowStage]:
    try:
        return WorkflowStage(str(value or ""))
    except Exception:
        return None


def run_integrity_checks(*, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    issues: List[Dict[str, Any]] = []
    workflow_issues: List[Dict[str, Any]] = []
    audit_issues: List[Dict[str, Any]] = []
    orphaned_workflows: List[str] = []
    corrupted_states: List[str] = []

    workflow_events = _read_jsonl(runtime_paths.manual_production_file("workflow_events.jsonl"))
    workflow_states = _read_jsonl(runtime_paths.manual_production_file("workflow_state.jsonl"))
    audit_events = _audit_records(runtime_paths.audit_trail_dir / "audit_events.json")

    allowed = getattr(workflow_state_engine, "_ALLOWED_TRANSITIONS", {})
    seen_events: Dict[str, List[Dict[str, Any]]] = {}
    seen_states: Dict[str, List[Dict[str, Any]]] = {}

    for event in workflow_events:
        tender_id = str(event.get("tender_id") or "")
        seen_events.setdefault(tender_id, []).append(event)
        from_stage = _stage(event.get("from_stage"))
        to_stage = _stage(event.get("to_stage"))
        if from_stage is None or to_stage is None:
            workflow_issues.append(_issue("fatal", "malformed_event", f"Malformed workflow event for {tender_id}"))
            continue
        if to_stage not in set(allowed.get(from_stage, set())):
            workflow_issues.append(
                _issue("fatal", "invalid_transition", f"Invalid transition {from_stage.value} -> {to_stage.value} for {tender_id}")
            )

    for state in workflow_states:
        tender_id = str(state.get("tender_id") or "")
        seen_states.setdefault(tender_id, []).append(state)
        stage = _stage(state.get("stage") or state.get("workflow_stage"))
        if stage is None:
            corrupted_states.append(tender_id or "unknown")
            workflow_issues.append(_issue("fatal", "corrupted_state", f"Corrupted workflow state for {tender_id}"))

    event_ids = {key for key in seen_events if key}
    state_ids = {key for key in seen_states if key}
    orphaned_workflows = sorted(state_ids - event_ids)

    audit_payload_text = json.dumps(audit_events, default=str)
    for event in workflow_events:
        stage = str(event.get("to_stage") or "")
        if stage and stage not in audit_payload_text:
            audit_issues.append(_issue("warning", "missing_audit_event", f"Missing audit evidence for stage {stage}"))

    db_integrity = db.database_integrity_check()
    directory_consistency = {
        "runtime_root_exists": runtime_paths.runtime_root.exists(),
        "manual_production_dir_exists": runtime_paths.manual_production_dir.exists(),
        "backups_dir_exists": runtime_paths.backups_dir.exists(),
        "health_dir_exists": runtime_paths.health_dir.exists(),
    }

    if not db_integrity.get("healthy", False):
        issues.append(_issue("fatal", "db_integrity_failed", "SQLite integrity check failed"))
    if workflow_issues:
        issues.extend(workflow_issues)
    if audit_issues:
        issues.extend(audit_issues)
    if orphaned_workflows:
        issues.append(_issue("warning", "orphaned_workflows", ", ".join(orphaned_workflows)))

    fatal = any(item.get("level") == "fatal" for item in issues)
    status = "unhealthy" if fatal else ("degraded" if issues else "healthy")
    return IntegrityReport(
        status=status,
        healthy=not fatal,
        degraded=bool(issues),
        checked_at=utc_now(),
        issues=issues,
        workflow_issues=workflow_issues,
        audit_issues=audit_issues,
        db_integrity=db_integrity,
        directory_consistency=directory_consistency,
        orphaned_workflows=orphaned_workflows,
        corrupted_states=corrupted_states,
    ).to_jsonable_dict()


def get_integrity_report(*, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    return run_integrity_checks(paths=paths)
