#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

OUTREACH_FILE = (
    RUNTIME_DIR
    / "autonomous_procurement_execution"
    / "supplier_outreach_plan.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_outreach_emails"

EMAILS_FILE = OUT_DIR / "supplier_rfq_email_queue.json"
SUMMARY_FILE = OUT_DIR / "supplier_outreach_email_summary.json"


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


def sanitize_filename(text):
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    return text[:120]


def build_subject(item):
    return (
        f"RFQ REQUEST | {item.get('category', 'GENERAL').upper()} | "
        f"{item.get('supplier')}"
    )


def build_email_body(item):
    description = item.get("line_description")
    target_price = money(item.get("target_price"))
    current_total = money(item.get("current_submission_total"))

    questions = item.get("recommended_questions") or []

    body = f"""
Dear Supplier,

We request your formal quotation and commercial confirmation for the following procurement requirement.

ITEM DESCRIPTION:
{description}

CURRENT COMMERCIAL EXPOSURE:
R{current_total:,.2f}

TARGET NEGOTIATION RANGE:
R{target_price:,.2f}

Please provide:

1. Official quotation
2. Lead time confirmation
3. Stock availability
4. OEM/manufacturer confirmation where applicable
5. Warranty confirmation
6. Bulk discount structure
7. Delivery period
8. Validity period of quotation

Commercial clarification items:
"""

    for q in questions:
        body += f"\n- {q}"

    body += """

This RFQ forms part of a commercial adjudication and procurement optimization process.

Please prioritize urgent response.

Regards,
Procurement Division
Lechesa Manaba Consulting and Projects
"""

    return body.strip()


def main():
    outreach = load_json(OUTREACH_FILE, default={})

    supplier_outreach = outreach.get("supplier_outreach", [])

    emails = []

    for idx, item in enumerate(supplier_outreach, start=1):

        subject = build_subject(item)
        body = build_email_body(item)

        email = {
            "email_id": idx,
            "generated_at": now_iso(),
            "supplier": item.get("supplier"),
            "supplier_band": item.get("supplier_band"),
            "supplier_reliability": item.get(
                "supplier_reliability"
            ),
            "category": item.get("category"),
            "subject": subject,
            "body": body,
            "line_description": item.get(
                "line_description"
            ),
            "target_price": item.get("target_price"),
            "current_submission_total": item.get(
                "current_submission_total"
            ),
            "email_status": "READY_TO_SEND",
        }

        emails.append(email)

    output = {
        "generated_at": now_iso(),
        "supplier_rfq_emails": emails,
    }

    summary = {
        "generated_at": now_iso(),
        "emails_generated": len(emails),
        "suppliers_targeted": len(
            set(x["supplier"] for x in emails)
        ),
        "high_priority_categories": sorted(
            list(
                set(
                    x["category"]
                    for x in emails
                    if x["category"] in (
                        "ppe",
                        "building_material",
                        "mechanical",
                    )
                )
            )
        ),
    }

    write_json(EMAILS_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Supplier RFQ emails written: {EMAILS_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Emails generated: {summary['emails_generated']}")
    print(f"Suppliers targeted: {summary['suppliers_targeted']}")


if __name__ == "__main__":
    main()
