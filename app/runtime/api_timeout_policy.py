from __future__ import annotations

from typing import Any, Dict


DEFAULT_TIMEOUT_SECONDS = 12.0
DEFAULT_RETRY_DELAY_SECONDS = 2.0
DEFAULT_MAX_ATTEMPTS = 3


def build_api_timeout_policy(service_name: str, *, timeout_seconds: float | None = None, retry_delay_seconds: float | None = None, max_attempts: int | None = None) -> Dict[str, Any]:
    normalized_service = str(service_name or "").strip() or "runtime"
    timeout_value = float(timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS)
    if timeout_value <= 0:
        timeout_value = DEFAULT_TIMEOUT_SECONDS
    retry_delay_value = float(retry_delay_seconds if retry_delay_seconds is not None else DEFAULT_RETRY_DELAY_SECONDS)
    if retry_delay_value <= 0:
        retry_delay_value = DEFAULT_RETRY_DELAY_SECONDS
    attempts_value = int(max_attempts if max_attempts is not None else DEFAULT_MAX_ATTEMPTS)
    if attempts_value < 1:
        attempts_value = DEFAULT_MAX_ATTEMPTS
    return {
        "service_name": normalized_service,
        "timeout_seconds": timeout_value,
        "retry_delay_seconds": retry_delay_value,
        "max_attempts": attempts_value,
        "retry_delays": [retry_delay_value * factor for factor in (1, 2, 4)],
        "policy": {
            "service_name": normalized_service,
            "timeout_seconds": timeout_value,
            "retry_delay_seconds": retry_delay_value,
            "max_attempts": attempts_value,
        },
    }

