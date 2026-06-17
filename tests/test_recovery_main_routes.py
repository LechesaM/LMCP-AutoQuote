from __future__ import annotations

import os

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DIR", "/Users/cash/Documents/runtime/manual_production")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DB_PATH", "/Users/cash/Documents/runtime/manual_production/lmcp_operations.db")

from app.recovery_main import app
from app.api.route_policy import RouteCategory, build_recovery_policy_introspection, classify_route_path


def test_recovery_main_exposes_incremental_read_only_runtime_routes() -> None:
    paths = {getattr(route, "path", None) for route in app.routes if getattr(route, "path", None)}

    assert "/health/system" in paths
    assert "/health/workflows" in paths
    assert "/health/operational-report" in paths
    assert "/dashboard/workflows" in paths
    assert "/dashboard/refusals" in paths
    assert "/dashboard/health" in paths
    assert "/dashboard/queues" in paths
    assert "/pilot/summary" in paths
    assert "/pilot/readiness" in paths
    assert "/pilot/signoffs" in paths
    assert "/telemetry/dashboard" in paths
    assert "/telemetry/review-queue" in paths
    assert "/telemetry/source-health" in paths
    assert "/telemetry/operational-health" in paths
    assert "/telemetry/qualification" in paths
    assert "/supplier-quotes/status" in paths
    assert "/supplier-quotes/auto-ingest/status" in paths
    assert "/supplier-quotes/intelligence/status" in paths
    assert "/operations/runtime-metrics" in paths
    assert "/operations/backup-validation" in paths
    assert "/governance/compliance-report" in paths
    assert "/governance/compliance-controls" in paths
    assert "/governance/policies" in paths
    assert "/observability/uptime" in paths
    assert "/observability/sla" in paths
    assert "/observability/anomalies" in paths
    assert "/productivity/review-efficiency" in paths
    assert "/productivity/focus-sessions" in paths
    assert "/stabilization/runtime" in paths
    assert "/stabilization/fallback-health" in paths
    assert "/business/executive-summary" in paths
    assert "/business/profitability" in paths
    assert "/system/recovery-policy" in paths

    assert "/dashboard/summary" in paths
    assert "/auth/login" in paths
    assert "/operator-auth/status" in paths


def test_recovery_main_route_policy_blocks_write_routes() -> None:
    paths = {getattr(route, "path", None) for route in app.routes if getattr(route, "path", None)}

    assert "/dashboard/archive" not in paths
    assert "/dashboard/refuse" not in paths
    assert "/dashboard/operator-note" not in paths
    assert "/dashboard/acknowledge-warning" not in paths
    assert "/governance/legal-hold/register" not in paths
    assert "/governance/legal-hold/release" not in paths
    assert "/governance/attestation/generate" not in paths
    assert "/supplier-quotes/run-once" not in paths
    assert "/supplier-quotes/intelligence/run" not in paths
    assert "/supplier-quotes/auto-ingest/run" not in paths

    report = app.state.route_policy_report
    categories = {item["category"] for item in report["routes"]}

    assert RouteCategory.RECOVERY_SAFE_READONLY.value in categories
    assert RouteCategory.RECOVERY_SAFE_ADVISORY.value in categories
    assert RouteCategory.RECOVERY_RESTRICTED.value in categories
    assert classify_route_path("/telemetry/qualification", {"GET"}) == RouteCategory.RECOVERY_SAFE_ADVISORY
    assert classify_route_path("/supplier-quotes/status", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/supplier-quotes/intelligence/status", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY


def test_recovery_policy_endpoint_reports_mounted_and_unmounted_routes() -> None:
    payload = build_recovery_policy_introspection(app.routes)

    assert payload["mode"] == "recovery"
    assert payload["mounted_route_count"] > 0
    assert payload["catalog_route_count"] >= payload["mounted_route_count"]

    routes = {entry["path"]: entry for entry in payload["routes"]}
    assert routes["/system/recovery-policy"]["mounted_in_recovery"] is True
    assert routes["/system/recovery-policy"]["policy_class"] == RouteCategory.RECOVERY_SAFE_READONLY.value
    assert routes["/system/recovery-policy"]["visibility"] == "read-only"
    assert routes["/supplier-quotes/status"]["mounted_in_recovery"] is True
    assert routes["/supplier-quotes/status"]["policy_class"] == RouteCategory.RECOVERY_SAFE_READONLY.value
    assert routes["/supplier-quotes/status"]["visibility"] == "read-only"
    assert routes["/supplier-quotes/intelligence/status"]["mounted_in_recovery"] is True
    assert routes["/supplier-quotes/intelligence/status"]["policy_class"] == RouteCategory.RECOVERY_SAFE_READONLY.value
    assert routes["/supplier-quotes/intelligence/status"]["visibility"] == "read-only"
    assert routes["/telemetry/qualification"]["mounted_in_recovery"] is True
    assert routes["/telemetry/qualification"]["policy_class"] == RouteCategory.RECOVERY_SAFE_ADVISORY.value
    assert routes["/telemetry/qualification"]["visibility"] == "advisory"
    assert any(
        entry["mounted_in_recovery"] is False and entry["visibility"] == "full-runtime-only"
        for entry in payload["routes"]
    )
