#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "portal_fetch" / "logs" / "supply_delivery_rfqs.json"
OUTPUT_DIR = RUNTIME_DIR / "manual_production" / "supply_delivery_quote_packs"
INDEX_FILE = OUTPUT_DIR / "supply_delivery_quote_pack_index.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_slug(value):
    value = str(value or "unknown")
    value = re.sub(r"[^\w\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")[:90] or "unknown"


def make_pack_id(rfq):
    raw = f"{rfq.get('department')}|{rfq.get('description')}|{rfq.get('closing_date')}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"SD-QPACK-{digest}"


def make_draft_letter(rfq):
    return f"""RE: Request for Quotation Preparation - {rfq.get('department', '')}

Tender / RFQ Description:
{rfq.get('description', '')}

Closing Date:
{rfq.get('closing_date', '')}

Procurement Type:
Supply and Delivery RFQ

Current System Status:
This opportunity has been automatically identified as a supply-and-delivery RFQ and prepared for quotation workflow.

Next Manual Actions Required:
1. Confirm official bid document / RFQ document.
2. Confirm item specification and quantity schedule.
3. Source supplier pricing.
4. Prepare final quote.
5. Review compliance and submission requirements.

Auto-Classification:
Decision: {rfq.get('classification', {}).get('decision')}
Score: {rfq.get('classification', {}).get('score')}
Accept Matches: {", ".join(rfq.get('classification', {}).get('accept_matches', []))}
Reject Matches: {", ".join(rfq.get('classification', {}).get('reject_matches', []))}
"""


def main():
    data = load_json(INPUT_FILE, default={})
    accepted = data.get("accepted", [])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    packs = []

    for rfq in accepted:
        pack_id = make_pack_id(rfq)
        tender_slug = safe_slug(rfq.get("rfq_id") or rfq.get("description"))
        pack_dir = OUTPUT_DIR / tender_slug

        pack_dir.mkdir(parents=True, exist_ok=True)

        quote_summary = {
            "pack_id": pack_id,
            "rfq_id": rfq.get("rfq_id"),
            "department": rfq.get("department"),
            "description": rfq.get("description"),
            "advert_date": rfq.get("advert_date"),
            "closing_date": rfq.get("closing_date"),
            "award_date": rfq.get("award_date"),
            "created_at": now_iso(),
            "quote_ready": True,
            "status": "supply_delivery_quote_pack_generated",
            "procurement_type": "supply_and_delivery",
            "pricing_status": "AWAITING_DOCUMENTS_OR_SUPPLIER_PRICING",
            "source_snapshot": rfq.get("source_snapshot"),
            "classification": rfq.get("classification"),
            "notes": [
                "Generated from live portal supply/delivery RFQ normalizer.",
                "Construction, CIDB and service-heavy opportunities are excluded.",
                "Attachment/detail-page harvesting still required for final automated pricing.",
            ],
        }

        quote_summary_path = pack_dir / "quote_summary.json"
        draft_letter_path = pack_dir / "draft_quote_letter.txt"

        write_json(quote_summary_path, quote_summary)

        with draft_letter_path.open("w", encoding="utf-8") as f:
            f.write(make_draft_letter(rfq))

        packs.append({
            "pack_id": pack_id,
            "rfq_id": rfq.get("rfq_id"),
            "department": rfq.get("department"),
            "description": rfq.get("description"),
            "closing_date": rfq.get("closing_date"),
            "pack_dir": str(pack_dir),
            "quote_summary_path": str(quote_summary_path),
            "draft_quote_letter_path": str(draft_letter_path),
            "quote_ready": True,
            "has_pricing": False,
            "pricing_status": "AWAITING_DOCUMENTS_OR_SUPPLIER_PRICING",
            "classification_score": rfq.get("classification", {}).get("score"),
        })

    index = {
        "generated_at": now_iso(),
        "source_file": str(INPUT_FILE),
        "total_supply_delivery_quote_packs": len(packs),
        "packs": packs,
    }

    write_json(INDEX_FILE, index)

    print(f"Supply delivery quote packs generated: {OUTPUT_DIR}")
    print(f"Index: {INDEX_FILE}")
    print(f"Total packs: {len(packs)}")

    for pack in packs:
        print(f"- {pack['department']} | {pack['description'][:90]}")


if __name__ == "__main__":
    main()
