#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "ajax_tender_feed" / "supply_delivery_tenders.json"
OUT_DIR = RUNTIME_DIR / "manual_production" / "ajax_supply_quote_packs"
INDEX_FILE = OUT_DIR / "ajax_supply_quote_pack_index.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_slug(value):
    value = str(value or "unknown")
    value = re.sub(r"[^\w\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")[:120] or "unknown"


def make_pack_id(tender):
    raw = f"{tender.get('tender_id')}|{tender.get('tender_no')}|{tender.get('description')}"
    return "AJAX-QPACK-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def make_draft_letter(tender):
    return f"""RE: Supply and Delivery RFQ Quote Preparation

Tender Number:
{tender.get('tender_no')}

Department:
{tender.get('department')}

Description:
{tender.get('description')}

Closing Date:
{tender.get('closing_date')}

Category:
{tender.get('category')}

Contact:
{tender.get('contact_person')} | {tender.get('email')} | {tender.get('telephone')}

System Status:
This RFQ was harvested from the live eTenders AJAX feed and classified as supply/delivery.

Next Actions:
1. Download and review support documents.
2. Identify RFQ/specification/pricing schedule.
3. Extract items and quantities.
4. Source supplier pricing.
5. Prepare submission-ready quote.

Classification:
Decision: {tender.get('classification', {}).get('decision')}
Score: {tender.get('classification', {}).get('score')}
Accept Matches: {", ".join(tender.get('classification', {}).get('accept_matches', []))}
Reject Matches: {", ".join(tender.get('classification', {}).get('reject_matches', []))}
"""


def main():
    data = load_json(INPUT_FILE, default={})
    accepted = data.get("accepted", [])

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    packs = []

    for tender in accepted:
        pack_id = make_pack_id(tender)
        folder_name = safe_slug(f"{tender.get('tender_no')}_{tender.get('description')[:70]}")
        pack_dir = OUT_DIR / folder_name
        docs_dir = pack_dir / "support_documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        quote_summary = {
            "pack_id": pack_id,
            "source": "ajax_tender_feed",
            "tender_id": tender.get("tender_id"),
            "tender_no": tender.get("tender_no"),
            "description": tender.get("description"),
            "department": tender.get("department"),
            "category": tender.get("category"),
            "type": tender.get("type"),
            "province": tender.get("province"),
            "closing_date": tender.get("closing_date"),
            "date_published": tender.get("date_published"),
            "contact_person": tender.get("contact_person"),
            "email": tender.get("email"),
            "telephone": tender.get("telephone"),
            "delivery": tender.get("delivery"),
            "e_submission": tender.get("e_submission"),
            "support_document_count": tender.get("support_document_count"),
            "support_documents": tender.get("support_documents"),
            "classification": tender.get("classification"),
            "created_at": now_iso(),
            "quote_ready": True,
            "status": "ajax_supply_quote_pack_generated",
            "pricing_status": "AWAITING_DOCUMENT_DOWNLOAD_AND_EXTRACTION",
        }

        write_json(pack_dir / "quote_summary.json", quote_summary)
        write_json(pack_dir / "raw_tender.json", tender)

        with (pack_dir / "draft_quote_letter.txt").open("w", encoding="utf-8") as f:
            f.write(make_draft_letter(tender))

        packs.append({
            "pack_id": pack_id,
            "tender_id": tender.get("tender_id"),
            "tender_no": tender.get("tender_no"),
            "department": tender.get("department"),
            "description": tender.get("description"),
            "closing_date": tender.get("closing_date"),
            "support_document_count": tender.get("support_document_count"),
            "pack_dir": str(pack_dir),
            "quote_summary_path": str(pack_dir / "quote_summary.json"),
            "raw_tender_path": str(pack_dir / "raw_tender.json"),
            "draft_quote_letter_path": str(pack_dir / "draft_quote_letter.txt"),
            "pricing_status": "AWAITING_DOCUMENT_DOWNLOAD_AND_EXTRACTION",
            "classification_score": tender.get("classification", {}).get("score"),
        })

    index = {
        "generated_at": now_iso(),
        "source_file": str(INPUT_FILE),
        "total_ajax_supply_quote_packs": len(packs),
        "packs": packs,
    }

    write_json(INDEX_FILE, index)

    print(f"AJAX supply quote packs generated: {OUT_DIR}")
    print(f"Total packs: {len(packs)}")
    print(f"Index: {INDEX_FILE}")


if __name__ == "__main__":
    main()
