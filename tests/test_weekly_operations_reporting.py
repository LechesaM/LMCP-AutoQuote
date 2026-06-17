from __future__ import annotations

import json

from app.api.business_intelligence_routes import router
from app.api.dashboard import dashboard_weekly_operations
from app.services.weekly_operations_report_service import build_weekly_operations_report


def test_weekly_operations_report_json_safe() -> None:
    payload = build_weekly_operations_report(window_days=7, limit=25)
    json.dumps(payload, default=str)
    assert payload["status"] == "ok"
    assert "procurement_funnel" in payload
    assert "financial_funnel" in payload
    assert "supplier_funnel" in payload
    assert "award_intelligence" in payload
    assert "summary" in payload


def test_dashboard_weekly_operations_endpoint_returns_report() -> None:
    payload = dashboard_weekly_operations(window_days=7, limit=25)
    assert payload["status"] == "ok"
    assert "weekly_operations" not in payload
    assert "procurement_funnel" in payload


def test_business_intelligence_routes_include_weekly_operations() -> None:
    paths = {route.path for route in router.routes}
    assert "/business/weekly-operations" in paths
    assert "/business/executive-summary" in paths
    assert "/business/strategic-report" in paths
    for route in router.routes:
        methods = {method.upper() for method in getattr(route, "methods", set())}
        assert methods <= {"GET"}
