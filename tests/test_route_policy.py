from __future__ import annotations

from app.api.route_policy import RouteCategory, build_route_policy_report, classify_route_path


def test_route_policy_classifies_core_recovery_routes() -> None:
    assert classify_route_path("/dashboard/summary", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/telemetry/qualification", {"GET"}) == RouteCategory.RECOVERY_SAFE_ADVISORY
    assert classify_route_path("/system/recovery-policy", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/operations/runtime-metrics", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/operations/rfqs/REAL-PILOT-001/submission-execution", {"GET"}) == RouteCategory.FULL_RUNTIME_ONLY
    assert classify_route_path("/operations/rfqs/REAL-PILOT-001/submission-execution", {"POST"}) == RouteCategory.FULL_RUNTIME_ONLY
    assert classify_route_path("/governance/compliance-report", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/observability/uptime", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/productivity/review-efficiency", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/stabilization/runtime", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/supplier-quotes/status", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/supplier-quotes/auto-ingest/status", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/supplier-quotes/intelligence/status", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/mission-control/history", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/mission-control/recommendation-effectiveness", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/mission-control/recommendation-outcomes/summary", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/mission-control/recommendation-effectiveness/events", {"POST"}) == RouteCategory.RECOVERY_RESTRICTED
    assert classify_route_path("/mission-control/recommendation-outcomes", {"POST"}) == RouteCategory.RECOVERY_RESTRICTED
    assert classify_route_path("/auth/login", {"POST"}) == RouteCategory.RECOVERY_SAFE_ADVISORY
    assert classify_route_path("/governance/legal-hold/register", {"POST"}) == RouteCategory.RECOVERY_RESTRICTED
    assert classify_route_path("/api/full_autonomous_cycle", {"POST"}) == RouteCategory.RECOVERY_FORBIDDEN


def test_route_policy_report_is_json_safe() -> None:
    report = build_route_policy_report([])

    assert report["routes"] == []
    assert report["counts"] == {}
    assert RouteCategory.RECOVERY_SAFE_READONLY.value in report["allowed_recovery_categories"]
