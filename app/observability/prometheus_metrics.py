from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.observability.metrics_registry import get_observability_metrics


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(name or "").strip().lower())
    cleaned = cleaned.strip("_") or "metric"
    return f"lmcp_{cleaned}"


def build_prometheus_metrics_export(limit: int = 100) -> Dict[str, Any]:
    payload = get_observability_metrics(limit=limit)
    metrics = payload.get("metrics", {})
    lines: List[str] = [
        "# HELP lmcp_runtime_observability_snapshot LMCP runtime observability snapshot.",
        "# TYPE lmcp_runtime_observability_snapshot gauge",
        "lmcp_runtime_observability_snapshot 1",
    ]
    for key, value in metrics.items():
        if isinstance(value, bool):
            numeric = 1 if value else 0
        elif isinstance(value, (int, float)):
            numeric = value
        else:
            continue
        metric_name = _metric_name(key)
        help_text = key.replace("_", " ")
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {numeric}")
    text = "\n".join(lines) + "\n"
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "metrics": metrics,
        "metrics_count": len(metrics),
        "text": text,
    }
