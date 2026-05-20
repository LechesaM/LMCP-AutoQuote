from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.runtime_paths import get_runtime_paths
from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.workflow_monitor import get_workflow_summary
from app.orchestration.queue_monitor import get_queue_summary
from app.orchestration.redis_config import get_redis_config, redis_connection_ready
from app.harvest.source_health import get_source_health_summary
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.orchestration.worker_supervision import get_worker_supervision_report
from app.orchestration.dead_letter_queue import list_dlq
from app.persistence.repositories import get_persistence_health
from app.persistence.backup_scheduler import get_backup_status
from app.persistence.restore_validator import validate_restore_readiness
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    return get_runtime_paths().manual_production_file("runtime_metrics.jsonl")


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _read(limit: int = 100) -> List[Dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records[-max(1, int(limit or 100)) :]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _parse_iso(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _recent_workflow_count(limit: int = 500) -> int:
    summary = get_workflow_summary(limit=limit)
    return _safe_int(summary.get("total_workflows", 0))


def _rfqs_per_hour() -> float:
    summary = get_workflow_summary(limit=500)
    updated_at = _parse_iso(summary.get("updated_at") or summary.get("checked_at"))
    total_workflows = _safe_int(summary.get("total_workflows", 0))
    if not updated_at:
        return float(total_workflows)
    hours = max(1.0, max(0.25, (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600.0))
    return round(total_workflows / hours, 2)


def get_runtime_metrics(limit: int = 100) -> Dict[str, Any]:
    metrics = get_metrics_snapshot().get("metrics", {})
    workflow = get_workflow_summary(limit=limit)
    queue = get_queue_summary(limit=limit)
    sources = get_source_health_summary(limit=limit)
    capacity = get_operator_capacity_snapshot()
    system = get_system_health()
    persistence = get_persistence_health()
    queue_backend = get_redis_config()
    dlq = list_dlq()
    backup_status = get_backup_status()
    restore_ready = validate_restore_readiness(backup_status.get("latest_backup_dir", ""))
    workers = get_worker_supervision_report()
    productivity = build_review_efficiency_analytics(limit=limit)
    runtime = {
        "rfqs_harvested_per_hour": _rfqs_per_hour(),
        "review_throughput": _safe_int(metrics.get("reviews_recorded", 0)),
        "queue_lag": _safe_int(queue.get("queue_lag_minutes", queue.get("summary", {}).get("queueLagMinutes", 0))),
        "operator_utilization": round((_safe_int(capacity.get("assigned_today", 0)) / max(1, _safe_int(capacity.get("total_daily_capacity", 1000)))) * 100.0, 2),
        "parser_failure_rate": float(sources.get("parser_failure_rate", 0.0)),
        "source_availability": round((_safe_int(sources.get("healthy_sources", 0)) / max(1, _safe_int(sources.get("total_sources", 1)))) * 100.0, 2),
        "telemetry_freshness_minutes": 0,
        "workflow_failures": _safe_int(metrics.get("workflow_failures", 0)),
        "persistence_failures": _safe_int(metrics.get("persistence_failures", 0)),
        "auth_failures": _safe_int(metrics.get("auth_failures", 0)),
        "rate_limit_events": _safe_int(metrics.get("rate_limit_events", 0)),
        "api_latency_ms": _safe_int(metrics.get("api_latency_ms", 0)),
        "backup_age_days": _safe_int(backup_status.get("latest_backup_age_days", -1)),
        "dlq_count": _safe_int(dlq.get("count", 0)),
        "worker_stale_count": _safe_int(workers.get("stale_worker_count", 0)),
        "operator_review_throughput": float(productivity.get("rfqs_reviewed_per_hour", 0.0)),
        "operator_review_efficiency": float(productivity.get("review_completion_time_minutes", 0.0)),
    }
    latest_snapshot = _read(limit=1)
    generated_at = latest_snapshot[-1].get("generated_at") if latest_snapshot else _now_iso()
    return {
        "status": "ok" if system.get("status") != "unhealthy" else "degraded",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "runtime_mode": system.get("production_mode", ""),
        "environment": system.get("environment", ""),
        "metrics": runtime,
        "workflow_summary": workflow,
        "queue_summary": queue,
        "source_summary": sources,
        "operator_capacity": capacity,
        "persistence": persistence,
        "queue_backend": queue_backend.backend,
        "queue_backend_ready": redis_connection_ready(),
        "dlq": dlq,
        "backup_status": backup_status,
        "restore_ready": restore_ready,
        "workers": workers,
        "productivity": productivity,
        "system_health": system,
        "telemetry_freshness_minutes": runtime["telemetry_freshness_minutes"],
        "last_snapshot_at": generated_at,
    }


def record_runtime_snapshot(snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = snapshot or get_runtime_metrics()
    record = {
        "snapshot_id": f"runtime-{datetime.now(timezone.utc).timestamp()}",
        "generated_at": _now_iso(),
        "data_source": payload.get("data_source", "runtime"),
        "payload": payload,
    }
    return _append(record)


def get_runtime_snapshots(limit: int = 100) -> Dict[str, Any]:
    items = _read(limit=limit)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "snapshots": items,
        "total": len(items),
    }
