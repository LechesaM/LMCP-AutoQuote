from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths
from app.operator_ops.supervised_live_rollout_profile import get_supervised_live_rollout_profile

TEAM_SIZE = 10
PER_OPERATOR_DAILY_CAPACITY = 100
TOTAL_DAILY_CAPACITY = 1000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assignment_path() -> Path:
    return get_runtime_paths().manual_production_file("operator_assignments.jsonl")


def _read_assignments() -> list[dict[str, Any]]:
    path = _assignment_path()
    if not path.exists():
        return []
    records = []
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


def get_operator_capacity_snapshot() -> Dict[str, Any]:
    assignments = _read_assignments()
    assigned_today = len(assignments)
    remaining = max(0, TOTAL_DAILY_CAPACITY - assigned_today)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if assignments else "fallback",
        "team_size": TEAM_SIZE,
        "per_operator_daily_capacity": PER_OPERATOR_DAILY_CAPACITY,
        "total_daily_capacity": TOTAL_DAILY_CAPACITY,
        "assigned_today": assigned_today,
        "remaining_capacity": remaining,
        "overloaded": assigned_today >= TOTAL_DAILY_CAPACITY,
        "recommended_load": 0,
        "rollout_profile": get_supervised_live_rollout_profile(),
    }


def capacity_status() -> Dict[str, Any]:
    return get_operator_capacity_snapshot()
