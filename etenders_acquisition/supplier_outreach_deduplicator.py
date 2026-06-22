#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_outreach_emails"
    / "supplier_consolidated_rfq_emails.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_outreach_emails"

OUTPUT_FILE = OUT_DIR / "supplier_consolidated_rfq_emails_deduped.json"
SUMMARY_FILE = OUT_DIR / "supplier_outreach_dedup_summary.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


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


def clean_key(text):
    return " ".join(str(text or "").lower().split())


def dedupe_items(items):
    deduped = {}

    for item in items:
        key = clean_key(item.get("description"))

        if key not in deduped:
            x = dict(item)
            x["duplicate_count"] = 1
            deduped[key] = x
            continue

        existing = deduped[key]
        existing["duplicate_count"] += 1
        existing["current_submission_total"] = max(
            money(existing.get("current_submission_total")),
            money(item.get("current_submission_total")),
        )
        existing["target_price"] = min(
            money(existing.get("target_price")),
            money(item.get("target_price")),
        )

    return list(deduped.values())


def build_body(email, items):
    supplier = email.get("supplier")

    total_exposure = sum(money(x.get("current_submission_total")) for x in items)
    total_target = sum(money(x.get("target_price")) for x in items)

    body = f"""
Dear Supplier,

We request consolidated commercial quotations for the following procurement package.

SUPPLIER:
{supplier}

TOTAL CURRENT COMMERCIAL EXPOSURE:
R{total_exposure:,.2f}

TARGET NEGOTIATION VALUE:
R{total_target:,.2f}

ITEMS REQUIRING QUOTATION:
"""

    for idx, item in enumerate(items, start=1):
        duplicate_note = ""
        if item.get("duplicate_count", 1) > 1:
            duplicate_note = f"\nMerged duplicate occurrences: {item.get('duplicate_count')}"

        body += f"""

{idx}. {item.get('description')}{duplicate_note}

Current Exposure:
R{money(item.get('current_submission_total')):,.2f}

Target Negotiation Range:
R{money(item.get('target_price')):,.2f}
"""

    body += """

Please provide:

1. Official quotations
2. Lead times
3. Bulk discount structures
4. OEM/manufacturer confirmations
5. Stock availability
6. Delivery schedules
7. Warranty confirmation
8. Commercial validity period

This request forms part of a commercial adjudication and procurement optimization process.

Urgent response is requested.

Regards,
Procurement Division
Lechesa Manaba Consulting and Projects
"""

    return body.strip()


def main():
    data = load_json(INPUT_FILE, default={})
    emails = data.get("consolidated_supplier_emails", [])

    output_emails = []
    raw_items = 0
    deduped_items_total = 0
    duplicates_removed = 0

    for email in emails:
        items = email.get("items", [])
        raw_items += len(items)

        deduped_items = dedupe_items(items)
        deduped_items_total += len(deduped_items)
        duplicates_removed += len(items) - len(deduped_items)

        total_exposure = sum(money(x.get("current_submission_total")) for x in deduped_items)
        total_target = sum(money(x.get("target_price")) for x in deduped_items)

        new_email = dict(email)
        new_email.update({
            "line_count": len(deduped_items),
            "raw_line_count": len(items),
            "duplicates_removed": len(items) - len(deduped_items),
            "total_current_exposure": total_exposure,
            "total_target_value": total_target,
            "items": deduped_items,
            "body": build_body(email, deduped_items),
            "email_status": "READY_TO_SEND_DEDUPED",
        })

        output_emails.append(new_email)

    summary = {
        "generated_at": now_iso(),
        "supplier_email_count": len(output_emails),
        "raw_items": raw_items,
        "deduped_items": deduped_items_total,
        "duplicates_removed": duplicates_removed,
    }

    write_json(OUTPUT_FILE, {
        "generated_at": summary["generated_at"],
        "consolidated_supplier_emails": output_emails,
    })

    write_json(SUMMARY_FILE, summary)

    print(f"Deduped supplier RFQ emails written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Supplier emails: {summary['supplier_email_count']}")
    print(f"Raw items: {summary['raw_items']}")
    print(f"Deduped items: {summary['deduped_items']}")
    print(f"Duplicates removed: {summary['duplicates_removed']}")


if __name__ == "__main__":
    main()
