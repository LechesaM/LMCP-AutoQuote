import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("runtime/workflow/workflow_layer.db")
RFQ_SUMMARY_PATH = Path("runtime/rfqs/rfq_orchestration_summary.json")
REVIEW_OUTPUT_PATH = Path("runtime/rfqs/rfq_dispatch_review.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def load_rfq_summary():
    if not RFQ_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"RFQ summary not found: {RFQ_SUMMARY_PATH}. "
            "Run rfq_orchestrator first."
        )

    with open(RFQ_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_db_rfq_batches():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        supplier_name,
        rfq_reference,
        rfq_file_path,
        total_items,
        total_estimated_value,
        status,
        response_due_at,
        created_at,
        sent_at
    FROM rfq_batches
    ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def build_dispatch_review():
    rfqs = load_rfq_summary()
    review_items = []

    for rfq in rfqs:
        issues = []

        if not rfq.get("email"):
            issues.append("missing_supplier_email")

        if not rfq.get("rfq_file_path"):
            issues.append("missing_rfq_file_path")

        elif not Path(rfq["rfq_file_path"]).exists():
            issues.append("rfq_file_not_found")

        if not rfq.get("total_items") or rfq["total_items"] <= 0:
            issues.append("no_rfq_items")

        if not rfq.get("total_estimated_value") or rfq["total_estimated_value"] <= 0:
            issues.append("zero_or_missing_estimated_value")

        dispatch_ready = len(issues) == 0

        review_items.append({
            "supplier_name": rfq.get("supplier_name"),
            "contact_person": rfq.get("contact_person"),
            "email": rfq.get("email"),
            "rfq_reference": rfq.get("rfq_reference"),
            "rfq_file_path": rfq.get("rfq_file_path"),
            "total_items": rfq.get("total_items"),
            "total_estimated_value": rfq.get("total_estimated_value"),
            "response_due_at": rfq.get("response_due_at"),
            "current_status": rfq.get("status"),
            "dispatch_ready": dispatch_ready,
            "issues": issues,
            "reviewed_at": utc_now()
        })

    output = {
        "generated_at": utc_now(),
        "total_rfqs": len(review_items),
        "dispatch_ready_count": sum(1 for item in review_items if item["dispatch_ready"]),
        "blocked_count": sum(1 for item in review_items if not item["dispatch_ready"]),
        "rfqs": review_items
    }

    REVIEW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(REVIEW_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return output


def print_review_report(review):
    print("\nRFQ DISPATCH REVIEW")
    print("=" * 80)
    print(f"Total RFQs: {review['total_rfqs']}")
    print(f"Ready:      {review['dispatch_ready_count']}")
    print(f"Blocked:    {review['blocked_count']}")
    print("=" * 80)

    for rfq in review["rfqs"]:
        status = "READY" if rfq["dispatch_ready"] else "BLOCKED"

        print(f"\n{status}: {rfq['supplier_name']}")
        print(f"  RFQ Ref: {rfq['rfq_reference']}")
        print(f"  Email: {rfq['email']}")
        print(f"  Items: {rfq['total_items']}")
        print(f"  Value: R{rfq['total_estimated_value']:,.2f}")
        print(f"  Due: {rfq['response_due_at']}")
        print(f"  File: {rfq['rfq_file_path']}")

        if rfq["issues"]:
            print(f"  Issues: {', '.join(rfq['issues'])}")

    print("\nReview file written:")
    print(REVIEW_OUTPUT_PATH)


if __name__ == "__main__":
    review = build_dispatch_review()
    print_review_report(review)
