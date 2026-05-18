from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import pilot_run_log_service


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _format_counter_items(items: Any) -> str:
    entries = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        value = _clean(item.get("value"))
        count = item.get("count")
        if value:
            entries.append(f"{value} ({count})")
    return "; ".join(entries) or "none"


def _print_summary(report: Dict[str, Any]) -> None:
    review_report = report.get("review_report") if isinstance(report.get("review_report"), dict) else {}
    print(f"total_runs: {review_report.get('total_runs', 0)}")
    print(f"blocked_runs: {review_report.get('blocked_runs', 0)}")
    print(f"dry_run_ready_runs: {review_report.get('dry_run_ready_runs', 0)}")
    print(f"pending_approval_runs: {review_report.get('pending_approval_runs', 0)}")
    print(f"approved_submit_attempts: {review_report.get('approved_submit_attempts', 0)}")
    print(f"approval_blocked_runs: {review_report.get('approval_blocked_runs', 0)}")
    print(f"common_warnings: {_format_counter_items(review_report.get('common_warnings'))}")
    print(f"common_errors: {_format_counter_items(review_report.get('common_errors'))}")
    print(f"excluded_tender_categories_found: {_format_counter_items(review_report.get('excluded_tender_categories_found'))}")
    print(f"mandatory_forms_most_often_detected: {_format_counter_items(review_report.get('mandatory_forms_most_often_detected'))}")
    print(f"quote_pack_quality_statuses: {_format_counter_items(review_report.get('quote_pack_quality_statuses'))}")
    print(f"readiness_recommendation: {_clean(review_report.get('readiness_recommendation'))}")
    print(f"autonomous_submission_enabled: {str(bool(review_report.get('autonomous_submission_enabled', False))).lower()}")


def show_manual_pilot_report(*, limit: int = 100, log_path: Optional[str] = None) -> Dict[str, Any]:
    if log_path:
        path = Path(log_path).expanduser()
        pilot_run_log_service.PILOT_RUN_LOG_FILE = path
        pilot_run_log_service.PILOT_RUN_DIR = path.parent
    return pilot_run_log_service.build_pilot_run_report(limit=limit)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Print the manual pilot report without starting FastAPI.")
    parser.add_argument("--limit", type=int, default=100, help="How many recent pilot runs to include.")
    parser.add_argument("--log-path", default=None, help="Optional path to pilot_runs.jsonl.")
    args = parser.parse_args(argv)

    report = show_manual_pilot_report(limit=args.limit, log_path=args.log_path)
    _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
