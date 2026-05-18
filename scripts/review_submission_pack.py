from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import submission_review_service


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _print_checklist(record: Dict[str, Any]) -> None:
    print(f"quote pack present: {str(bool(record.get('quote_pack_present', False))).lower()}")
    print(f"submission pack present: {str(bool(record.get('submission_pack_present', False))).lower()}")
    print(f"pricing file present: {str(bool(record.get('pricing_file_present', False))).lower()}")
    print(f"source RFQ present: {str(bool(record.get('source_rfq_present', False))).lower()}")
    print(f"approval record present: {str(bool(record.get('approval_record_present', False))).lower()}")
    print(f"final submission still false: {str(bool(record.get('final_submission_still_false', False))).lower()}")


def review_submission_pack(*, tender_id: str, tender_root: str) -> Dict[str, Any]:
    record = submission_review_service.build_submission_review_record(
        tender_id=tender_id,
        tender_root=tender_root,
    )
    submission_review_service.append_submission_review(record)
    return record


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Review a submission pack without submitting anything.")
    parser.add_argument("--tender-id", required=True, help="Stable tender identifier.")
    parser.add_argument("--tender-root", required=True, help="Folder containing the RFQ/tender pack.")
    args = parser.parse_args(argv)

    record = review_submission_pack(tender_id=args.tender_id, tender_root=args.tender_root)
    print(f"status: {_clean(record.get('status'))}")
    _print_checklist(record)
    print(f"review blockers: {'; '.join(record.get('review_blockers') or []) or 'none'}")
    print(f"submission review log location: {submission_review_service.SUBMISSION_REVIEW_LOG_FILE}")
    return 0 if bool(record.get("submission_review_ready", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())

