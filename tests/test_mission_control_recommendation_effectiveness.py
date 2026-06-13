from __future__ import annotations

from app.services.mission_control_recommendation_outcome_service import (
    build_default_mission_control_recommendation_outcome_summary,
    build_mission_control_recommendation_outcome_summary,
    record_mission_control_recommendation_outcome,
)


def test_recommendation_outcome_summary_appends_and_aggregates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_OUTCOME_LOG_PATH", str(tmp_path / "recommendation_outcomes.jsonl"))

    record_mission_control_recommendation_outcome(
        {
            "recommendationId": "rec-1",
            "recommendationType": "quote",
            "outcome": "created",
            "daysToOutcome": 0,
            "estimatedProfit": 85000,
            "actualProfit": None,
            "recordedAt": "2026-06-13T08:00:00Z",
        }
    )
    record_mission_control_recommendation_outcome(
        {
            "recommendationId": "rec-1",
            "recommendationType": "quote",
            "outcome": "submitted",
            "daysToOutcome": 3,
            "estimatedProfit": 85000,
            "actualProfit": None,
            "recordedAt": "2026-06-14T08:00:00Z",
        }
    )
    record_mission_control_recommendation_outcome(
        {
            "recommendationId": "rec-1",
            "recommendationType": "quote",
            "outcome": "won",
            "daysToOutcome": 7,
            "estimatedProfit": 85000,
            "actualProfit": 92000,
            "recordedAt": "2026-06-15T08:00:00Z",
        }
    )

    summary = build_mission_control_recommendation_outcome_summary()

    assert summary["status"] == "configured"
    assert summary["totals"]["outcomes"] == 3
    assert summary["totals"]["created"] == 1
    assert summary["totals"]["submitted"] == 1
    assert summary["totals"]["won"] == 1
    assert summary["byRecommendationType"]["quote"]["generated"] == 3
    assert summary["byRecommendationType"]["quote"]["submitted"] == 1
    assert summary["byRecommendationType"]["quote"]["won"] == 1
    assert summary["byRecommendationType"]["quote"]["completionRate"] == 33.33
    assert summary["byRecommendationType"]["quote"]["actionRate"] == 66.67


def test_recommendation_outcome_summary_returns_default_when_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_OUTCOME_LOG_PATH", str(tmp_path / "recommendation_outcomes.jsonl"))

    summary = build_mission_control_recommendation_outcome_summary()

    assert summary["status"] == "insufficient_history"
    assert summary["totals"]["outcomes"] == 0
    assert summary["byOutcome"] == {"created": 0, "submitted": 0, "won": 0, "lost": 0, "no_action": 0}


def test_recommendation_outcome_default_summary_helper() -> None:
    summary = build_default_mission_control_recommendation_outcome_summary()

    assert summary["status"] == "insufficient_history"
    assert summary["totals"]["outcomes"] == 0
