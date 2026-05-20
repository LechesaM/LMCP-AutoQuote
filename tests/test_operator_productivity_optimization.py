from __future__ import annotations

import json

from app.api.operator_productivity_routes import router
from app.productivity.operator_workload_balancer import build_operator_workload_summary
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary
from app.productivity.operator_focus_sessions import build_focus_session_summary
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics


def test_workload_balancing_json_safe():
    payload = build_operator_workload_summary(limit=50)
    json.dumps(payload, default=str)
    assert "operators" in payload


def test_queue_optimization_json_safe():
    payload = build_review_queue_optimization_summary(limit=50)
    json.dumps(payload, default=str)
    assert "optimized_queue" in payload


def test_focus_session_metrics_valid():
    payload = build_focus_session_summary(limit=50)
    json.dumps(payload, default=str)
    assert "summary" in payload


def test_efficiency_analytics_valid():
    payload = build_review_efficiency_analytics(limit=50)
    json.dumps(payload, default=str)
    assert "rfqs_reviewed_per_hour" in payload


def test_productivity_routes_exist():
    paths = {route.path for route in router.routes}
    assert "/productivity/workload" in paths
    assert "/productivity/queue-optimization" in paths
    assert "/productivity/review-efficiency" in paths
    assert "/productivity/focus-sessions" in paths
    assert "/productivity/queue-heatmap" in paths
    assert "/productivity/review-priorities" in paths
    assert "/productivity/evidence-acceleration" in paths
