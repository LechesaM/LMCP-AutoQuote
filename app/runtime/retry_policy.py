from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_RETRY_DELAYS = (1.0, 2.0, 5.0)
DEFAULT_MAX_RETRIES = 3


def build_retry_policy(service_name: str, *, retry_delays: List[float] | None = None, max_retries: int | None = None) -> Dict[str, Any]:
    normalized_service = str(service_name or "").strip() or "runtime"
    delays = [float(delay) for delay in (retry_delays or DEFAULT_RETRY_DELAYS)]
    delays = [delay if delay > 0 else 1.0 for delay in delays]
    retries_value = int(max_retries if max_retries is not None else DEFAULT_MAX_RETRIES)
    if retries_value < 1:
        retries_value = DEFAULT_MAX_RETRIES
    return {
        "service_name": normalized_service,
        "retry_delays": delays,
        "max_retries": retries_value,
        "policy": {
            "service_name": normalized_service,
            "retry_delays": delays,
            "max_retries": retries_value,
            "backoff": True,
        },
    }

