from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.operations.health_snapshots import get_health_snapshots
from app.operations.runtime_metrics import get_runtime_snapshots
from app.persistence.backup_scheduler import get_backup_status
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary

from ._shared import now_iso, safe_int, safe_str


def _file_age_days(path: Path) -> float:
    try:
        return round(max(0.0, (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 86400.0), 2)
    except Exception:
        return 0.0


def build_runtime_cleanup_report(*, dry_run: bool = True, confirmed: bool = False, limit: int = 100) -> Dict[str, Any]:
    paths = get_runtime_paths()
    runtime_snapshots = get_runtime_snapshots(limit=limit).get("snapshots", [])
    health_snapshots = get_health_snapshots(limit=limit).get("snapshots", [])
    queue = build_review_queue_optimization_summary(limit=limit)
    backup = get_backup_status()

    cleanup_candidates: List[Dict[str, Any]] = []
    for name in ("runtime_metrics.jsonl", "health_snapshots.jsonl"):
        path = paths.manual_production_file(name)
        if path.exists() and _file_age_days(path) > 7:
            cleanup_candidates.append({"path": str(path), "reason": "stale telemetry log", "age_days": _file_age_days(path), "category": "telemetry"})
    for file_path in paths.manual_production_dir.glob("*.tmp"):
        cleanup_candidates.append({"path": str(file_path), "reason": "temporary artifact", "age_days": _file_age_days(file_path), "category": "artifact"})
    for file_path in paths.manual_production_dir.glob("*.partial"):
        cleanup_candidates.append({"path": str(file_path), "reason": "partial artifact", "age_days": _file_age_days(file_path), "category": "artifact"})
    for file_path in paths.manual_production_dir.glob("*.cache"):
        cleanup_candidates.append({"path": str(file_path), "reason": "cache artifact", "age_days": _file_age_days(file_path), "category": "artifact"})
    if queue.get("stale_rfqs"):
        cleanup_candidates.append({"path": "queue_recommendations", "reason": "stale queue recommendations", "age_days": 0.0, "category": "queue"})

    if backup.get("backup_age_warning"):
        cleanup_candidates.append({"path": backup.get("latest_backup_dir", ""), "reason": "backup age warning", "age_days": safe_int(backup.get("latest_backup_age_days", 0), 0), "category": "backup"})

    cleanup_summary = {
        "runtime_snapshot_count": len(runtime_snapshots),
        "health_snapshot_count": len(health_snapshots),
        "cleanup_candidate_count": len(cleanup_candidates),
        "stale_telemetry_count": len([item for item in cleanup_candidates if item.get("category") == "telemetry"]),
        "artifact_count": len([item for item in cleanup_candidates if item.get("category") == "artifact"]),
        "queue_recommendation_count": len([item for item in cleanup_candidates if item.get("category") == "queue"]),
        "backup_related_count": len([item for item in cleanup_candidates if item.get("category") == "backup"]),
    }
    warnings = []
    if cleanup_candidates:
        warnings.append("Dry-run cleanup candidates were identified.")
    if backup.get("backup_age_warning"):
        warnings.append("Backup age warning should be reviewed before cleanup.")
    status = "healthy" if not cleanup_candidates else "degraded"
    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "dry_run_only": True,
        "confirmed": bool(confirmed),
        "cleanup_summary": cleanup_summary,
        "would_cleanup": cleanup_candidates,
        "warnings": warnings,
        "blockers": [],
    }


def build_runtime_cleanup_dry_run(confirmed: bool = False, limit: int = 100) -> Dict[str, Any]:
    return build_runtime_cleanup_report(dry_run=True, confirmed=confirmed, limit=limit)

