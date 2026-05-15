from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter


router = APIRouter(prefix="/api/system", tags=["stable-system"])

BASE_DIR = Path(__file__).resolve().parents[2]

SAFE_RUNTIME_DIRS: Dict[str, Path] = {
    "runtime": BASE_DIR / "runtime",
    "rfq_lifecycle": BASE_DIR / "runtime" / "rfq_lifecycle",
    "submission_proofs": BASE_DIR / "runtime" / "submission_proofs",
    "portal_submission": BASE_DIR / "runtime" / "portal_submission",
    "proof_center": BASE_DIR / "runtime" / "proof_center",
    "monthly_quotes": BASE_DIR / "monthly_quotes",
}

SAFETY_FLAGS: Dict[str, bool] = {
    "no_email_send": True,
    "no_portal_upload": True,
    "no_final_submit": True,
    "controlled_dry_run_only": True,
    "no_captcha_bypass": True,
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _main_module() -> Any:
    return sys.modules.get("app.main") or sys.modules.get("main")


def _app_version() -> str:
    main_module = _main_module()
    version = getattr(main_module, "APP_VERSION", None)
    return str(version) if version else "unknown"


def _safe_text(value: Any, max_length: int = 500) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _router_failures(raw_failures: Iterable[Any]) -> List[Dict[str, str]]:
    failures: List[Dict[str, str]] = []
    for failure in raw_failures:
        if isinstance(failure, tuple) and len(failure) >= 2:
            router_name, error = failure[0], failure[1]
        else:
            router_name, error = "unknown", failure

        failures.append(
            {
                "router": _safe_text(router_name, 160),
                "error": _safe_text(error),
            }
        )
    return failures


def _directory_stats(path: Path) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "file_count": 0,
        "directory_count": 0,
        "total_bytes": 0,
        "scan_errors": [],
    }

    if not stats["is_dir"]:
        return stats

    scan_errors: List[str] = []
    try:
        for child in path.rglob("*"):
            try:
                if child.is_dir():
                    stats["directory_count"] += 1
                elif child.is_file():
                    stats["file_count"] += 1
                    stats["total_bytes"] += child.stat().st_size
            except OSError as exc:
                if len(scan_errors) < 5:
                    scan_errors.append(_safe_text(exc, 240))
    except OSError as exc:
        scan_errors.append(_safe_text(exc, 240))

    stats["scan_errors"] = scan_errors
    return stats


def _runtime_payload() -> Dict[str, Any]:
    directories = {
        name: _directory_stats(path)
        for name, path in SAFE_RUNTIME_DIRS.items()
    }
    return {
        "status": "ok",
        "timestamp": _timestamp(),
        "directory_count": len(directories),
        "directories": directories,
    }


def _routes_payload() -> Dict[str, Any]:
    main_module = _main_module()
    loaded_routers = list(getattr(main_module, "loaded_routers", []) or [])
    failed_routers = _router_failures(getattr(main_module, "failed_routers", []) or [])

    return {
        "status": "ok",
        "timestamp": _timestamp(),
        "loaded_routers": loaded_routers,
        "failed_routers": failed_routers,
        "counts": {
            "loaded": len(loaded_routers),
            "failed": len(failed_routers),
        },
    }


def _health_payload() -> Dict[str, Any]:
    runtime = _runtime_payload()
    runtime_directories_present = {
        name: bool(info["exists"] and info["is_dir"])
        for name, info in runtime["directories"].items()
    }

    return {
        "status": "ok",
        "service": "LMCP AutoQuote System",
        "version": _app_version(),
        "backend_alive": True,
        "timestamp": _timestamp(),
        "runtime_directories_present": runtime_directories_present,
        "all_runtime_directories_present": all(runtime_directories_present.values()),
    }


def _safety_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": _timestamp(),
        **SAFETY_FLAGS,
        "safety": dict(SAFETY_FLAGS),
    }


@router.get("/health")
def system_health() -> Dict[str, Any]:
    return _health_payload()


@router.get("/routes")
def system_routes() -> Dict[str, Any]:
    return _routes_payload()


@router.get("/runtime")
def system_runtime() -> Dict[str, Any]:
    return _runtime_payload()


@router.get("/safety")
def system_safety() -> Dict[str, Any]:
    return _safety_payload()


@router.get("/summary")
def system_summary() -> Dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": _timestamp(),
        "health": _health_payload(),
        "routes": _routes_payload(),
        "runtime": _runtime_payload(),
        "safety": _safety_payload(),
    }
