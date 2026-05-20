from __future__ import annotations

from typing import Any, Dict


DEFAULT_TIMEOUTS = {
    "runtime": 10.0,
    "telemetry": 10.0,
    "queue": 8.0,
    "persistence": 12.0,
    "auth": 6.0,
    "observability": 8.0,
}


def build_api_timeout_policy(service_name: str, *, timeout_seconds: float | None = None) -> Dict[str, Any]:
    timeout = float(timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUTS.get(service_name, 10.0))
    timeout = max(0.5, timeout)
    return {
        "status": "healthy",
        "service_name": service_name,
        "timeout_seconds": round(timeout, 2),
        "warning_after_seconds": round(timeout * 0.75, 2),
        "retry_budget": 2,
        "advisory_only": True,
    }


def get_timeout_policy(service_name: str) -> Dict[str, Any]:
    return build_api_timeout_policy(service_name)

