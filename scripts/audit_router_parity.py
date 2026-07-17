#!/usr/bin/env python3
"""Read-only source/runtime router parity audit for LMCP AutoQuote.

The script imports the active FastAPI module without starting a server, records
router registration results, and optionally compares them with a captured
running OpenAPI document. It intentionally does not issue mutating HTTP
requests, start workers, restart Docker, or modify runtime stores.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_MAIN_MODULE = "app.main"
DEFAULT_RUNNING_OPENAPI = Path(
    "/Users/Shared/LMCP-Recovery-2026-07-15/source-runtime-parity/running-openapi.json"
)

if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_command(args: List[str], cwd: Path = REPOSITORY, timeout: int = 20) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": args,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover - defensive diagnostics
        return {
            "command": args,
            "exit_code": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def git_info() -> Dict[str, Any]:
    branch = run_command(["git", "branch", "--show-current"])
    commit = run_command(["git", "log", "-1", "--oneline"])
    status = run_command(["git", "status", "--short"])
    return {
        "branch": branch.get("stdout"),
        "commit": commit.get("stdout"),
        "working_tree_clean": status.get("stdout") == "",
        "status_short": status.get("stdout", "").splitlines(),
        "errors": [x for x in (branch.get("stderr"), commit.get("stderr"), status.get("stderr")) if x],
    }


def sha256_file(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def file_info(path: Path) -> Dict[str, Any]:
    try:
        stat = path.stat()
        return {
            "path": str(path),
            "exists": True,
            "size": stat.st_size,
            "modified_at": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(),
            "sha256": sha256_file(path),
        }
    except OSError as exc:
        return {
            "path": str(path),
            "exists": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def route_inventory(app: Any) -> List[Dict[str, Any]]:
    routes: List[Dict[str, Any]] = []
    for route in getattr(app, "routes", []) or []:
        methods = sorted(getattr(route, "methods", []) or [])
        routes.append(
            {
                "path": getattr(route, "path", None),
                "name": getattr(route, "name", None),
                "methods": methods,
                "endpoint": getattr(getattr(route, "endpoint", None), "__name__", None),
            }
        )
    return routes


def duplicate_routes(routes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keys: List[Tuple[str, str]] = []
    for route in routes:
        path = str(route.get("path") or "")
        for method in route.get("methods") or []:
            keys.append((method, path))
    counts = Counter(keys)
    return [
        {"method": method, "path": path, "count": count}
        for (method, path), count in sorted(counts.items())
        if count > 1
    ]


def classify_failure(message: str, traceback_text: str = "") -> str:
    haystack = f"{message}\n{traceback_text}"
    if "dict | None" in haystack or "eval_type_backport" in haystack or "unsupported operand type(s) for |" in haystack:
        return "PYTHON39_ANNOTATION"
    if "No module named" in haystack or "ModuleNotFoundError" in haystack:
        return "MISSING_MODULE"
    if "cannot import name" in haystack or "ImportError" in haystack:
        return "STALE_IMPORT"
    if "circular import" in haystack:
        return "CIRCULAR_IMPORT"
    if (
        "Operation not permitted: '/app'" in haystack
        or "Read-only file system: '/app'" in haystack
        or "No such file or directory: '/app'" in haystack
    ):
        return "ROUTER_REGISTRY_MISMATCH"
    if "optional" in haystack.lower():
        return "OPTIONAL_DEPENDENCY"
    return "OTHER"


def minimal_repair(classification: str) -> str:
    repairs = {
        "PYTHON39_ANNOTATION": "Replace evaluated PEP 604 annotations with typing.Optional/Dict or ensure postponed evaluation is honored by the framework.",
        "MISSING_MODULE": "Restore the missing module or mark the router optional only if it is genuinely non-mandatory.",
        "STALE_IMPORT": "Update the import target to the current module/function name.",
        "CIRCULAR_IMPORT": "Move shared types/helpers to a dependency-light module and import lazily where needed.",
        "ROUTER_REGISTRY_MISMATCH": "Run in the same container path context or remove import-time hard-coded /app filesystem access.",
        "OPTIONAL_DEPENDENCY": "Install or guard the optional dependency without hiding mandatory router failures.",
        "OTHER": "Inspect traceback and repair the narrow failing line.",
    }
    return repairs.get(classification, repairs["OTHER"])


def extract_failure_details(failed_routers: Iterable[Tuple[str, str]], optional_routers: Iterable[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
    module_by_name = {name: module_path for name, module_path, _attribute in optional_routers}
    details: List[Dict[str, Any]] = []
    for router_name, message in failed_routers:
        module_path = module_by_name.get(router_name)
        source_file = None
        failing_line = None
        traceback_text = ""
        if module_path:
            try:
                spec = importlib.util.find_spec(module_path)  # type: ignore[attr-defined]
                if spec and spec.origin:
                    source_file = spec.origin
            except Exception:
                pass
        classification = classify_failure(message, traceback_text)
        details.append(
            {
                "router": router_name,
                "module": module_path,
                "source_file": source_file,
                "error_type": None,
                "message": message,
                "failing_line": failing_line,
                "classification": classification,
                "minimal_safe_repair": minimal_repair(classification),
            }
        )
    return details


def openapi_method_path_set(openapi: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    for path, methods in (openapi.get("paths") or {}).items():
        if isinstance(methods, dict):
            for method in methods:
                if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}:
                    result.append(f"{method.upper()} {path}")
    return sorted(result)


def route_method_path_set(routes: Iterable[Dict[str, Any]]) -> List[str]:
    result: List[str] = []
    for route in routes:
        path = route.get("path")
        for method in route.get("methods") or []:
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                result.append(f"{method} {path}")
    return sorted(result)


def load_running_openapi(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {"available": False, "reason": "not requested"}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        methods = openapi_method_path_set(data)
        return {
            "available": True,
            "path": str(path),
            "path_count": len(data.get("paths") or {}),
            "method_path_count": len(methods),
            "method_paths": methods,
        }
    except Exception as exc:
        return {
            "available": False,
            "path": str(path),
            "reason": f"{type(exc).__name__}: {exc}",
        }


def audit(main_module: str, expected_loaded: Optional[int], running_openapi: Optional[Path]) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "generated_at": utc_now(),
        "repository": str(REPOSITORY),
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "version_info": list(sys.version_info[:3]),
            "platform": platform.platform(),
        },
        "git": git_info(),
        "environment": {
            "cwd": os.getcwd(),
            "pythonpath": os.environ.get("PYTHONPATH"),
            "pythondontwritebytecode": os.environ.get("PYTHONDONTWRITEBYTECODE"),
            "pythonpycacheprefix": os.environ.get("PYTHONPYCACHEPREFIX"),
        },
        "source_files": {
            "app_main": file_info(REPOSITORY / "app" / "main.py"),
            "rfq_lifecycle_api": file_info(REPOSITORY / "app" / "api" / "rfq_lifecycle_api.py"),
        },
        "main_module": main_module,
        "expected_loaded": expected_loaded,
        "safety": {
            "server_started": False,
            "mutating_requests_sent": False,
            "docker_restarted": False,
            "runtime_store_modified_by_script": False,
        },
    }

    try:
        module = importlib.import_module(main_module)
        app = getattr(module, "app", None)
        routes = route_inventory(app)
        duplicates = duplicate_routes(routes)
        loaded_routers = list(getattr(module, "loaded_routers", []) or [])
        failed_routers = [tuple(item) for item in (getattr(module, "failed_routers", []) or [])]
        optional_routers = list(getattr(module, "OPTIONAL_ROUTERS", []) or [])
        source_method_paths = route_method_path_set(routes)
        running = load_running_openapi(running_openapi)
        report.update(
            {
                "imported": True,
                "app_version": getattr(module, "APP_VERSION", None),
                "loaded_routers": loaded_routers,
                "loaded_routers_count": len(loaded_routers),
                "failed_routers_count": len(failed_routers),
                "failed_routers": extract_failure_details(failed_routers, optional_routers),
                "route_count": len(routes),
                "duplicate_routes_count": len(duplicates),
                "duplicate_routes": duplicates,
                "source_method_path_count": len(source_method_paths),
                "source_method_paths": source_method_paths,
                "running_openapi": running,
            }
        )
        if running.get("available"):
            running_methods = set(running.get("method_paths") or [])
            source_methods = set(source_method_paths)
            report["openapi_parity"] = {
                "running_minus_source": sorted(running_methods - source_methods),
                "source_minus_running": sorted(source_methods - running_methods),
                "running_minus_source_count": len(running_methods - source_methods),
                "source_minus_running_count": len(source_methods - running_methods),
            }
        else:
            report["openapi_parity"] = {"available": False, "reason": running.get("reason")}
        report["expected_loaded_match"] = expected_loaded is None or len(loaded_routers) == expected_loaded
    except Exception as exc:
        report.update(
            {
                "imported": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    return report


def write_json(report: Dict[str, Any], output: Optional[Path]) -> None:
    text = json.dumps(report, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit LMCP router parity without starting a server.")
    parser.add_argument("--output", type=Path, help="Path to write JSON report")
    parser.add_argument("--verbose", action="store_true", help="Print a concise console summary")
    parser.add_argument("--expected-loaded", type=int, default=None, help="Expected loaded router count")
    parser.add_argument("--main-module", default=DEFAULT_MAIN_MODULE, help="Application module to import")
    parser.add_argument(
        "--running-openapi",
        type=Path,
        default=DEFAULT_RUNNING_OPENAPI if DEFAULT_RUNNING_OPENAPI.exists() else None,
        help="Captured running OpenAPI JSON for route comparison",
    )
    args = parser.parse_args()

    report = audit(args.main_module, args.expected_loaded, args.running_openapi)
    write_json(report, args.output)

    if args.verbose:
        print("router parity audit")
        print("  imported:", report.get("imported"))
        print("  app_version:", report.get("app_version"))
        print("  loaded_routers_count:", report.get("loaded_routers_count"))
        print("  failed_routers_count:", report.get("failed_routers_count"))
        print("  duplicate_routes_count:", report.get("duplicate_routes_count"))
        parity = report.get("openapi_parity") or {}
        if parity.get("available") is False:
            print("  openapi_parity:", parity.get("reason"))
        else:
            print("  running_minus_source_count:", parity.get("running_minus_source_count"))
            print("  source_minus_running_count:", parity.get("source_minus_running_count"))
    return 0 if report.get("imported") else 1


if __name__ == "__main__":
    raise SystemExit(main())
