from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now

_JSONL_FILENAMES = (
    "workflow_events.jsonl",
    "workflow_state.jsonl",
    "approvals.jsonl",
    "submission_reviews.jsonl",
    "submission_proofs.jsonl",
)


class RuntimeDiagnosticsReport(StrictBaseModel):
    status: str = "healthy"
    checked_at: Any = None
    runtime_root_ok: bool = True
    missing_directories: List[str]
    directory_checks: Dict[str, Dict[str, Any]]
    db_file: Dict[str, Any]
    disk_usage: Dict[str, Any]
    jsonl_integrity: Dict[str, Any]
    warnings: List[str]


def _dir_check(path: Path) -> Dict[str, Any]:
    return {
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "writable": path.exists() and path.is_dir() and (path.stat().st_mode & 0o222) != 0,
    }


def _check_jsonl(path: Path) -> Dict[str, Any]:
    integrity = {
        "file": path.name,
        "exists": path.exists(),
        "valid": True,
        "record_count": 0,
        "invalid_lines": [],
    }
    if not path.exists():
        return integrity
    try:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            integrity["record_count"] += 1
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    integrity["valid"] = False
                    integrity["invalid_lines"].append(line_no)
            except Exception:
                integrity["valid"] = False
                integrity["invalid_lines"].append(line_no)
    except Exception:
        integrity["valid"] = False
    return integrity


def _disk_usage(path: Path) -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
        used_ratio = float(usage.used) / float(usage.total) if usage.total else 0.0
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_ratio": round(used_ratio, 4),
            "warning": used_ratio >= 0.9,
        }
    except Exception:
        return {
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "used_ratio": 0.0,
            "warning": True,
        }


def get_runtime_diagnostics(paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    paths = paths or get_runtime_paths()
    directory_checks = {key: _dir_check(path) for key, path in {
        "runtime_root": paths.runtime_root,
        "logs_dir": paths.logs_dir,
        "manual_production_dir": paths.manual_production_dir,
        "health_dir": paths.health_dir,
        "locks_dir": paths.locks_dir,
        "audit_trail_dir": paths.audit_trail_dir,
        "submission_history_dir": paths.submission_history_dir,
    }.items()}
    missing_directories = [name for name, details in directory_checks.items() if not details["exists"]]
    jsonl_integrity = {}
    for filename in _JSONL_FILENAMES:
        jsonl_integrity[filename] = _check_jsonl(paths.manual_production_file(filename))
    db_path = paths.manual_production_db_path
    db_file = {
        "exists": db_path.exists(),
        "is_file": db_path.is_file(),
        "size_bytes": db_path.stat().st_size if db_path.exists() and db_path.is_file() else 0,
        "readable": db_path.exists() and db_path.is_file() and db_path.stat().st_size >= 0,
    }
    warnings: List[str] = []
    if missing_directories:
        warnings.append("Missing runtime directories detected")
    if any(not item["valid"] for item in jsonl_integrity.values()):
        warnings.append("One or more JSONL files failed integrity checks")
    if db_file["exists"] and db_file["size_bytes"] == 0:
        warnings.append("Database file exists but is empty")
    disk_usage = _disk_usage(paths.runtime_root)
    if disk_usage["warning"]:
        warnings.append("Disk usage is above the safe threshold")
    status = "healthy" if not warnings else "degraded"
    return RuntimeDiagnosticsReport(
        status=status,
        checked_at=utc_now(),
        runtime_root_ok=paths.runtime_root.exists() and paths.runtime_root.is_dir(),
        missing_directories=missing_directories,
        directory_checks=directory_checks,
        db_file=db_file,
        disk_usage=disk_usage,
        jsonl_integrity=jsonl_integrity,
        warnings=warnings,
    ).to_jsonable_dict()
