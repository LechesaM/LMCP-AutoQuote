import json

from app.stabilization.deployment_stability_checks import build_deployment_stability_report
from app.stabilization.fallback_resilience import build_fallback_resilience_report
from app.stabilization.governance_consistency_validator import build_governance_consistency_report
from app.stabilization.operator_fatigue_monitor import build_operator_fatigue_report
from app.stabilization.runtime_stability_engine import build_runtime_stability_report


def _assert_json_safe(payload):
    json.dumps(payload, default=str)


def test_runtime_stability_summary_is_json_safe():
    payload = build_runtime_stability_report(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert "stability_score" in payload
    assert isinstance(payload["operational_warnings"], list)


def test_fallback_resilience_summary_is_json_safe():
    payload = build_fallback_resilience_report(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert "fallback_activations" in payload
    assert "runtime_recovery_success" in payload


def test_operator_fatigue_summary_is_json_safe():
    payload = build_operator_fatigue_report(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert isinstance(payload["fatigue_rows"], list)
    assert isinstance(payload["workload_rebalance_recommendations"], list)


def test_deployment_stability_summary_is_json_safe():
    payload = build_deployment_stability_report(limit=25)
    _assert_json_safe(payload)
    assert payload["status"] in {"healthy", "degraded", "failing"}
    assert isinstance(payload["route_names"], list)

