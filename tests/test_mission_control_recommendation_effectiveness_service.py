from __future__ import annotations

from app.services.mission_control_recommendation_effectiveness_service import (
    build_mission_control_recommendation_effectiveness,
    record_mission_control_recommendation_event,
)


def test_recommendation_effectiveness_appends_and_summarizes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_EFFECTIVENESS_LOG_PATH", str(tmp_path / "recommendation_effectiveness.jsonl"))

    record_mission_control_recommendation_event(
        {
            "eventType": "generated",
            "recommendationId": "rec-1",
            "recommendationType": "review",
            "priority": "high",
            "source": "ai_scoring",
            "relatedRfqId": "RFQ-1",
            "score": 92,
            "estimatedProfit": 1200,
            "occurredAt": "2026-06-13T08:00:00Z",
        }
    )
    record_mission_control_recommendation_event(
        {
            "eventType": "opened",
            "recommendationId": "rec-1",
            "recommendationType": "review",
            "priority": "high",
            "source": "ai_scoring",
            "relatedRfqId": "RFQ-1",
            "score": 92,
            "estimatedProfit": 1200,
            "occurredAt": "2026-06-13T08:05:00Z",
        }
    )
    record_mission_control_recommendation_event(
        {
            "eventType": "acted",
            "recommendationId": "rec-1",
            "recommendationType": "review",
            "priority": "high",
            "source": "ai_scoring",
            "relatedRfqId": "RFQ-1",
            "score": 92,
            "estimatedProfit": 1200,
            "occurredAt": "2026-06-13T08:10:00Z",
        }
    )
    record_mission_control_recommendation_event(
        {
            "eventType": "completed",
            "recommendationId": "rec-1",
            "recommendationType": "review",
            "priority": "high",
            "source": "ai_scoring",
            "relatedRfqId": "RFQ-1",
            "score": 92,
            "estimatedProfit": 1200,
            "occurredAt": "2026-06-13T08:15:00Z",
        }
    )

    summary = build_mission_control_recommendation_effectiveness()

    assert summary["status"] == "configured"
    assert summary["totals"]["events"] == 4
    assert summary["totals"]["generated"] == 1
    assert summary["totals"]["opened"] == 1
    assert summary["totals"]["acted"] == 1
    assert summary["totals"]["completed"] == 1
    assert summary["byRecommendationType"]["review"] == 4


def test_recommendation_effectiveness_returns_default_when_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LMCP_MISSION_CONTROL_EFFECTIVENESS_LOG_PATH", str(tmp_path / "recommendation_effectiveness.jsonl"))

    summary = build_mission_control_recommendation_effectiveness()

    assert summary["status"] == "insufficient_history"
    assert summary["totals"]["events"] == 0
    assert summary["byEventType"] == {"generated": 0, "opened": 0, "acted": 0, "completed": 0}
