from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_PROOF_LOG = Path("/private/tmp/lmcp_runtime/logs/controlled_runtime_proof.json")
DEFAULT_ENDPOINT_LOG = Path("/private/tmp/lmcp_runtime/logs/controlled_runtime_endpoints.json")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_paths(entries: Any) -> List[str]:
    paths: List[str] = []
    for item in entries if isinstance(entries, list) else []:
        if isinstance(item, dict):
            path = _clean(item.get("path"))
            if path:
                paths.append(path)
        elif isinstance(item, str) and item.strip():
            paths.append(item.strip())
    return paths


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def _print_kv(label: str, value: Any) -> None:
    if value is None or value == "":
        rendered = "n/a"
    else:
        rendered = str(value)
    print(f"{label:<28} {rendered}")


def show_controlled_proof_report(*, log_path: Optional[str] = None) -> Dict[str, Any]:
    path = Path(log_path).expanduser() if log_path else DEFAULT_PROOF_LOG
    report = _load_json(path)
    endpoint_path = DEFAULT_ENDPOINT_LOG if path == DEFAULT_PROOF_LOG else path.with_name("controlled_runtime_endpoints.json")
    endpoint_report: Dict[str, Any] = {}
    if endpoint_path.exists():
        try:
            endpoint_report = _load_json(endpoint_path)
        except Exception:
            endpoint_report = {}
    health = endpoint_report.get("health") if isinstance(endpoint_report.get("health"), dict) else {}
    effective = endpoint_report.get("effective_status") if isinstance(endpoint_report.get("effective_status"), dict) else {}
    workflow = endpoint_report.get("workflow_health") if isinstance(endpoint_report.get("workflow_health"), dict) else {}
    if not health:
        health = report.get("health") if isinstance(report.get("health"), dict) else {}
    if not effective:
        effective = report.get("effective_status") if isinstance(report.get("effective_status"), dict) else {}
    if not workflow:
        workflow = report.get("workflow_health") if isinstance(report.get("workflow_health"), dict) else {}
    quote_pack = report.get("quote_pack") if isinstance(report.get("quote_pack"), dict) else {}
    pricing = report.get("pricing_schedule") if isinstance(report.get("pricing_schedule"), dict) else {}
    submission_pack = report.get("submission_pack") if isinstance(report.get("submission_pack"), dict) else {}
    safety = report.get("safety") if isinstance(report.get("safety"), dict) else {}

    pricing_files = _pick_paths(pricing.get("files"))
    submission_files = _pick_paths(submission_pack.get("submission_pack_files"))

    return {
        "log_path": str(path),
        "endpoint_log_path": str(endpoint_path),
        "runtime_dir": _clean(report.get("runtime_dir") or health.get("runtime_dir")),
        "controlled_status": _clean(effective.get("effective_system_status") or workflow.get("controlled_status")),
        "workflow_checks_passed": sum(1 for value in (workflow.get("workflow_checks") or {}).values() if bool(value))
        if isinstance(workflow.get("workflow_checks"), dict)
        else 0,
        "quote_pack_pdf": _clean(quote_pack.get("pdf_path")),
        "pricing_files": pricing_files,
        "submission_manifest": _clean(submission_pack.get("submission_pack_manifest_path")),
        "submission_pack_ready_count": submission_pack.get("submission_pack_ready_count", 0),
        "safety": {
            "no_portal_upload": bool(safety.get("no_portal_upload", False)),
            "no_email_send": bool(safety.get("no_email_send", False)),
            "no_final_submit": bool(safety.get("no_final_submit", False)),
        },
        "health": health,
        "effective_status": effective,
        "workflow_health": workflow,
        "pricing_schedule": pricing,
        "submission_pack": submission_pack,
        "submission_files": submission_files,
    }


def _print_summary(report: Dict[str, Any]) -> None:
    safety = report.get("safety") if isinstance(report.get("safety"), dict) else {}
    health = report.get("health") if isinstance(report.get("health"), dict) else {}
    effective = report.get("effective_status") if isinstance(report.get("effective_status"), dict) else {}
    workflow = report.get("workflow_health") if isinstance(report.get("workflow_health"), dict) else {}
    router_health = workflow.get("router_health") if isinstance(workflow.get("router_health"), dict) else {}
    workflow_checks = workflow.get("workflow_checks") if isinstance(workflow.get("workflow_checks"), dict) else {}

    print("Controlled Proof Report")
    print("=======================")
    _print_kv("Log path", report.get("log_path"))
    _print_kv("Endpoint log", report.get("endpoint_log_path"))
    _print_kv("Runtime dir", report.get("runtime_dir"))
    _print_kv("Controlled status", report.get("controlled_status"))
    _print_kv("Workflow checks passed", f"{report.get('workflow_checks_passed', 0)} / {len(workflow_checks) or 7}")

    _print_section("Runtime Health")
    _print_kv("Health status", health.get("status"))
    _print_kv("Effective system status", effective.get("effective_system_status"))
    _print_kv("Workflow status", workflow.get("status"))
    loaded_routers = health.get("loaded_routers_count")
    if loaded_routers is None:
        loaded_routers = router_health.get("loaded_routers_count")
    failed_routers = health.get("failed_routers_count")
    if failed_routers is None:
        failed_routers = router_health.get("failed_routers_count")
    duplicate_routes = health.get("duplicate_routes_count")
    if duplicate_routes is None:
        duplicate_routes = router_health.get("duplicate_routes_count")
    _print_kv("Loaded routers", loaded_routers if loaded_routers is not None else 0)
    _print_kv("Failed routers", failed_routers if failed_routers is not None else 0)
    _print_kv("Duplicate routes", duplicate_routes if duplicate_routes is not None else 0)

    _print_section("Artifacts")
    _print_kv("Quote pack PDF", report.get("quote_pack_pdf"))
    _print_kv("Pricing files", ", ".join(report.get("pricing_files", [])) or "none")
    _print_kv("Submission manifest", report.get("submission_manifest"))
    _print_kv("Submission pack ready", report.get("submission_pack_ready_count", 0))

    _print_section("Workflow Checks")
    if workflow_checks:
        for name, passed in workflow_checks.items():
            _print_kv(name, "passed" if bool(passed) else "failed")
    else:
        _print_kv("workflow_checks", "n/a")

    _print_section("Safety")
    _print_kv("Portal upload", "blocked" if bool(safety.get("no_portal_upload", False)) else "allowed")
    _print_kv("Email send", "blocked" if bool(safety.get("no_email_send", False)) else "allowed")
    _print_kv("Final submit", "blocked" if bool(safety.get("no_final_submit", False)) else "allowed")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Print a compact summary of the controlled proof log.")
    parser.add_argument("--log-path", default=None, help="Optional path to controlled_runtime_proof.json.")
    parser.add_argument("--json", action="store_true", help="Print the full parsed report as JSON.")
    args = parser.parse_args(argv)

    report = show_controlled_proof_report(log_path=args.log_path)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
