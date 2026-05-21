from __future__ import annotations

from app.api.route_policy import RouteCategory, build_route_policy_report, classify_route_path


def test_route_policy_classifies_core_recovery_routes() -> None:
    assert classify_route_path("/dashboard/summary", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/telemetry/qualification", {"GET"}) == RouteCategory.RECOVERY_SAFE_ADVISORY
    assert classify_route_path("/system/recovery-policy", {"GET"}) == RouteCategory.RECOVERY_SAFE_READONLY
    assert classify_route_path("/auth/login", {"POST"}) == RouteCategory.RECOVERY_SAFE_ADVISORY
    assert classify_route_path("/governance/legal-hold/register", {"POST"}) == RouteCategory.RECOVERY_RESTRICTED
    assert classify_route_path("/api/full_autonomous_cycle", {"POST"}) == RouteCategory.RECOVERY_FORBIDDEN


def test_route_policy_report_is_json_safe() -> None:
    report = build_route_policy_report([])

    assert report["routes"] == []
    assert report["counts"] == {}
    assert RouteCategory.RECOVERY_SAFE_READONLY.value in report["allowed_recovery_categories"]
