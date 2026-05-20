from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.orchestration.dead_letter_queue import archive_dlq_item, list_dlq, retry_from_dlq
from app.orchestration.durable_queue import get_queue_depth, get_queue_health
from app.orchestration.queue_recovery_service import detect_queue_recovery_needs, recommend_queue_recovery
from app.orchestration.redis_config import get_redis_config, redis_connection_ready
from app.orchestration.worker_supervision import get_worker_supervision_report
from app.persistence.backup_scheduler import create_runtime_backup, get_backup_status
from app.persistence.migration_plan import generate_migration_plan
from app.persistence.persistence_health import validate_persistence_health
from app.persistence.persistence_reliability_report import build_persistence_reliability_report
from app.persistence.retention_policy import get_retention_policy, run_retention_dry_run
from app.persistence.restore_validator import validate_restore_readiness


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_persistence_health_response() -> Dict[str, Any]:
    payload = validate_persistence_health()
    reliability = build_persistence_reliability_report()
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "health": payload,
        "reliability_report": reliability,
    }


def build_migration_plan_response() -> Dict[str, Any]:
    payload = generate_migration_plan()
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "runtime"),
        "migration_plan": payload,
    }


def build_retention_policy_response() -> Dict[str, Any]:
    policy = get_retention_policy()
    dry_run = run_retention_dry_run(dry_run=True, confirm=False)
    return {
        "status": policy.get("status", "ok"),
        "generated_at": policy.get("generated_at", _now_iso()),
        "data_source": policy.get("data_source", "runtime"),
        "retention_policy": policy,
        "dry_run": dry_run,
    }


def build_backup_status_response() -> Dict[str, Any]:
    payload = get_backup_status()
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "backup_status": payload,
    }


def build_restore_readiness_response() -> Dict[str, Any]:
    backup_status = get_backup_status()
    payload = validate_restore_readiness(backup_status.get("latest_backup_dir", ""))
    return {
        "status": payload.get("status", "blocked"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "restore_readiness": payload,
    }


def build_queue_durability_response() -> Dict[str, Any]:
    queue_depth = get_queue_depth()
    queue_health = get_queue_health()
    redis_config = get_redis_config()
    return {
        "status": queue_health.get("status", "healthy"),
        "generated_at": queue_health.get("generated_at", _now_iso()),
        "data_source": queue_health.get("data_source", "fallback"),
        "queue_depth": queue_depth,
        "queue_health": queue_health,
        "queue_backend": redis_config.backend,
        "queue_backend_ready": redis_connection_ready(),
        "redis_config": {
            "backend": redis_config.backend,
            "host": redis_config.host,
            "port": redis_config.port,
            "database": redis_config.db,
            "configured": redis_config.configured,
        },
    }


def build_dead_letter_queue_response() -> Dict[str, Any]:
    payload = list_dlq()
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "dead_letter_queue": payload,
    }


def build_queue_recovery_response() -> Dict[str, Any]:
    needs = detect_queue_recovery_needs()
    recommendations = recommend_queue_recovery()
    return {
        "status": needs.get("status", "ok"),
        "generated_at": needs.get("generated_at", _now_iso()),
        "data_source": needs.get("data_source", "runtime"),
        "queue_recovery": needs,
        "recommendations": recommendations,
    }


def build_worker_supervision_response() -> Dict[str, Any]:
    payload = get_worker_supervision_report()
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "worker_supervision": payload,
    }


def build_manual_backup_response(*, operator_id: str = "", label: str = "") -> Dict[str, Any]:
    payload = create_runtime_backup(prefix=label or "manual")
    payload["operator_id"] = operator_id
    payload["manual_trigger"] = True
    return payload


def build_retention_dry_run_response(*, confirmed: bool = False) -> Dict[str, Any]:
    return run_retention_dry_run(dry_run=True, confirm=bool(confirmed))


def build_queue_dlq_retry_response(dlq_id: str) -> Dict[str, Any]:
    return retry_from_dlq(dlq_id)


def build_queue_dlq_archive_response(dlq_id: str) -> Dict[str, Any]:
    return archive_dlq_item(dlq_id)
