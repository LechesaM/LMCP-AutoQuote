from __future__ import annotations

import json

from app.api.business_intelligence_routes import router
from app.business_intelligence.executive_dashboard import build_executive_dashboard
from app.business_intelligence.governance_trend_analytics import build_governance_trend_analytics
from app.business_intelligence.profitability_analytics import build_profitability_analytics
from app.business_intelligence.source_roi_analytics import build_source_roi_analytics
from app.business_intelligence.strategic_reporting import build_strategic_report


def test_executive_summary_json_safe() -> None:
    payload = build_executive_dashboard(limit=25)
    json.dumps(payload, default=str)
    assert "executive_summary" in payload
    assert "weekly_trend" in payload
    assert "monthly_trend" in payload


def test_profitability_analytics_json_safe() -> None:
    payload = build_profitability_analytics(limit=25)
    json.dumps(payload, default=str)
    assert "summary" in payload
    assert "high_value_rfqs" in payload


def test_source_roi_json_safe() -> None:
    payload = build_source_roi_analytics(limit=25)
    json.dumps(payload, default=str)
    assert "top_value_sources" in payload
    assert "low_value_sources" in payload


def test_governance_trends_json_safe() -> None:
    payload = build_governance_trend_analytics(limit=25)
    json.dumps(payload, default=str)
    assert "summary" in payload
    assert "governance_incidents" in payload


def test_strategic_report_json_safe() -> None:
    payload = build_strategic_report(limit=25)
    json.dumps(payload, default=str)
    assert "executive_summary" in payload
    assert "export_ready" in payload


def test_business_routes_exist_and_read_only() -> None:
    paths = {route.path for route in router.routes}
    assert "/business/executive-summary" in paths
    assert "/business/profitability" in paths
    assert "/business/rfq-conversion" in paths
    assert "/business/source-roi" in paths
    assert "/business/operator-trends" in paths
    assert "/business/governance-trends" in paths
    assert "/business/workload-forecast" in paths
    assert "/business/opportunity-forecast" in paths
    assert "/business/revenue-projection" in paths
    assert "/business/historical-trends" in paths
    assert "/business/strategic-report" in paths
    assert "/business/export/csv" in paths
    assert "/business/export/pdf-summary" in paths
    for route in router.routes:
        methods = {method.upper() for method in getattr(route, "methods", set())}
        assert methods <= {"GET"}
