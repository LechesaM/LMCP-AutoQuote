from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict


_METRICS: Dict[str, int] = defaultdict(int)


def reset_test_metrics() -> None:
    _METRICS.clear()


def increment_metric(name: str, amount: int = 1) -> None:
    _METRICS[name] = int(_METRICS.get(name, 0)) + int(amount)


def get_metrics_snapshot() -> Dict[str, Any]:
    return {"status": "ok", "metrics": dict(_METRICS)}
