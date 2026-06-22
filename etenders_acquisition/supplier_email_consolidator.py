#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_outreach_emails"
    / "supplier_rfq_email_queue.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_outreach_emails"

CONSOLIDATED_FILE = (
    OUT_DIR
    / "supplier_consolidated_rfq_emails.json"
)

SUMMARY_FILE = (
    OUT_DIR
    / "supplier_email_consolidation_summary.json"
)


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


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def build_consolidated_body(supplier, items):
    total_exposure = sum(
        money(x.get("current_submission_total"))
        for x in items
    )

    total_target = sum(
        money(x.get("target_price"))
        for x in items
    )

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
        body += f"""

{idx}. {item.get('line_description')}

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

    emails = data.get("supplier_rfq_emails", [])

    grouped = defaultdict(list)

    for email in emails:
        grouped[email.get("supplier")].append(email)

    consolidated = []

    for idx, (supplier, items) in enumerate(grouped.items(), start=1):

        categories = sorted(
            list(set(x.get("category") for x in items))
        )

        exposure = sum(
            money(x.get("current_submission_total"))
            for x in items
        )

        target = sum(
            money(x.get("target_price"))
            for x in items
        )

        consolidated.append({
            "consolidated_email_id": idx,
            "generated_at": now_iso(),
            "supplier": supplier,
            "supplier_band": items[0].get("supplier_band"),
            "supplier_reliability": items[0].get(
                "supplier_reliability"
            ),
            "categories": categories,
            "line_count": len(items),
            "total_current_exposure": exposure,
            "total_target_value": target,
            "subject": (
                f"CONSOLIDATED RFQ REQUEST | "
                f"{supplier} | "
                f"{len(items)} ITEMS"
            ),
            "body": build_consolidated_body(
                supplier,
                items,
            ),
            "items": [
                {
                    "category": x.get("category"),
                    "description": x.get("line_description"),
                    "current_submission_total": x.get(
                        "current_submission_total"
                    ),
                    "target_price": x.get("target_price"),
                }
                for x in items
            ],
            "email_status": "READY_TO_SEND",
        })

    output = {
        "generated_at": now_iso(),
        "consolidated_supplier_emails": consolidated,
    }

    summary = {
        "generated_at": now_iso(),
        "raw_email_count": len(emails),
        "consolidated_email_count": len(consolidated),
        "email_reduction": len(emails) - len(consolidated),
        "suppliers": sorted(list(grouped.keys())),
    }

    write_json(CONSOLIDATED_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Consolidated emails written: {CONSOLIDATED_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Raw emails: {summary['raw_email_count']}")
    print(f"Consolidated emails: {summary['consolidated_email_count']}")
    print(f"Email reduction: {summary['email_reduction']}")


if __name__ == "__main__":
    main()
