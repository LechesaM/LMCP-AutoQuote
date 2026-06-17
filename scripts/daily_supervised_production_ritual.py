#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LMCP_PROJECT_ROOT", str(PROJECT_ROOT))
os.environ.setdefault("LMCP_RUNTIME_DIR", str(PROJECT_ROOT / "runtime"))
for _name, _value in {
    "LMCP_PROJECT_ROOT": str(PROJECT_ROOT),
    "LMCP_RUNTIME_DIR": str(PROJECT_ROOT / "runtime"),
}.items():
    _current = os.environ.get(_name, "")
    if not _current or _current.startswith("/app"):
        os.environ[_name] = _value

from app.core.runtime_paths import get_runtime_paths
from app.services.audit_trail_service import append_audit_event
from app.services.autonomous_submission_loop_service import run_autonomous_submission_loop
from app.services.live_rfq_store import LiveRFQStore
from app.services.safe_autonomous_scheduler_service import run_safe_autonomous_cycle
from app.services.submission_analytics_service import (
    get_submission_profit_tracking,
    get_submission_success_tracking,
)
from app.services.submission_history_proof_enrichment_service import enrich_submission_history_with_proof_paths
from app.services.submission_history_service import get_submission_summary
from app.services.submission_reconciliation_service import reconcile_submission_execution


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ritual_runtime_root() -> Path:
    return Path(os.environ.get("LMCP_RUNTIME_DIR") or (PROJECT_ROOT / "runtime")).expanduser().resolve()


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _history_path() -> Path:
    return _ritual_runtime_root() / "manual_production" / "daily_supervised_production_ritual_history.jsonl"


def _latest_report_path() -> Path:
    return _ritual_runtime_root() / "manual_production" / "daily_supervised_production_ritual.json"


def _write_report(report: Dict[str, Any]) -> None:
    report_path = _latest_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    history_path = _history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, default=str) + "\n")


def _candidate_tender_ids(run_result: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for item in _safe_list(run_result.get("items")):
        item_dict = _safe_dict(item)
        tender_id = str(
            item_dict.get("buyer_rfq_number")
            or item_dict.get("tender_id")
            or item_dict.get("rfq_id")
            or item_dict.get("rfq_number")
            or item_dict.get("reference_number")
            or ""
        ).strip()
        if tender_id and tender_id not in ids:
            ids.append(tender_id)
    return ids


def _build_reconciliation_rows(tender_ids: List[str], limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for tender_id in tender_ids[: max(1, limit)]:
        try:
            rows.append(reconcile_submission_execution({"tender_id": tender_id}))
        except Exception as exc:
            rows.append(
                {
                    "status": "error",
                    "tender_id": tender_id,
                    "reconciled": False,
                    "blockers": [str(exc)],
                }
            )
    return rows


def main(argv: List[str] | None = None) -> int:
    get_runtime_paths.cache_clear()
    parser = argparse.ArgumentParser(description="Run the daily supervised production ritual.")
    parser.add_argument("--limit", type=int, default=3, help="Maximum number of retry/pending items to process.")
    parser.add_argument("--max-total", type=int, default=10, help="Maximum tenders to harvest in the safe scheduler cycle.")
    parser.add_argument("--max-submissions", type=int, default=3, help="Maximum submissions to allow when submit mode is enabled.")
    parser.add_argument("--enable-submit", action="store_true", help="Allow the safe scheduler to submit allowed RFQs.")
    parser.add_argument("--confirm-submit", action="store_true", help="Required to enable submissions.")
    parser.add_argument("--min-submitted", type=int, default=0, help="Fail if fewer than this many submissions are recorded in the report.")
    args = parser.parse_args(argv)

    if args.enable_submit and not args.confirm_submit:
        raise SystemExit("--confirm-submit is required when --enable-submit is set.")

    submitted_enabled = bool(args.enable_submit and args.confirm_submit)
    started_at = _now_iso()
    append_audit_event(
        event_type="daily_supervised_production_ritual_started",
        source="daily_supervised_production_ritual",
        severity="info",
        title="Daily supervised production ritual started",
        message="Daily supervised production ritual started.",
        runtime_dir=str(_ritual_runtime_root()),
        payload={
            "started_at": started_at,
            "max_total": args.max_total,
            "max_submissions": args.max_submissions,
            "enable_submit": submitted_enabled,
            "limit": args.limit,
        },
    )

    safe_cycle = asyncio.run(
        run_safe_autonomous_cycle(
            max_total=args.max_total,
            max_submissions=args.max_submissions,
            enable_submit=submitted_enabled,
            enable_quote_engine=True,
            reason="daily_supervised_production_ritual",
        )
    )
    retry_cycle = run_autonomous_submission_loop(limit=args.limit)
    proof_enrichment = enrich_submission_history_with_proof_paths()
    submission_summary = get_submission_summary()
    success_tracking = get_submission_success_tracking()
    profit_tracking = get_submission_profit_tracking(submitted_only=True)
    reconciliations = _build_reconciliation_rows(_candidate_tender_ids(safe_cycle), args.limit)

    report = {
        "status": "ok" if str(safe_cycle.get("status") or "").lower() == "ok" and str(retry_cycle.get("status") or "").lower() in {"ok", "disabled"} else "degraded",
        "checked_at": _now_iso(),
        "started_at": started_at,
        "finished_at": _now_iso(),
        "scheduler_mode": "supervised",
        "settings": {
            "limit": args.limit,
            "max_total": args.max_total,
            "max_submissions": args.max_submissions,
            "enable_submit": submitted_enabled,
        },
        "safe_cycle": safe_cycle,
        "submission_retry_cycle": retry_cycle,
        "proof_enrichment": proof_enrichment,
        "submission_summary": submission_summary,
        "success_tracking": success_tracking,
        "profit_tracking": profit_tracking,
        "reconciliations": reconciliations,
        "live_rfq_count": int(LiveRFQStore.count() if hasattr(LiveRFQStore, "count") else len(_safe_list(LiveRFQStore.get_all().get("items")))),
        "daily_gross_margin": profit_tracking.get("gross_margin"),
        "daily_margin_rate": profit_tracking.get("margin_rate"),
        "submission_count": submission_summary.get("submitted", 0),
    }

    _write_report(report)

    append_audit_event(
        event_type="daily_supervised_production_ritual_completed",
        source="daily_supervised_production_ritual",
        severity="success" if report["status"] == "ok" else "warning",
        title="Daily supervised production ritual completed",
        message=f"Daily supervised production ritual completed with status {report['status']}.",
        runtime_dir=str(_ritual_runtime_root()),
        payload=report,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    if args.min_submitted and int(report.get("submission_count") or 0) < args.min_submitted:
        raise SystemExit(f"Submission count {report.get('submission_count') or 0} is below minimum required {args.min_submitted}.")

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
