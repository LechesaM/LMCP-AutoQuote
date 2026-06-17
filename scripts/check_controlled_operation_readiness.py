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

from app.core.runtime_paths import get_runtime_paths
from app.pilot import build_pilot_readiness_report, get_pilot_execution_metadata, get_pilot_signoffs, get_pilot_summary


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _path_exists(path: Path) -> bool:
    return path.exists()


def _evaluate_thresholds(report: Dict[str, Any], summary: Dict[str, Any], signoffs: List[Dict[str, Any]]) -> Dict[str, Any]:
    readiness_score = float(report.get("pilot_readiness_score", 0) or 0)
    total_runs = int(summary.get("total_runs", 0) or 0)
    successful_runs = int(summary.get("successful_runs", 0) or 0)
    failed_runs = int(summary.get("failed_runs", 0) or 0)
    proof_signoffs = sum(1 for item in signoffs if _clean(item.get("signoff_type")) == "proof" and _clean(item.get("signoff_status")) == "signed")
    approval_signoffs = sum(1 for item in signoffs if _clean(item.get("signoff_type")) == "approval" and _clean(item.get("signoff_status")) == "signed")

    blockers: List[str] = []
    if readiness_score < 80:
        blockers.append("pilot readiness score must be at least 80")
    if total_runs < 1:
        blockers.append("at least one pilot run must be recorded")
    if successful_runs < 1:
        blockers.append("at least one successful pilot run must be recorded")
    if failed_runs > 0 and total_runs < 3:
        blockers.append("failed runs must be reviewed before controlled operation expands")
    if approval_signoffs < 1:
        blockers.append("at least one approval signoff must be recorded")
    if proof_signoffs < 1:
        blockers.append("at least one proof signoff must be recorded")

    return {
        "readiness_score": readiness_score,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "approval_signoffs": approval_signoffs,
        "proof_signoffs": proof_signoffs,
        "controlled_operation_ready": not blockers,
        "blockers": blockers,
    }


def build_controlled_operation_readiness_report(limit: int = 20) -> Dict[str, Any]:
    runtime_paths = get_runtime_paths()
    report = build_pilot_readiness_report(limit=limit)
    summary = get_pilot_summary()
    signoffs = get_pilot_signoffs()
    thresholds = _evaluate_thresholds(report, summary, signoffs)

    required_docs = [
        PROJECT_ROOT / "docs" / "controlled_operation_checklist.md",
        PROJECT_ROOT / "docs" / "supervised_live_pilot_runbook.md",
        PROJECT_ROOT / "docs" / "supervised_live_daily_checklist.md",
    ]
    doc_blockers = [str(path) for path in required_docs if not _path_exists(path)]
    if doc_blockers:
        thresholds["blockers"].append("required controlled-operation documentation is missing")
        thresholds["missing_docs"] = doc_blockers
        thresholds["controlled_operation_ready"] = False
    else:
        thresholds["missing_docs"] = []

    return {
        "pilot_mode": get_pilot_execution_metadata(),
        "runtime_root": str(runtime_paths.runtime_root),
        "project_root": str(runtime_paths.project_root),
        "manual_production_dir": str(runtime_paths.manual_production_dir),
        "pilot_readiness_report": report,
        "pilot_summary": summary,
        "signoffs": signoffs[-limit:],
        "thresholds": thresholds,
        "controlled_operation_ready": bool(thresholds["controlled_operation_ready"]),
        "blockers": thresholds["blockers"],
    }


def _print_summary(payload: Dict[str, Any]) -> None:
    thresholds = payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}
    print(f"controlled operation ready: {str(bool(payload.get('controlled_operation_ready', False))).lower()}")
    print(f"pilot readiness score: {thresholds.get('readiness_score', 0)}")
    print(f"total pilot runs: {thresholds.get('total_runs', 0)}")
    print(f"successful pilot runs: {thresholds.get('successful_runs', 0)}")
    print(f"failed pilot runs: {thresholds.get('failed_runs', 0)}")
    print(f"approval signoffs: {thresholds.get('approval_signoffs', 0)}")
    print(f"proof signoffs: {thresholds.get('proof_signoffs', 0)}")
    print(f"missing docs: {', '.join(thresholds.get('missing_docs') or []) or 'none'}")
    print(f"blockers: {'; '.join(payload.get('blockers') or []) or 'none'}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether the supervised pilot environment is ready for controlled operation.")
    parser.add_argument("--limit", type=int, default=20, help="How many recent signoffs to include in the report.")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    args = parser.parse_args(argv)

    payload = build_controlled_operation_readiness_report(limit=args.limit)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(payload)
    return 0 if bool(payload.get("controlled_operation_ready", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
