from __future__ import annotations

from app.services.mission_control_recommendations_service import build_mission_control_recommendations


def test_recommendations_are_weighted_by_effectiveness() -> None:
    recommendations = build_mission_control_recommendations(
        ai_scoring={
            "items": [
                {
                    "id": "rfq-1",
                    "rfqId": "RFQ-1",
                    "title": "RFQ-1",
                    "score": 90,
                    "estimatedProfit": 5000,
                    "recommendedAction": "review",
                    "reasons": ["Strong buyer intent"],
                    "risks": [],
                }
            ]
        },
        quote_intelligence={
            "status": "configured",
            "supplierCoverage": 30,
            "pricingFreshness": 55,
            "awardSignals": 12,
            "competitorSignals": 8,
        },
        submission_readiness={
            "readiness_state": "READY",
            "blocking_issues": [],
        },
        pipeline_stages={"Blocked": 0},
        recommendation_effectiveness={
            "byRecommendationType": {
                "review": {
                    "recommendationType": "review",
                    "generated": 100,
                    "opened": 75,
                    "acted": 40,
                    "completed": 25,
                    "actionRate": 40.0,
                    "completionRate": 25.0,
                },
                "supplier_gap": {
                    "recommendationType": "supplier_gap",
                    "generated": 100,
                    "opened": 30,
                    "acted": 10,
                    "completed": 5,
                    "actionRate": 10.0,
                    "completionRate": 5.0,
                },
            }
        },
    )

    assert recommendations["status"] == "configured"
    assert recommendations["items"]
    assert recommendations["items"][0]["type"] == "review"
    assert recommendations["items"][0]["weightedScore"] >= recommendations["items"][-1]["weightedScore"]
    assert recommendations["items"][0]["effectiveness"]["completionRate"] == 25.0
