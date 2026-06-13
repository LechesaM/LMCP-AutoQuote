from __future__ import annotations

from app.api.mission_control_snapshot_api import _default_snapshot


def test_default_mission_control_snapshot_includes_recommendation_effectiveness() -> None:
    snapshot = _default_snapshot()

    assert snapshot["recommendationEffectiveness"]["status"] == "insufficient_history"
    assert snapshot["recommendationEffectiveness"]["totals"]["events"] == 0
