from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(os.getenv("LMCP_BASE_DIR", "/app"))
RUNTIME_DIR = BASE_DIR / "runtime"
MONTHLY_QUOTES_DIR = BASE_DIR / "monthly_quotes"
LOGS_DIR = BASE_DIR / "logs"

ARCHIVE_ROOT = RUNTIME_DIR / "archives"
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

ARCHIVE_INDEX_FILE = ARCHIVE_ROOT / "archive_index.json"
LAST_RUN_FILE = ARCHIVE_ROOT / "last_archive_run.json"

DEFAULT_DAYS_TO_KEEP_LIVE = int(os.getenv("LMCP_ARCHIVE_DAYS_TO_KEEP_LIVE", "7"))
DEFAULT_MIN_FREE_GB = float(os.getenv("LMCP_MIN_FREE_GB", "10"))
DEFAULT_KEEP_PROOFS_LIVE_DAYS = int(os.getenv("LMCP_KEEP_PROOFS_LIVE_DAYS", "30"))

PROTECTED_DIR_NAMES = {
    "archives",
    "playwright_profiles",
    "proof_center",
}

PROOF_PATH_MARKERS = {
    "proof",
    "proofs",
    "proof_center",
    "final_submission_v47_5/proofs",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _append_index(record: Dict[str, Any]) -> None:
    index = _read_json(ARCHIVE_INDEX_FILE, [])
    if not isinstance(index, list):
        index = []
    index.append(record)
    _write_json(ARCHIVE_INDEX_FILE, index[-1000:])


def _free_space_gb(path: Path = BASE_DIR) -> float:
    target = path if path.exists() else Path("/")
    usage = shutil.disk_usage(str(target))
    return round(usage.free / (1024 ** 3), 2)


def _safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except Exception:
        return path.name


def _is_protected(path: Path) -> bool:
    parts = set(path.parts)
    if parts.intersection(PROTECTED_DIR_NAMES):
        return True
    return False


def _is_proof_related(path: Path) -> bool:
    lowered = str(path).lower().replace("\\", "/")
    return any(marker in lowered for marker in PROOF_PATH_MARKERS)


def _older_than(path: Path, days: int) -> bool:
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        return modified < cutoff
    except Exception:
        return False


def _collect_files(root: Path, days_to_keep_live: int, keep_proofs_live_days: int) -> List[Path]:
    if not root.exists():
        return []

    files: List[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if _is_protected(path):
            continue

        if _is_proof_related(path):
            if _older_than(path, keep_proofs_live_days):
                files.append(path)
            continue

        if _older_than(path, days_to_keep_live):
            files.append(path)

    return files


def _zip_files(files: Iterable[Path], source_root: Path, archive_path: Path) -> Dict[str, Any]:
    file_list = list(files)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    skipped = 0
    errors: List[Dict[str, str]] = []

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in file_list:
            try:
                if not path.exists() or not path.is_file():
                    skipped += 1
                    continue

                arcname = _safe_relative(path, source_root)
                zf.write(path, arcname=arcname)
                added += 1
            except Exception as exc:
                errors.append({"path": str(path), "error": str(exc)})

    return {
        "archive_path": str(archive_path),
        "candidate_count": len(file_list),
        "added_count": added,
        "skipped_count": skipped,
        "error_count": len(errors),
        "errors": errors[:50],
        "archive_size_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
    }


def _delete_archived_files(files: Iterable[Path], archive_result: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"deleted_count": 0, "failed_count": 0, "dry_run": True, "failures": []}

    archive_path = Path(str(archive_result.get("archive_path", "")))
    if not archive_path.exists() or int(archive_result.get("added_count") or 0) <= 0:
        return {
            "deleted_count": 0,
            "failed_count": 0,
            "dry_run": False,
            "failures": [{"error": "Archive was not created successfully. Originals were not deleted."}],
        }

    deleted = 0
    failures: List[Dict[str, str]] = []

    for path in files:
        try:
            if path.exists() and path.is_file():
                path.unlink()
                deleted += 1
        except Exception as exc:
            failures.append({"path": str(path), "error": str(exc)})

    return {
        "deleted_count": deleted,
        "failed_count": len(failures),
        "dry_run": False,
        "failures": failures[:50],
    }


def _remove_empty_dirs(root: Path, dry_run: bool) -> Dict[str, Any]:
    if not root.exists():
        return {"removed_count": 0, "dry_run": dry_run}

    removed = 0

    for path in sorted([p for p in root.rglob("*") if p.is_dir()], key=lambda p: len(p.parts), reverse=True):
        if _is_protected(path):
            continue
        try:
            if not any(path.iterdir()):
                if not dry_run:
                    path.rmdir()
                removed += 1
        except Exception:
            pass

    return {"removed_count": removed, "dry_run": dry_run}


def run_self_clean_archive(
    days_to_keep_live: int = DEFAULT_DAYS_TO_KEEP_LIVE,
    keep_proofs_live_days: int = DEFAULT_KEEP_PROOFS_LIVE_DAYS,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    dry_run: bool = False,
) -> Dict[str, Any]:
    started_at = _now()
    free_before = _free_space_gb(BASE_DIR)

    roots = {
        "runtime": RUNTIME_DIR,
        "monthly_quotes": MONTHLY_QUOTES_DIR,
        "logs": LOGS_DIR,
    }

    source_results: Dict[str, Any] = {}
    total_candidates = 0
    total_archived = 0
    total_deleted = 0

    run_dir = ARCHIVE_ROOT / datetime.now(timezone.utc).strftime("%Y-%m")
    run_dir.mkdir(parents=True, exist_ok=True)

    for name, root in roots.items():
        files = _collect_files(root, days_to_keep_live=days_to_keep_live, keep_proofs_live_days=keep_proofs_live_days)
        total_candidates += len(files)

        if not files:
            source_results[name] = {
                "root": str(root),
                "candidate_count": 0,
                "message": "No files old enough to archive.",
            }
            continue

        archive_path = run_dir / f"{name}__archive__{_stamp()}.zip"
        archive_result = _zip_files(files, source_root=root, archive_path=archive_path)
        delete_result = _delete_archived_files(files, archive_result, dry_run=dry_run)
        empty_dir_result = _remove_empty_dirs(root, dry_run=dry_run)

        total_archived += int(archive_result.get("added_count") or 0)
        total_deleted += int(delete_result.get("deleted_count") or 0)

        source_results[name] = {
            "root": str(root),
            "archive": archive_result,
            "cleanup": delete_result,
            "empty_dirs": empty_dir_result,
        }

    free_after = _free_space_gb(BASE_DIR)

    status = "ok"
    if free_after < min_free_gb:
        status = "warning_low_disk"
    if dry_run:
        status = "dry_run"

    result = {
        "status": status,
        "service_version": "LMCP_SELF_CLEAN_ARCHIVE_V1",
        "started_at": started_at,
        "finished_at": _now(),
        "dry_run": dry_run,
        "settings": {
            "days_to_keep_live": days_to_keep_live,
            "keep_proofs_live_days": keep_proofs_live_days,
            "min_free_gb": min_free_gb,
            "base_dir": str(BASE_DIR),
            "archive_root": str(ARCHIVE_ROOT),
        },
        "summary": {
            "free_before_gb": free_before,
            "free_after_gb": free_after,
            "freed_estimate_gb": round(free_after - free_before, 2),
            "candidate_files": total_candidates,
            "archived_files": total_archived,
            "deleted_original_files": total_deleted,
        },
        "sources": source_results,
    }

    _write_json(LAST_RUN_FILE, result)
    _append_index(result)

    return result


def get_self_clean_archive_status(limit: int = 20) -> Dict[str, Any]:
    index = _read_json(ARCHIVE_INDEX_FILE, [])
    if not isinstance(index, list):
        index = []

    last = _read_json(LAST_RUN_FILE, {})
    archives = []
    try:
        archives = [
            {
                "path": str(p),
                "name": p.name,
                "size_bytes": p.stat().st_size,
                "modified_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            }
            for p in sorted(ARCHIVE_ROOT.rglob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
        ]
    except Exception:
        archives = []

    return {
        "status": "ok",
        "service_version": "LMCP_SELF_CLEAN_ARCHIVE_V1",
        "free_space_gb": _free_space_gb(BASE_DIR),
        "last_run": last,
        "recent_runs": index[-limit:],
        "archives": archives[:limit],
        "archive_root": str(ARCHIVE_ROOT),
        "updated_at": _now(),
    }


if __name__ == "__main__":
    print(json.dumps(run_self_clean_archive(), indent=2))
