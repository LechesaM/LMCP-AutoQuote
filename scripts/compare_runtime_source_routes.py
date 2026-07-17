#!/usr/bin/env python3
"""Compare running and source OpenAPI route sets for LMCP AutoQuote.

This is a read-only reconciliation utility. It consumes captured OpenAPI JSON
files, optionally imports the source FastAPI app for module attribution, and
writes normalized method/path inventories plus a difference matrix.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

DEFAULT_EVIDENCE_DIR = Path("/Users/Shared/LMCP-Recovery-2026-07-15/route-reconciliation")
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

FAILED_ROUTER_PREFIXES = {
    "/smart-harvester-v31": "smart_harvester_v31_router",
    "/real-rfq-harvester-v32": "real_rfq_harvester_v32_router",
    "/real-portal-rfq-extraction-v33": "real_portal_rfq_extraction_v33_router",
    "/structured-rfq-extractor-v34": "structured_rfq_extractor_v34_router",
    "/playwright-live-dom-extractor-v35": "playwright_live_dom_extractor_v35_router",
    "/interactive-playwright-extractor-v36": "interactive_playwright_extractor_v36_router",
    "/deep-rfq-link-extractor-v37": "deep_rfq_link_extractor_v37_router",
    "/interactive-click-deep-extraction-v38": "interactive_click_deep_extraction_v38_router",
    "/true-navigation-extraction-v39": "true_navigation_extraction_v39_router",
    "/tender-form-intelligence": "tender_form_intelligence_router",
    "/sbd-intelligence": "sbd_intelligence_router",
    "/csd-persistent-session": "csd_persistent_session_router",
    "/csd-monthly-refresh": "csd_monthly_refresh_router",
    "/final-automation": "final_automation_router",
}

RISKY_PREFIXES = (
    "/autonomous",
    "/full-autonomous",
    "/v48-autonomous",
    "/v46-auto-submission",
    "/v47-portal-submission",
    "/v47-final-submit",
    "/v47-smart-upload",
    "/final-automation",
    "/rfq-lifecycle",
    "/supply-command",
    "/v50-",
    "/v49",
    "/v47",
    "/v45",
    "/v44",
    "/v43",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def openapi_entries(openapi: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    entries: Dict[str, Dict[str, Any]] = {}
    for path, method_map in (openapi.get("paths") or {}).items():
        if not isinstance(method_map, dict):
            continue
        for method, operation in method_map.items():
            if method.lower() not in HTTP_METHODS:
                continue
            op = operation if isinstance(operation, dict) else {}
            normalized_method = method.upper()
            key = f"{normalized_method} {path}"
            entries[key] = {
                "method": normalized_method,
                "path": path,
                "operation_id": op.get("operationId"),
                "tags": op.get("tags") or [],
                "summary": op.get("summary"),
            }
    return entries


def route_source_map() -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str]], List[str]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    failed: List[Tuple[str, str]] = []
    loaded: List[str] = []
    try:
        module = importlib.import_module("app.main")
        loaded = list(getattr(module, "loaded_routers", []) or [])
        failed = [tuple(item) for item in (getattr(module, "failed_routers", []) or [])]
        app = getattr(module, "app", None)
        for route in getattr(app, "routes", []) or []:
            path = getattr(route, "path", None)
            endpoint = getattr(route, "endpoint", None)
            endpoint_module = getattr(endpoint, "__module__", None)
            endpoint_name = getattr(endpoint, "__name__", None)
            for method in getattr(route, "methods", []) or []:
                if method.lower() in HTTP_METHODS:
                    mapping[f"{method.upper()} {path}"] = {
                        "source_module": endpoint_module,
                        "endpoint": endpoint_name,
                        "route_name": getattr(route, "name", None),
                    }
    except Exception as exc:
        failed.append(("app.main", f"{type(exc).__name__}: {exc}"))
    return mapping, failed, loaded


def run_git_grep(ref: str, needle: str) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "grep", "-n", "--fixed-strings", needle, ref, "--", "app"],
            cwd=str(REPOSITORY),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[:10]
    except Exception:
        return []
    return []


def current_source_hits(path: str) -> List[str]:
    needles = [path, path.rsplit("/", 1)[0] if "/" in path.strip("/") else path]
    hits: List[str] = []
    for needle in dict.fromkeys([n for n in needles if n and n != "/"]):
        try:
            result = subprocess.run(
                ["rg", "-n", "--fixed-strings", needle, "app", "-g", "*.py"],
                cwd=str(REPOSITORY),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
            if result.returncode == 0:
                hits.extend(result.stdout.strip().splitlines()[:8])
        except Exception:
            pass
    return hits[:12]


def historical_hits(path: str, refs: Iterable[str]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    parts = [path]
    if "/" in path.strip("/"):
        parts.append("/" + path.strip("/").split("/", 1)[1])
        parts.append(path.rsplit("/", 1)[-1])
    for ref in refs:
        ref_hits: List[str] = []
        for part in dict.fromkeys([p for p in parts if p and p != "/"]):
            ref_hits.extend(run_git_grep(ref, part))
        if ref_hits:
            result[ref] = ref_hits[:20]
    return result


def failed_router_for_path(path: str, active_failed_routers: Optional[Iterable[str]] = None) -> Optional[str]:
    active_failed = set(active_failed_routers or [])
    for prefix, router in FAILED_ROUTER_PREFIXES.items():
        if path.startswith(prefix) and router in active_failed:
            return router
    return None


def likely_module_from_path(path: str, source_info: Optional[Dict[str, Any]], hits: List[str]) -> Optional[str]:
    if source_info and source_info.get("source_module"):
        return str(source_info.get("source_module"))
    for hit in hits:
        if hit.startswith("app/") and ".py:" in hit:
            return hit.split(":", 1)[0].replace("/", ".").removesuffix(".py")
    return None


def route_is_risky(method: str, path: str) -> bool:
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True
    return any(path.startswith(prefix) for prefix in RISKY_PREFIXES)


def classify_route(
    key: str,
    running_entry: Optional[Dict[str, Any]],
    source_entry: Optional[Dict[str, Any]],
    source_info: Optional[Dict[str, Any]],
    source_hits: List[str],
    hist_hits: Dict[str, List[str]],
    active_failed_routers: Iterable[str],
) -> Tuple[str, str, str, str]:
    method, path = key.split(" ", 1)
    failed_router = failed_router_for_path(path, active_failed_routers)
    if running_entry and not source_entry:
        if failed_router:
            return (
                "IMPORT_FAILURE",
                f"Route prefix belongs to failed source router {failed_router}.",
                "Restart would lose this running route unless the failed router loads in the restart environment.",
                "Fix or validate the failed router before restart.",
            )
        if source_hits:
            return (
                "CONDITIONAL_REGISTRATION",
                "Current source contains matching path text but it is absent from generated source OpenAPI.",
                "Restart may lose this route if registration remains gated or disconnected.",
                "Trace the source registration condition before restart.",
            )
        if hist_hits:
            return (
                "PROCESS_MEMORY_ONLY",
                "Route was found in historical refs but not in generated current source OpenAPI.",
                "Restart would remove this process-memory-only route.",
                "Decide whether the route is obsolete or must be restored.",
            )
        return (
            "RUNNING_ONLY",
            "Route exists in running OpenAPI only and was not found in current source search.",
            "Restart would remove this route.",
            "Search preserved archives or restore only with explicit evidence.",
        )
    if source_entry and not running_entry:
        if failed_router:
            return (
                "UNKNOWN",
                f"Route prefix maps to failed router {failed_router}, but it appears in source OpenAPI.",
                "Unexpected source registration state.",
                "Inspect source route registration.",
            )
        if path.startswith("/v50-") or path.startswith("/v49") or path.startswith("/v48") or path.startswith("/v47") or path.startswith("/v46") or path.startswith("/v45") or path.startswith("/v44") or path.startswith("/v43") or path.startswith("/v40") or path.startswith("/clean-ink-v3"):
            return (
                "SOURCE_ONLY",
                "Current source includes versioned V40-V50 router not present in running process OpenAPI.",
                "Restart would activate this route family.",
                "Review safety of mutating actions before restart; do not invoke mutating endpoints during audit.",
            )
        return (
            "SOURCE_ONLY",
            "Route exists in generated current source OpenAPI only.",
            "Restart would add this route.",
            "Review whether it is expected recovered source or recovery noise.",
        )
    if running_entry and source_entry:
        if running_entry.get("operation_id") != source_entry.get("operation_id") or running_entry.get("tags") != source_entry.get("tags"):
            return (
                "SAME_ROUTE_DIFFERENT_OPERATION",
                "Method/path exists in both sets but operation metadata differs.",
                "Restart may change generated clients or docs for this route.",
                "Review operation IDs and tags if clients depend on them.",
            )
        return (
            "PRESENT_IN_BOTH",
            "Method/path and basic OpenAPI metadata match.",
            "Low route-presence risk.",
            "No route reconciliation action required.",
        )
    return ("UNKNOWN", "No route data available.", "Unknown.", "Inspect manually.")


def build_matrix(
    running: Dict[str, Dict[str, Any]],
    source: Dict[str, Dict[str, Any]],
    source_route_map: Dict[str, Dict[str, Any]],
    refs: Iterable[str],
    active_failed_routers: Iterable[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in sorted(set(running) | set(source)):
        method, path = key.split(" ", 1)
        running_entry = running.get(key)
        source_entry = source.get(key)
        source_info = source_route_map.get(key)
        hits = current_source_hits(path) if running_entry and not source_entry else []
        hist = historical_hits(path, refs) if running_entry and not source_entry else {}
        classification, evidence, restart_risk, action = classify_route(
            key, running_entry, source_entry, source_info, hits, hist, active_failed_routers
        )
        rows.append(
            {
                "method": method,
                "path": path,
                "operation_id": {
                    "running": (running_entry or {}).get("operation_id"),
                    "source": (source_entry or {}).get("operation_id"),
                },
                "running_present": running_entry is not None,
                "source_present": source_entry is not None,
                "running_tags": (running_entry or {}).get("tags") or [],
                "source_tags": (source_entry or {}).get("tags") or [],
                "likely_router_or_module": likely_module_from_path(path, source_info, hits),
                "registration_mechanism": "app.main include_router / OPTIONAL_ROUTERS",
                "environment_flag": None,
                "import_failure": failed_router_for_path(path, active_failed_routers),
                "classification": classification,
                "evidence": evidence,
                "current_source_hits": hits,
                "historical_hits": hist,
                "risky_route": route_is_risky(method, path),
                "restart_risk": restart_risk,
                "recommended_action": action,
                "confidence": "HIGH" if classification in {"IMPORT_FAILURE", "PROCESS_MEMORY_ONLY", "SOURCE_ONLY"} else "MEDIUM",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare running and source OpenAPI method/path route sets.")
    parser.add_argument("--running-openapi", type=Path, default=DEFAULT_EVIDENCE_DIR / "running-openapi.json")
    parser.add_argument("--source-openapi", type=Path, default=DEFAULT_EVIDENCE_DIR / "source-openapi.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--matrix-output", type=Path, default=REPOSITORY / "docs" / "recovery" / "runtime_route_difference_matrix.json")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    running_openapi = load_json(args.running_openapi)
    source_openapi = load_json(args.source_openapi)
    running_entries = openapi_entries(running_openapi)
    source_entries = openapi_entries(source_openapi)
    source_route_map, failed_routers, loaded_routers = route_source_map()
    refs = [
        "v2.0-operational-baseline",
        "recovery-2026-07-15",
        "integration-v1.2-enterprise-base",
        "origin/release/v1.1",
        "release/v1.1",
        "recovery/rfq-quote-pack-bridge",
    ]
    active_failed_routers = [name for name, _message in failed_routers]
    matrix = build_matrix(running_entries, source_entries, source_route_map, refs, active_failed_routers)

    running_method_paths = list(running_entries.values())
    source_method_paths = list(source_entries.values())
    write_json(args.output_dir / "running-method-paths.json", running_method_paths)
    write_json(args.output_dir / "source-method-paths.json", source_method_paths)
    write_json(args.matrix_output, matrix)

    summary = {
        "generated_at": utc_now(),
        "repository": str(REPOSITORY),
        "running_openapi": str(args.running_openapi),
        "source_openapi": str(args.source_openapi),
        "running_paths": len(running_openapi.get("paths") or {}),
        "source_paths": len(source_openapi.get("paths") or {}),
        "running_method_path_count": len(running_entries),
        "source_method_path_count": len(source_entries),
        "running_only_count": sum(1 for row in matrix if row["running_present"] and not row["source_present"]),
        "source_only_count": sum(1 for row in matrix if row["source_present"] and not row["running_present"]),
        "different_operation_count": sum(1 for row in matrix if row["classification"] == "SAME_ROUTE_DIFFERENT_OPERATION"),
        "loaded_router_count": len(loaded_routers),
        "failed_router_count": len(failed_routers),
        "failed_routers": failed_routers,
    }
    write_json(args.output_dir / "route-reconciliation-summary.json", summary)

    if args.verbose:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
