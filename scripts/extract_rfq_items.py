from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.rfq_boq_extraction_engine import extract_rfq_boq


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".csv", ".html", ".htm"}


def _collect_documents(tender_root: Path) -> List[str]:
    if not tender_root.exists():
        return []
    return [str(path) for path in tender_root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS]


def extract_rfq_items(*, tender_root: str, tender_id: Optional[str] = None) -> List[str]:
    root = Path(tender_root).expanduser()
    docs = _collect_documents(root)
    if not docs:
        return []
    result = extract_rfq_boq(
        {
            "title": tender_id or root.name,
            "buyer_rfq_number": tender_id or root.name,
            "rfq_number": tender_id or root.name,
            "local_document_paths": docs,
        }
    )
    return [str(item.get("description") or "").strip() for item in result.get("line_items") or [] if str(item.get("description") or "").strip()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Print extracted RFQ item descriptions for manual pricing.")
    parser.add_argument("--tender-root", required=True, help="Folder containing the RFQ/tender pack.")
    parser.add_argument("--tender-id", default=None, help="Optional tender identifier.")
    args = parser.parse_args(argv)

    descriptions = extract_rfq_items(tender_root=args.tender_root, tender_id=args.tender_id)
    print(f"extracted_line_item_count: {len(descriptions)}")
    print("extracted_line_item_descriptions:")
    if descriptions:
        for idx, description in enumerate(descriptions, start=1):
            print(f"{idx}. {description}")
    else:
        print("none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
