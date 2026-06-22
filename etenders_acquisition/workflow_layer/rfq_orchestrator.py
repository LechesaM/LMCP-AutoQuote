import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from workflow_layer.email_templates import build_rfq_email
from workflow_layer.supplier_contacts import get_supplier_contact
from workflow_layer.email_dispatcher import send_email

DB_PATH = Path("runtime/workflow/workflow_layer.db")
PRICING_SCHEDULE_PATH = Path("runtime/final_tender_submission/final_tender_pricing_schedule.json")
RFQ_OUTPUT_DIR = Path("runtime/rfqs")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def load_pricing_schedule(path=PRICING_SCHEDULE_PATH):
    if not path.exists():
        raise FileNotFoundError(f"Pricing schedule not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and isinstance(data.get("pricing_schedule"), list):
        return data["pricing_schedule"]

    if isinstance(data, list):
        return data

    raise ValueError("Could not find pricing_schedule list in final_tender_pricing_schedule.json")


def get_supplier_name(item):
    return item.get("selected_supplier") or "UNKNOWN_SUPPLIER"


def get_description(item):
    return item.get("description") or ""


def get_category(item):
    return item.get("category") or ""


def get_quantity(item):
    return item.get("quantity") or item.get("qty") or ""


def get_unit(item):
    return item.get("unit") or item.get("uom") or ""


def get_total(item):
    value = item.get("selected_quote_value")

    if value is None:
        value = item.get("supplier_quoted_value")

    if value is None:
        value = item.get("final_supplier_value")

    if value is None:
        value = item.get("award_value")

    try:
        return float(value or 0)
    except Exception:
        return 0.0


def get_original_value(item):
    try:
        return float(item.get("original_submission_value") or 0)
    except Exception:
        return 0.0


def get_saving(item):
    try:
        return float(item.get("final_saving") or 0)
    except Exception:
        return 0.0


def get_saving_pct(item):
    try:
        return float(item.get("final_saving_pct") or 0)
    except Exception:
        return 0.0


def group_items_by_supplier(items):
    grouped = {}

    for item in items:
        supplier_name = get_supplier_name(item)

        if supplier_name not in grouped:
            grouped[supplier_name] = []

        grouped[supplier_name].append(item)

    return grouped


def create_rfq_reference(tender_id, supplier_name):
    safe_supplier = (
        supplier_name.upper()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("&", "AND")
    )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"RFQ-{tender_id}-{safe_supplier}-{timestamp}"


def export_supplier_rfq_csv(rfq_reference, supplier_name, items):
    RFQ_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = RFQ_OUTPUT_DIR / f"{rfq_reference}.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rfq_reference",
                "supplier_name",
                "item_no",
                "category",
                "description",
                "unit",
                "quantity",
                "original_submission_value",
                "target_total",
                "target_saving",
                "target_saving_pct",
                "supplier_quoted_rate",
                "supplier_quoted_total",
                "lead_time_days",
                "vat_included",
                "stock_available",
                "commercial_exclusions",
                "supplier_notes"
            ]
        )

        writer.writeheader()

        for idx, item in enumerate(items, start=1):
            writer.writerow({
                "rfq_reference": rfq_reference,
                "supplier_name": supplier_name,
                "item_no": idx,
                "category": get_category(item),
                "description": get_description(item),
                "unit": get_unit(item),
                "quantity": get_quantity(item),
                "original_submission_value": get_original_value(item),
                "target_total": get_total(item),
                "target_saving": get_saving(item),
                "target_saving_pct": get_saving_pct(item),
                "supplier_quoted_rate": "",
                "supplier_quoted_total": "",
                "lead_time_days": "",
                "vat_included": "",
                "stock_available": "",
                "commercial_exclusions": "",
                "supplier_notes": ""
            })

    return output_path


def record_rfq_batch(
    tender_id,
    supplier_name,
    rfq_reference,
    rfq_file_path,
    total_items,
    total_estimated_value,
    response_due_at,
    status="draft"
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO rfq_batches (
        tender_id,
        supplier_name,
        rfq_reference,
        rfq_file_path,
        total_items,
        total_estimated_value,
        status,
        created_at,
        response_due_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tender_id,
        supplier_name,
        rfq_reference,
        str(rfq_file_path),
        total_items,
        total_estimated_value,
        status,
        utc_now(),
        response_due_at
    ))

    conn.commit()
    conn.close()


def mark_rfq_sent(rfq_reference):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    UPDATE rfq_batches
    SET status = 'sent',
        sent_at = ?
    WHERE rfq_reference = ?
    """, (utc_now(), rfq_reference))

    conn.commit()
    conn.close()


def orchestrate_rfqs(
    tender_id="FINAL-TENDER",
    send_live_emails=False,
    response_days=3
):
    items = load_pricing_schedule()
    grouped = group_items_by_supplier(items)

    response_due_at = (
        datetime.now(timezone.utc) + timedelta(days=response_days)
    ).date().isoformat()

    created_rfqs = []

    for supplier_name, supplier_items in grouped.items():
        if supplier_name == "UNKNOWN_SUPPLIER":
            print("Skipping UNKNOWN_SUPPLIER items")
            continue

        contact = get_supplier_contact(supplier_name)

        if not contact:
            print(f"No contact found for supplier: {supplier_name}")
            continue

        _, contact_person, email, phone, branch, category = contact

        rfq_reference = create_rfq_reference(tender_id, supplier_name)

        rfq_file_path = export_supplier_rfq_csv(
            rfq_reference=rfq_reference,
            supplier_name=supplier_name,
            items=supplier_items
        )

        total_estimated_value = sum(get_total(item) for item in supplier_items)

        record_rfq_batch(
            tender_id=tender_id,
            supplier_name=supplier_name,
            rfq_reference=rfq_reference,
            rfq_file_path=rfq_file_path,
            total_items=len(supplier_items),
            total_estimated_value=total_estimated_value,
            response_due_at=response_due_at,
            status="draft"
        )

        email_content = build_rfq_email(
            supplier_name=supplier_name,
            rfq_reference=rfq_reference,
            tender_id=tender_id,
            total_items=len(supplier_items),
            response_due_date=response_due_at
        )

        status = "draft"

        if send_live_emails:
            send_email(
                to_email=email,
                subject=email_content["subject"],
                body=email_content["body"],
                attachment_paths=[rfq_file_path]
            )
            mark_rfq_sent(rfq_reference)
            status = "sent"

        created_rfqs.append({
            "supplier_name": supplier_name,
            "contact_person": contact_person,
            "email": email,
            "rfq_reference": rfq_reference,
            "rfq_file_path": str(rfq_file_path),
            "total_items": len(supplier_items),
            "total_estimated_value": round(total_estimated_value, 2),
            "response_due_at": response_due_at,
            "status": status
        })

        print(
            f"RFQ prepared: {supplier_name} | "
            f"{len(supplier_items)} items | "
            f"R{total_estimated_value:,.2f} | "
            f"{status}"
        )

    RFQ_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = RFQ_OUTPUT_DIR / "rfq_orchestration_summary.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(created_rfqs, f, indent=2)

    print(f"RFQ summary written: {output_path}")
    return created_rfqs


if __name__ == "__main__":
    orchestrate_rfqs(
        tender_id="FINAL-TENDER",
        send_live_emails=False,
        response_days=3
    )
