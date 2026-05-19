from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.operator_ops.operator_action_models import OperatorAssignmentRecord, new_operator_id
from app.operator_ops.operator_audit_timeline import record_timeline_event
from app.operator_ops.operator_capacity_service import TEAM_SIZE, PER_OPERATOR_DAILY_CAPACITY, TOTAL_DAILY_CAPACITY


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _assignment_path() -> Path:
    return get_runtime_paths().manual_production_file("operator_assignments.jsonl")


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _assignment_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _read() -> List[Dict[str, Any]]:
    path = _assignment_path()
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


def _due_at() -> str:
    return (_now() + timedelta(hours=8)).isoformat()


def recommend_operator_assignments(limit: int = 100) -> Dict[str, Any]:
    from app.dashboard.workflow_queue_service import get_pending_approval_queue, get_proof_capture_queue, get_review_ready_queue

    current = _read()
    assigned_ids = {str(item.get("tender_id")) for item in current}
    candidates = []
    for row in get_review_ready_queue(limit=limit) + get_pending_approval_queue(limit=limit) + get_proof_capture_queue(limit=limit):
        tender_id = str(row.get("tender_id") or row.get("id") or "")
        if not tender_id or tender_id in assigned_ids:
            continue
        candidates.append(
            {
                "tender_id": tender_id,
                "title": str(row.get("title") or "Unknown"),
                "recommendation": "manual",
                "priority": 100 if str(row.get("stage") or "") == "approved" else 75,
                "workflow_stage": str(row.get("stage") or row.get("workflow_stage") or "unknown"),
                "owner": "",
                "reason": "manual operator attention required",
                "due_at": _due_at(),
            }
        )
    candidates.sort(key=lambda item: (-int(item["priority"]), str(item["tender_id"])))
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if candidates else "fallback",
        "recommended": candidates[: max(1, int(limit or 100))],
        "capacity": {
            "team_size": TEAM_SIZE,
            "per_operator_daily_capacity": PER_OPERATOR_DAILY_CAPACITY,
            "total_daily_capacity": TOTAL_DAILY_CAPACITY,
        },
    }


def create_assignment(*, operator_id: str, tender_id: str, priority: int = 50, recommendation: str = "manual", source: str = "manual", details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    record = OperatorAssignmentRecord(
        assignment_id=new_operator_id("assignment"),
        operator_id=operator_id,
        tender_id=tender_id,
        status="assigned",
        priority=int(priority),
        due_at=_now() + timedelta(hours=8),
        workload=len(_read()) + 1,
        recommendation=recommendation,
        source=source,
        details=details or {},
    ).to_jsonable_dict()
    _append(record)
    record_timeline_event(
        event_type="operator_assignment_created",
        operator_id=operator_id,
        tender_id=tender_id,
        title="Operator assignment created",
        severity="info",
        details=record,
    )
    return record


def get_operator_assignments(limit: int = 100) -> Dict[str, Any]:
    records = _read()
    assignments = records[-max(1, int(limit or 100)) :]
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if assignments else "fallback",
        "assignments": assignments,
        "summary": {
            "total_assignments": len(records),
            "active_assignments": len(assignments),
            "operators": TEAM_SIZE,
            "capacity": TOTAL_DAILY_CAPACITY,
        },
        "recommendations": recommend_operator_assignments(limit=limit).get("recommended", []),
    }
