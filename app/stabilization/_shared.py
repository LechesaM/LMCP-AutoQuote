from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def as_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def rolling_mean(values: Iterable[float]) -> float:
    items = [float(item) for item in values if item is not None]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 2)

