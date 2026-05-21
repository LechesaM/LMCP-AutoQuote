from __future__ import annotations

import os

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DIR", "/Users/cash/Documents/runtime/manual_production")
os.environ.setdefault("LMCP_MANUAL_PRODUCTION_DB_PATH", "/Users/cash/Documents/runtime/manual_production/lmcp_operations.db")

from app.recovery_main import app
from app.api.route_policy import RouteCategory, classify_route_path


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

    report = app.state.route_policy_report
    categories = {item["category"] for item in report["routes"]}

    assert RouteCategory.RECOVERY_SAFE_READONLY.value in categories
    assert RouteCategory.RECOVERY_SAFE_ADVISORY.value in categories
    assert RouteCategory.RECOVERY_RESTRICTED.value in categories
    assert classify_route_path("/telemetry/qualification", {"GET"}) == RouteCategory.RECOVERY_SAFE_ADVISORY
