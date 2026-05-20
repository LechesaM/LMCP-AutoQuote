from __future__ import annotations

import json

from app.business_intelligence.forecasting_engine import build_forecasting_engine
from app.business_intelligence.historical_trend_engine import build_historical_trend_engine
from app.business_intelligence.opportunity_forecasting import build_opportunity_forecast
from app.business_intelligence.revenue_projection import build_revenue_projection
from app.business_intelligence.workload_forecasting import build_workload_forecast


def test_forecasts_generated_safely() -> None:
    payloads = [
        build_workload_forecast(limit=25),
        build_opportunity_forecast(limit=25),
        build_revenue_projection(limit=25),
        build_forecasting_engine({"queue_depth": [1, 2, 3]}, horizon=3),
        build_historical_trend_engine([{"created_at": "2026-05-01T00:00:00+00:00", "estimated_profit": 100.0}]),
    ]
    for payload in payloads:
        json.dumps(payload, default=str)
        assert "status" in payload
        assert "generated_at" in payload


def test_forecast_states_valid() -> None:
    payload = build_workload_forecast(limit=25)
    assert payload["advisory_only"] is True
    assert payload["status"] in {"ok", "fallback"}


def test_no_autonomous_actions_in_forecasting() -> None:
    payload = build_opportunity_forecast(limit=25)
    assert payload["advisory_only"] is True
    assert payload["status"] in {"ok", "fallback"}


def test_rolling_averages_valid() -> None:
    payload = build_forecasting_engine({"queue_depth": [5, 10, 15, 20]}, horizon=4)
    json.dumps(payload, default=str)
    assert "trends" in payload
    assert "projections" in payload

