import argparse
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from workflow_layer.email_templates import build_rfq_email
from workflow_layer.email_dispatcher import send_email

DB_PATH = Path("runtime/workflow/workflow_layer.db")
REVIEW_PATH = Path("runtime/rfqs/rfq_dispatch_review.json")
DISPATCH_LOG_PATH = Path("runtime/rfqs/rfq_dispatch_log.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def load_review():
    if not REVIEW_PATH.exists():
        raise FileNotFoundError(
            f"Dispatch review not found: {REVIEW_PATH}. "
            "Run: python3 -m workflow_layer.rfq_dispatch_review"
        )

    with open(REVIEW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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


def write_dispatch_log(log_items):
    DISPATCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": utc_now(),
        "total_attempted": len(log_items),
        "sent_count": sum(1 for item in log_items if item["dispatch_status"] == "sent"),
        "blocked_count": sum(1 for item in log_items if item["dispatch_status"] == "blocked"),
        "failed_count": sum(1 for item in log_items if item["dispatch_status"] == "failed"),
        "dispatches": log_items
    }

    with open(DISPATCH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def send_approved_rfqs(send_live=False, tender_id="FINAL-TENDER"):
    review = load_review()
    dispatch_log = []

    for rfq in review.get("rfqs", []):
        supplier_name = rfq.get("supplier_name")
        rfq_reference = rfq.get("rfq_reference")
        email = rfq.get("email")
        rfq_file_path = rfq.get("rfq_file_path")
        total_items = rfq.get("total_items")
        response_due_at = rfq.get("response_due_at")

        if not rfq.get("dispatch_ready"):
            dispatch_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "dispatch_status": "blocked",
                "reason": "dispatch_ready_false",
                "issues": rfq.get("issues", []),
                "processed_at": utc_now()
            })
            continue

        if not send_live:
            dispatch_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "email": email,
                "rfq_file_path": rfq_file_path,
                "dispatch_status": "blocked",
                "reason": "dry_run_only_missing_send_live_flag",
                "processed_at": utc_now()
            })
            continue

        try:
            email_content = build_rfq_email(
                supplier_name=supplier_name,
                rfq_reference=rfq_reference,
                tender_id=tender_id,
                total_items=total_items,
                response_due_date=response_due_at
            )

            send_email(
                to_email=email,
                subject=email_content["subject"],
                body=email_content["body"],
                attachment_paths=[rfq_file_path]
            )

            mark_rfq_sent(rfq_reference)

            dispatch_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "email": email,
                "rfq_file_path": rfq_file_path,
                "dispatch_status": "sent",
                "processed_at": utc_now()
            })

            print(f"SENT: {supplier_name} | {rfq_reference}")

        except Exception as exc:
            dispatch_log.append({
                "supplier_name": supplier_name,
                "rfq_reference": rfq_reference,
                "email": email,
                "rfq_file_path": rfq_file_path,
                "dispatch_status": "failed",
                "error": str(exc),
                "processed_at": utc_now()
            })

            print(f"FAILED: {supplier_name} | {rfq_reference} | {exc}")

    log_payload = write_dispatch_log(dispatch_log)

    print("\nRFQ DISPATCH RESULT")
    print("=" * 80)
    print(f"Attempted: {log_payload['total_attempted']}")
    print(f"Sent:      {log_payload['sent_count']}")
    print(f"Blocked:   {log_payload['blocked_count']}")
    print(f"Failed:    {log_payload['failed_count']}")
    print(f"Log:       {DISPATCH_LOG_PATH}")

    return log_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--send-live",
        action="store_true",
        help="Actually send RFQ emails. Without this flag, script runs in dry-run mode."
    )
    parser.add_argument(
        "--tender-id",
        default="FINAL-TENDER",
        help="Tender ID to include in RFQ email subject/body."
    )

    args = parser.parse_args()

    send_approved_rfqs(
        send_live=args.send_live,
        tender_id=args.tender_id
    )
