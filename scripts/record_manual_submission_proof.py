from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import submission_proof_service


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _print_summary(record: Dict[str, Any]) -> None:
    print(f"status: {_clean(record.get('status'))}")
    print(f"submission review status: {_clean(record.get('submission_review_status'))}")
    print(f"manual submission recorded: {str(bool(record.get('manual_submission_recorded', False))).lower()}")
    print(f"final submission attempted: {str(bool(record.get('final_submission_attempted', False))).lower()}")
    print(f"portal name: {_clean(record.get('portal_name'))}")
    print(f"submission reference: {_clean(record.get('submission_reference'))}")
    print(f"submitted by: {_clean(record.get('submitted_by'))}")
    print(f"proof file present: {str(bool(record.get('proof_file_present', False))).lower()}")
    if _clean(record.get("proof_file")):
        print(f"proof file: {_clean(record.get('proof_file'))}")
    print(f"submission proof log location: {submission_proof_service.SUBMISSION_PROOF_LOG_FILE}")


def record_manual_submission_proof(
    *,
    tender_id: str,
    tender_root: str,
    portal_name: str,
    submission_reference: str,
    submitted_by: str,
    proof_file: str = "",
) -> Dict[str, Any]:
    record = submission_proof_service.build_submission_proof_record(
        tender_id=tender_id,
        tender_root=tender_root,
        portal_name=portal_name,
        submission_reference=submission_reference,
        submitted_by=submitted_by,
        proof_file=proof_file,
    )
    if record.get("status") == "recorded":
        submission_proof_service.append_submission_proof(record)
    return record


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Record manual submission proof after a review-ready pack.")
    parser.add_argument("--tender-id", required=True, help="Stable tender identifier.")
    parser.add_argument("--tender-root", required=True, help="Folder containing the RFQ/tender pack.")
    parser.add_argument("--portal-name", required=True, help="Portal or channel name used for the manual submission.")
    parser.add_argument("--submission-reference", required=True, help="Reference returned by the portal or manual process.")
    parser.add_argument("--proof-file", default="", help="Optional proof file path to attach.")
    parser.add_argument("--submitted-by", required=True, help="Operator name that performed the submission.")
    args = parser.parse_args(argv)

    record = record_manual_submission_proof(
        tender_id=args.tender_id,
        tender_root=args.tender_root,
        portal_name=args.portal_name,
        submission_reference=args.submission_reference,
        proof_file=args.proof_file,
        submitted_by=args.submitted_by,
    )
    _print_summary(record)
    if record.get("status") != "recorded":
        blockers = record.get("blockers") or []
        print(f"proof capture refused: {'; '.join(blockers) or 'unknown blocker'}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

