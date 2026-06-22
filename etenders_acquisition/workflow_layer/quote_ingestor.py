import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("runtime/workflow/workflow_layer.db")
SIM_RESPONSE_SUMMARY_PATH = Path(
    "runtime/supplier_responses/simulated/simulated_supplier_responses.json"
)
INGESTION_OUTPUT_PATH = Path(
    "runtime/supplier_responses/quote_ingestion_summary.json"
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def load_simulated_responses():
    if not SIM_RESPONSE_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"Simulated response summary not found: {SIM_RESPONSE_SUMMARY_PATH}. "
            "Run supplier_response_simulator first."
        )

    with open(SIM_RESPONSE_SUMMARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("responses", [])


def safe_float(value):
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").replace("R", "").strip())
    except Exception:
        return 0.0


def ingest_quote_csv(quote_path):
    quote_path = Path(quote_path)

    if not quote_path.exists():
        raise FileNotFoundError(f"Quote file not found: {quote_path}")

    rows = []

    with open(quote_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            target_total = safe_float(row.get("target_total"))
            supplier_quoted_total = safe_float(row.get("supplier_quoted_total"))

            variance = supplier_quoted_total - target_total
            variance_pct = 0.0

            if target_total:
                variance_pct = (variance / target_total) * 100

            rows.append({
                "rfq_reference": row.get("rfq_reference"),
                "supplier_name": row.get("supplier_name"),
                "item_no": row.get("item_no"),
                "category": row.get("category"),
                "description": row.get("description"),
                "target_total": round(target_total, 2),
                "supplier_quoted_total": round(supplier_quoted_total, 2),
                "variance": round(variance, 2),
                "variance_pct": round(variance_pct, 2),
                "lead_time_days": row.get("lead_time_days"),
                "vat_included": row.get("vat_included"),
                "stock_available": row.get("stock_available"),
                "commercial_exclusions": row.get("commercial_exclusions"),
                "supplier_notes": row.get("supplier_notes")
            })

    return rows


def update_supplier_response_totals(
    rfq_reference,
    supplier_name,
    quoted_total,
    notes_payload
):
    conn = get_conn()
    cur = conn.cursor()

    notes = json.dumps(notes_payload)

    cur.execute("""
    UPDATE supplier_responses
    SET
        quoted_total = ?,
        response_status = 'quote_ingested',
        notes = ?,
        received_at = ?
    WHERE rfq_reference = ?
      AND supplier_name = ?
    """, (
        quoted_total,
        notes,
        utc_now(),
        rfq_reference,
        supplier_name
    ))

    if cur.rowcount == 0:
        cur.execute("""
        INSERT INTO supplier_responses (
            rfq_reference,
            supplier_name,
            response_status,
            quoted_total,
            notes,
            received_at,
            created_at
        )
        VALUES (?, ?, 'quote_ingested', ?, ?, ?, ?)
        """, (
            rfq_reference,
            supplier_name,
            quoted_total,
            notes,
            utc_now(),
            utc_now()
        ))

    cur.execute("""
    UPDATE rfq_batches
    SET status = 'quote_ingested'
    WHERE rfq_reference = ?
    """, (rfq_reference,))

    conn.commit()
    conn.close()


def ingest_supplier_quotes():
    responses = load_simulated_responses()
    ingested = []

    for response in responses:
        quote_path = response.get("simulated_quote_path")
        rfq_reference = response.get("rfq_reference")
        supplier_name = response.get("supplier_name")

        quote_rows = ingest_quote_csv(quote_path)

        quoted_total = sum(
            row["supplier_quoted_total"]
            for row in quote_rows
        )

        target_total = sum(
            row["target_total"]
            for row in quote_rows
        )

        variance = quoted_total - target_total
        variance_pct = 0.0

        if target_total:
            variance_pct = (variance / target_total) * 100

        notes_payload = {
            "quote_file": quote_path,
            "line_count": len(quote_rows),
            "target_total": round(target_total, 2),
            "quoted_total": round(quoted_total, 2),
            "variance": round(variance, 2),
            "variance_pct": round(variance_pct, 2),
            "ingested_at": utc_now()
        }

        update_supplier_response_totals(
            rfq_reference=rfq_reference,
            supplier_name=supplier_name,
            quoted_total=round(quoted_total, 2),
            notes_payload=notes_payload
        )

        ingested.append({
            "supplier_name": supplier_name,
            "rfq_reference": rfq_reference,
            "quote_path": quote_path,
            "line_count": len(quote_rows),
            "target_total": round(target_total, 2),
            "quoted_total": round(quoted_total, 2),
            "variance": round(variance, 2),
            "variance_pct": round(variance_pct, 2),
            "status": "quote_ingested"
        })

        print(
            f"INGESTED: {supplier_name} | "
            f"{len(quote_rows)} lines | "
            f"Quoted R{quoted_total:,.2f} | "
            f"Variance {variance_pct:.2f}%"
        )

    INGESTION_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": utc_now(),
        "total_quotes_ingested": len(ingested),
        "quotes": ingested
    }

    with open(INGESTION_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Quote ingestion summary written: {INGESTION_OUTPUT_PATH}")
    return payload


if __name__ == "__main__":
    ingest_supplier_quotes()
