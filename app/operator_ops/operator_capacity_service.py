from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .supervised_live_rollout_profile import get_supervised_live_rollout_profile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_operator_capacity_snapshot() -> Dict[str, Any]:
    return {
        "status": "ok",
        "total_daily_capacity": 1000,
        "team_size": 10,
        "rollout_profile": get_supervised_live_rollout_profile(),
        "updated_at": _now_iso(),
    }

