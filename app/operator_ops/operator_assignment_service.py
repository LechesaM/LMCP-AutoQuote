from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .supervised_live_rollout_profile import get_supervised_live_rollout_profile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_operator_assignments(limit: int = 20) -> Dict[str, Any]:
    profile = get_supervised_live_rollout_profile()
    items = [
        {
            "operator_id": f"operator-{idx}",
            "recommendation": "manual",
            "source": "manual" if idx % 2 == 0 else "operator_action",
            "score": 100 - idx,
        }
        for idx in range(1, min(limit, 10) + 1)
    ]
    return {
        "status": "ok",
        "summary": {"operators": 10, "capacity": 1000},
        "recommended": items,
        "rollout_profile": profile,
        "updated_at": _now_iso(),
    }


def recommend_operator_assignments(limit: int = 20) -> Dict[str, Any]:
    payload = get_operator_assignments(limit=limit)
    return {"status": "ok", **payload}

