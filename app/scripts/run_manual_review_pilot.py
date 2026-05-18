from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.services.operator_auth_service import OperatorContext
from app.services.quote_review_service import _normalise_pilot_entries, run_manual_review_pilot

TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "pilot_manifest_template.json"


def _load_manifest(path: str) -> dict:
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.exists():
        raise ValueError(
            "Pilot manifest file does not exist: "
            f"{manifest_path}\n"
            f"Template: {TEMPLATE_PATH}\n"
            "Copy and edit the template, then re-run with:\n"
            "python3 app/scripts/run_manual_review_pilot.py --manifest /absolute/path/to/your_pilot_manifest.json"
        )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Pilot manifest must be a JSON object.")
    if not isinstance(data.get("rfqs"), list):
        raise ValueError("Pilot manifest must contain an 'rfqs' list.")
    return data


def _print_stage(stage: str, status: str, payload: Optional[dict] = None) -> None:
    detail = ""
    safe_payload = payload or {}
    if safe_payload:
        detail = " " + " ".join(f"{key}={value}" for key, value in sorted(safe_payload.items()))
    print(f"[pilot] {stage} {status}{detail}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the controlled 10-RFQ manual review pilot.")
    parser.add_argument(
        "--manifest",
        required=True,
        help=f"Path to the pilot manifest JSON file. Template: {TEMPLATE_PATH}",
    )
    parser.add_argument("--operator-id", default="pilot-admin", help="Operator identifier for the pilot run.")
    parser.add_argument("--operator-name", default="Pilot Operator", help="Display name recorded in the pilot audit trail.")
    parser.add_argument("--role", default="admin", choices=("preparer", "reviewer", "submitter", "admin"), help="Operator role.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum RFQs to process, capped at 10.")
    parser.add_argument("--single-rfq", action="store_true", help="Process only the first RFQ from the manifest.")
    parser.add_argument("--skip-ingestion", action="store_true", help="Skip quote-pack ingestion and validate extraction/classification/reporting only.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the manifest and print the RFQs that would be processed without creating a run.")
    parser.add_argument("--ingestion-timeout-seconds", type=int, default=60, help="Hard timeout for draft ingestion per RFQ.")
    parser.add_argument("--max-pilot-pricing-rows", type=int, default=100, help="Maximum pricing rows stored and ingested per RFQ during the pilot.")
    parser.add_argument(
        "--continue-on-timeout",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue to the next RFQ if draft ingestion times out.",
    )
    args = parser.parse_args()

    try:
        _print_stage("manifest_load", "start", {"manifest": args.manifest})
        manifest = _load_manifest(args.manifest)
        _print_stage("manifest_load", "end", {"rfq_count": len(manifest.get("rfqs") or [])})
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    effective_limit = 1 if args.single_rfq else args.limit
    try:
        _print_stage("manifest_validation", "start", {"limit": effective_limit})
        selected_entries = _normalise_pilot_entries(manifest.get("rfqs") or [], limit=effective_limit)
        _print_stage("manifest_validation", "end", {"selected_rfqs": len(selected_entries)})
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.dry_run:
        payload = {
            "status": "dry_run",
            "pilot_name": str(manifest.get("pilot_name") or ""),
            "rfq_count": len(selected_entries),
            "rfqs": [
                {
                    "rfq_index": index,
                    "rfq_filename": Path(str(entry.get("rfq_path") or "")).name,
                    "rfq_path": entry.get("rfq_path"),
                }
                for index, entry in enumerate(selected_entries, start=1)
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0

    operator = OperatorContext(
        operator_id=args.operator_id,
        display_name=args.operator_name,
        role=args.role,
        authenticated=True,
        auth_source="pilot_script",
    )

    db = None if args.skip_ingestion else SessionLocal()
    try:
        try:
            result = run_manual_review_pilot(
                db,
                rfq_entries=selected_entries,
                operator=operator,
                pilot_name=str(manifest.get("pilot_name") or ""),
                limit=effective_limit,
                skip_ingestion=args.skip_ingestion,
                ingestion_timeout_seconds=args.ingestion_timeout_seconds,
                max_pilot_pricing_rows=args.max_pilot_pricing_rows,
                continue_on_timeout=args.continue_on_timeout,
                progress_callback=_print_stage,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    finally:
        if db is not None:
            db.close()

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
