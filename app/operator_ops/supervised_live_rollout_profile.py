from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_supervised_live_rollout_profile() -> Dict[str, Any]:
    return {
        "name": "initial_supervised_live_rollout",
        "scale_status": "not_scaling_yet",
        "focus": "queue stability and conservative manual review",
        "phases": [
            {"name": "phase_1", "operators": 3, "target_rfqs_per_day": "25-50"},
            {"name": "phase_2", "operators": 5, "target_rfqs_per_day": "50-100"},
            {"name": "phase_3", "operators": 7, "target_rfqs_per_day": "100-150"},
        ],
        "updated_at": _now_iso(),
    }

