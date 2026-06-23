from __future__ import annotations

from app.main import app


def test_main_exposes_frontend_runtime_surface() -> None:
    routes = {route.path for route in app.routes}

    for path in [
        "/health",
        "/status",
        "/operator-auth/login",
        "/operator-auth/session",
        "/operator-auth/status",
        "/telemetry/dashboard",
        "/telemetry/source-health",
        "/telemetry/review-queue",
        "/telemetry/operational-health",
        "/telemetry/qualification",
        "/operations/source-health-details",
        "/rfq-lifecycle/upload-dry-run/status",
        "/rfq-lifecycle/rehearsals/history",
        "/rfq-lifecycle/rehearsals/latest",
        "/rfq-lifecycle/rehearsals/readiness",
        "/rfq-lifecycle/rehearsals/readiness/history",
        "/rfq-lifecycle/pilot-evidence/history",
        "/rfq-lifecycle/pilot-evidence/latest",
        "/rfq-lifecycle/pilot-evidence/governance-review",
        "/rfq-lifecycle/pilot-evidence/{pack_id}",
        "/rfq-lifecycle/stability",
        "/rfq-lifecycle/stability/latest",
        "/rfq-lifecycle/stability/history",
        "/rfq-lifecycle/cadence",
        "/rfq-lifecycle/cadence/latest",
        "/rfq-lifecycle/cadence/history",
        "/rfq-lifecycle/review-board",
        "/rfq-lifecycle/review-board/latest",
        "/rfq-lifecycle/review-board/history",
        "/rfq-lifecycle/recurring-cycles",
        "/rfq-lifecycle/recurring-cycles/latest",
        "/rfq-lifecycle/recurring-cycles/history",
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
