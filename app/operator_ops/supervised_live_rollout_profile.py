from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RolloutPhase:
    days: str
    operators: int
    target_rfqs_per_day: str

    def to_jsonable_dict(self) -> Dict[str, object]:
        return {
            "days": self.days,
            "operators": self.operators,
            "target_rfqs_per_day": self.target_rfqs_per_day,
        }


ROLL_OUT_PROFILE = {
    "name": "initial_supervised_live_rollout",
    "mode": "supervised_live",
    "focus": [
        "queue stability",
        "governance discipline",
        "telemetry usefulness",
        "evidence handling",
        "source quality",
        "operator fatigue",
    ],
    "phases": [
        RolloutPhase(days="1-2", operators=3, target_rfqs_per_day="25-50"),
        RolloutPhase(days="3-4", operators=5, target_rfqs_per_day="50-100"),
        RolloutPhase(days="5-7", operators=7, target_rfqs_per_day="100-200"),
    ],
    "scale_status": "not_scaling_yet",
}


def get_supervised_live_rollout_profile() -> Dict[str, object]:
    return {
        **ROLL_OUT_PROFILE,
        "phases": [phase.to_jsonable_dict() for phase in ROLL_OUT_PROFILE["phases"]],
    }

