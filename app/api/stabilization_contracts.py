from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.stabilization.deployment_stability_checks import build_deployment_stability_report
from app.stabilization.fallback_resilience import build_fallback_resilience_report
from app.stabilization.governance_consistency_validator import build_governance_consistency_report
from app.stabilization.operator_fatigue_monitor import build_operator_fatigue_report
from app.stabilization.operator_ux_feedback import build_operator_ux_feedback_report
from app.stabilization.runtime_cleanup import build_runtime_cleanup_report, build_runtime_cleanup_dry_run
from app.stabilization.runtime_stability_engine import build_runtime_stability_report
from app.stabilization.telemetry_noise_reduction import build_telemetry_noise_reduction_report


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wrap(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        key: payload,
    }


def build_stabilization_runtime_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_runtime_stability_report(limit=limit), "runtime_stability")


def build_stabilization_fallback_health_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_fallback_resilience_report(limit=limit), "fallback_health")


def build_stabilization_telemetry_noise_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_telemetry_noise_reduction_report(limit=limit), "telemetry_noise")


def build_stabilization_governance_consistency_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_governance_consistency_report(limit=limit), "governance_consistency")


def build_stabilization_operator_fatigue_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_operator_fatigue_report(limit=limit), "operator_fatigue")


def build_stabilization_operator_feedback_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_operator_ux_feedback_report(limit=limit), "operator_feedback")


def build_stabilization_runtime_cleanup_response(limit: int = 100, *, confirmed: bool = False) -> Dict[str, Any]:
    payload = build_runtime_cleanup_report(limit=limit, confirmed=confirmed)
    return _wrap(payload, "runtime_cleanup")


def build_stabilization_runtime_cleanup_dry_run_response(limit: int = 100, *, confirmed: bool = False) -> Dict[str, Any]:
    payload = build_runtime_cleanup_dry_run(limit=limit, confirmed=confirmed)
    return _wrap(payload, "runtime_cleanup")


def build_stabilization_deployment_stability_response(limit: int = 100) -> Dict[str, Any]:
    return _wrap(build_deployment_stability_report(limit=limit), "deployment_stability")

