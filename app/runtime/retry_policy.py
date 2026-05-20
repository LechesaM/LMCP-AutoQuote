from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class RetryPolicy:
    service_name: str
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    backoff_factor: float = 2.0
    max_delay_seconds: float = 15.0
    jitter_seconds: float = 0.0

    def to_jsonable_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "max_attempts": self.max_attempts,
            "base_delay_seconds": self.base_delay_seconds,
            "backoff_factor": self.backoff_factor,
            "max_delay_seconds": self.max_delay_seconds,
            "jitter_seconds": self.jitter_seconds,
        }

    def delays(self) -> List[float]:
        values: List[float] = []
        current = max(0.0, float(self.base_delay_seconds))
        for _ in range(max(1, int(self.max_attempts))):
            values.append(round(min(current, float(self.max_delay_seconds)), 2))
            current *= max(1.0, float(self.backoff_factor))
        return values


def build_retry_policy(
    service_name: str,
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay_seconds: float = 15.0,
    jitter_seconds: float = 0.0,
) -> Dict[str, Any]:
    policy = RetryPolicy(
        service_name=service_name,
        max_attempts=max(1, int(max_attempts)),
        base_delay_seconds=max(0.0, float(base_delay_seconds)),
        backoff_factor=max(1.0, float(backoff_factor)),
        max_delay_seconds=max(0.0, float(max_delay_seconds)),
        jitter_seconds=max(0.0, float(jitter_seconds)),
    )
    return {
        "status": "healthy",
        "advisory_only": True,
        "policy": policy.to_jsonable_dict(),
        "retry_delays": policy.delays(),
        "recommended_delay_seconds": policy.delays()[0] if policy.delays() else 0.0,
    }

