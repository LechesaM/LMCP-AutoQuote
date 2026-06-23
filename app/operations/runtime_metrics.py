from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.monitoring.health_service import get_system_health
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence.repositories import get_persistence_health

from .structured_logging import log_runtime_diagnostic


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metrics_file() -> Path:
    return get_runtime_paths().health_dir / "runtime_metrics.jsonl"


def _safe_status(payload: Dict[str, Any]) -> str:
    status = str(payload.get("status") or "").strip().lower()
    if status:
        return status
    if "stale_worker_count" in payload:
        try:
            return "healthy" if int(payload.get("stale_worker_count") or 0) <= 0 else "degraded"
        except Exception:
            return "degraded"
    return ""


def _read_metrics(path: Path | None = None) -> List[Dict[str, Any]]:
    file_path = path or _metrics_file()
    if not file_path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _write_metric_snapshot(snapshot: Dict[str, Any], path: Path | None = None) -> Dict[str, Any]:
    file_path = path or _metrics_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(snapshot or {})
    payload.setdefault("generated_at", _utc_now_iso())
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
    return payload


def get_metrics_snapshot(limit: int = 100) -> Dict[str, Any]:
    system_health = get_system_health()
    workflow_summary = get_workflow_summary(limit=limit)
    queue_summary = get_queue_summary(limit=limit)
    source_health = get_source_health_summary(limit=limit)
    persistence_health = get_persistence_health()
    worker_supervision = get_worker_supervision_report()
    alertiness = {
        "status": "ok",
        "generated_at": _utc_now_iso(),
        "metrics": {
            "system_status": _safe_status(system_health),
            "workflow_count": int(workflow_summary.get("total_workflows") or 0),
            "queue_lag_minutes": int(queue_summary.get("queue_lag_minutes") or 0),
            "healthy_sources": int(source_health.get("healthy_sources") or 0),
            "stale_workers": int(worker_supervision.get("stale_worker_count") or 0),
            "persistence_status": _safe_status(persistence_health),
        },
    }
    return alertiness


def get_queue_summary(limit: int = 100) -> Dict[str, Any]:
    summary = get_workflow_summary(limit=limit)
    return {
        "status": "ok",
        "queue_lag_minutes": 0,
        "summary": summary.get("queue_summary") or {},
    }


def get_source_health_summary(limit: int = 100) -> Dict[str, Any]:
    return {
        "status": "ok",
        "failing_sources": 0,
        "parser_failure_rate": 0.0,
        "healthy_sources": 0,
        "total_sources": 0,
    }


def get_operator_capacity_snapshot() -> Dict[str, Any]:
    return {"assigned_today": 0, "total_daily_capacity": 0}


def get_redis_config() -> Any:
    return type("RedisConfig", (), {"backend": "unknown"})()


def redis_connection_ready() -> bool:
    return False


def list_dlq() -> Dict[str, Any]:
    return {"count": 0}


def get_backup_status() -> Dict[str, Any]:
    return {"backup_age_warning": False, "latest_backup_age_days": 0, "latest_backup_dir": ""}


def validate_restore_readiness(backup_dir: Any) -> Dict[str, Any]:
    return {"status": "healthy"}


def get_worker_supervision_report() -> Dict[str, Any]:
    try:
        from app.orchestration.worker_supervision import detect_stale_workers

        stale = detect_stale_workers(stale_after_minutes=10)
        return {
            "status": "ok" if not stale else "degraded",
            "stale_worker_count": len(stale),
            "stale_workers": stale,
        }
    except Exception:
        return {"status": "fallback", "stale_worker_count": 0, "stale_workers": []}


def build_review_efficiency_analytics(limit: int = 100) -> Dict[str, Any]:
    return {"rfqs_reviewed_per_hour": 0.0, "review_completion_time_minutes": 0.0}


def build_runtime_metrics_snapshot(limit: int = 100) -> Dict[str, Any]:
    system_health = get_system_health()
    workflow_summary = get_workflow_summary(limit=limit)
    queue_summary = get_queue_summary(limit=limit)
    source_health = get_source_health_summary(limit=limit)
    operator_capacity = get_operator_capacity_snapshot()
    persistence_health = get_persistence_health()
    worker_supervision = get_worker_supervision_report()
    backup_status = get_backup_status()
    restore_readiness = validate_restore_readiness(backup_status.get("latest_backup_dir"))
    review_efficiency = build_review_efficiency_analytics(limit=limit)
    try:
        metrics_snapshot = get_metrics_snapshot(limit=limit)
    except TypeError:
        metrics_snapshot = get_metrics_snapshot()

    system_status = _safe_status(system_health)
    persistence_status = _safe_status(persistence_health)
    worker_status = _safe_status(worker_supervision)

    stability_score = 100.0
    if system_status not in {"ok", "healthy"}:
        stability_score -= 35.0
    if persistence_status not in {"ok", "healthy"}:
        stability_score -= 30.0
    if worker_status not in {"ok", "healthy"}:
        stability_score -= 20.0
    if int(queue_summary.get("queue_lag_minutes") or 0) > 10:
        stability_score -= 10.0
    if int(source_health.get("failing_sources") or 0) > 0:
        stability_score -= 5.0
    stability_score = max(0.0, min(100.0, round(stability_score, 2)))

    stale_telemetry = system_status not in {"ok", "healthy"} or persistence_status not in {"ok", "healthy"} or worker_status not in {"ok", "healthy"}
    telemetry_state = "stale" if stale_telemetry else "fresh"
    current_score = stability_score
    if isinstance(metrics_snapshot, dict):
        metrics_value = metrics_snapshot.get("metrics")
        if isinstance(metrics_value, dict) and metrics_value.get("stability_score") is not None:
            try:
                current_score = float(metrics_value.get("stability_score"))
            except Exception:
                current_score = stability_score

    current_snapshot = {
        "status": "degraded" if stale_telemetry else "ok",
        "telemetry_state": telemetry_state,
        "stale_telemetry": stale_telemetry,
        "degraded_state": stale_telemetry,
        "generated_at": _utc_now_iso(),
        "data_source": "runtime",
        "system_health": system_health,
        "workflow_summary": workflow_summary,
        "queue_summary": queue_summary,
        "source_health": source_health,
        "operator_capacity": operator_capacity,
        "persistence": persistence_health,
        "worker_supervision": worker_supervision,
        "backup_status": backup_status,
        "restore_readiness": restore_readiness,
        "review_efficiency": review_efficiency,
        "metrics_snapshot": metrics_snapshot,
        "metrics": {
            "stability_score": current_score,
        },
    }
    safe_path = get_runtime_paths().health_dir / "runtime_metrics_last_safe.json"
    if stale_telemetry and safe_path.exists():
        try:
            last_safe_snapshot = json.loads(safe_path.read_text(encoding="utf-8"))
        except Exception:
            last_safe_snapshot = {}
    else:
        last_safe_snapshot = dict(current_snapshot)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(json.dumps(last_safe_snapshot, indent=2, default=str), encoding="utf-8")

    if stale_telemetry and isinstance(last_safe_snapshot, dict):
        last_safe_metrics = last_safe_snapshot.get("metrics")
        if isinstance(last_safe_metrics, dict) and last_safe_metrics.get("stability_score") is not None:
            current_snapshot["metrics"]["stability_score"] = last_safe_metrics.get("stability_score")

    current_snapshot["last_safe_snapshot"] = last_safe_snapshot
    current_snapshot["last_safe_snapshot_at"] = _clean_safe_timestamp(last_safe_snapshot.get("generated_at"))
    log_runtime_diagnostic("runtime_metrics", "Built runtime metrics snapshot", snapshot=current_snapshot)
    _write_metric_snapshot(current_snapshot)
    return current_snapshot


def _clean_safe_timestamp(value: Any) -> str:
    return str(value or "").strip()


def record_runtime_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(snapshot or {})
    payload.setdefault("generated_at", _utc_now_iso())
    if str(payload.get("status") or "").lower() in {"ok", "healthy"}:
        safe_path = get_runtime_paths().health_dir / "runtime_metrics_last_safe.json"
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        payload["last_safe_snapshot_at"] = payload.get("generated_at")
    _write_metric_snapshot(payload)
    return payload


def get_runtime_metrics(limit: int = 100) -> Dict[str, Any]:
    snapshot = build_runtime_metrics_snapshot(limit=limit)
    history = _read_metrics()
    recent = list(reversed(history[-max(1, int(limit or 100)) :]))
    snapshot["history"] = recent
    snapshot["history_count"] = len(history)
    return snapshot
