from __future__ import annotations

from app.main import app


def test_main_exposes_frontend_runtime_surface() -> None:
    routes = {route.path for route in app.routes}

    for path in [
        "/health",
        "/operator-auth/login",
        "/operator-auth/session",
        "/operator-auth/status",
        "/telemetry/dashboard",
        "/telemetry/source-health",
        "/telemetry/review-queue",
        "/telemetry/operational-health",
        "/telemetry/qualification",
        "/operations/source-health-details",
        "/observability/prometheus",
        "/observability/grafana",
        "/observability/sentry",
        "/observability/sla",
        "/observability/anomalies",
        "/observability/alerts",
        "/observability/logs",
        "/observability/uptime",
        "/observability/performance",
    ]:
        assert path in routes, path
