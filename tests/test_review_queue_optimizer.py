from __future__ import annotations

from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary


def test_queue_ordering_stable():
    payload = build_review_queue_optimization_summary(limit=50)
    items = payload["optimized_queue"]
    assert items == sorted(items, key=lambda row: (-float(row["priority_score"]), float(row["queue_age_minutes"]), str(row["tender_id"])))


def test_overdue_detection_valid():
    payload = build_review_queue_optimization_summary(limit=50)
    assert "overdue_reviews" in payload


def test_priority_groups_valid():
    payload = build_review_queue_optimization_summary(limit=50)
    groups = payload["priority_groups"]
    assert set(groups).issuperset({"urgent", "high", "medium", "low"})


def test_stale_rfq_detection_valid():
    payload = build_review_queue_optimization_summary(limit=50)
    assert "stale_rfqs" in payload

