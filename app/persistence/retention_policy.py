from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths


RETENTION_WINDOWS_DAYS = {
    "audit_events": 3650,
    "workflow_events": 730,
    "operator_actions": 730,
    "telemetry_snapshots": 90,
    "runtime_logs": 90,
    "incidents": 3650,
    "backups": 30,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_retention_policy() -> Dict[str, Any]:
    paths = get_runtime_paths()
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "windows_days": dict(RETENTION_WINDOWS_DAYS),
        "paths": {
            "audit_trail_dir": str(paths.audit_trail_dir),
            "manual_production_dir": str(paths.manual_production_dir),
            "logs_dir": str(paths.logs_dir),
            "backups_dir": str(paths.backups_dir),
        },
        "dry_run_only": True,
    }


def run_retention_dry_run(*, dry_run: bool = True, confirm: bool = False) -> Dict[str, Any]:
    policy = get_retention_policy()
    would_delete = []
    for label, days in RETENTION_WINDOWS_DAYS.items():
        would_delete.append({"category": label, "retention_days": days, "action": "archive_or_delete"})
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "dry_run": bool(dry_run),
        "confirmed": bool(confirm),
        "would_delete": would_delete,
        "deleted": [] if dry_run or not confirm else would_delete,
        "policy": policy,
    }


def evaluate_retention_readiness() -> Dict[str, Any]:
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "retention_windows_days": dict(RETENTION_WINDOWS_DAYS),
        "requires_explicit_confirmation": True,
    }

