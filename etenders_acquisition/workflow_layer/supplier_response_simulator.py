import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

RFQ_SUMMARY_PATH = Path("runtime/rfqs/rfq_orchestration_summary.json")
SIM_RESPONSE_DIR = Path("runtime/supplier_responses/simulated")
DB_PATH = Path("runtime/workflow/workflow_layer.db")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def load_rfq_summary():
    if not RFQ_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"RFQ summary not found: {RFQ_SUMMARY_PATH}"
        )

    with open(RFQ_SUMMARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def create_simulated_quote_csv(rfq):
    SIM_RESPONSE_DIR.mkdir(parents=True, exist_ok=True)

    supplier_name = rfq["supplier_name"]
    rfq_reference = rfq["rfq_reference"]
    source_rfq_path = Path(rfq["rfq_file_path"])

    if not source_rfq_path.exists():
        raise FileNotFoundError(f"RFQ CSV not found: {source_rfq_path}")

    output_path = SIM_RESPONSE_DIR / f"SIMULATED_QUOTE_{rfq_reference}.csv"

    with open(source_rfq_path, "r", encoding="utf-8") as src:
        reader = csv.DictReader(src)
        rows = list(reader)

    with open(output_path, "w", newline="", encoding="utf-8") as out:
        fieldnames = list(rows[0].keys())

        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            target_total = float(row.get("target_total") or 0)

            simulated_quote_total = round(target_total * 0.985, 2)

            row["supplier_quoted_total"] = simulated_quote_total
            row["lead_time_days"] = "5"
            row["vat_included"] = "YES"
            row["stock_available"] = "YES"
            row["commercial_exclusions"] = "None"
            row["supplier_notes"] = (
                f"Simulated supplier quote for {supplier_name}. "
                f"RFQ reference {rfq_reference}."
            )

            writer.writerow(row)

    return output_path


def record_simulated_response(rfq, quote_path):
    conn = get_conn()
    cur = conn.cursor()

    notes = json.dumps({
        "simulation": True,
        "quote_file": str(quote_path),
        "source": "supplier_response_simulator"
    })

    cur.execute("""
    INSERT INTO supplier_responses (
        rfq_reference,
        supplier_name,
        response_status,
        notes,
        received_at,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        rfq["rfq_reference"],
        rfq["supplier_name"],
        "response_received",
        notes,
        utc_now(),
        utc_now()
    ))

    cur.execute("""
    UPDATE rfq_batches
    SET status = 'response_received'
    WHERE rfq_reference = ?
    """, (rfq["rfq_reference"],))

    conn.commit()
    conn.close()


def simulate_supplier_responses():
    rfqs = load_rfq_summary()
    simulated = []

    for rfq in rfqs:
        quote_path = create_simulated_quote_csv(rfq)
        record_simulated_response(rfq, quote_path)

        simulated.append({
            "supplier_name": rfq["supplier_name"],
            "rfq_reference": rfq["rfq_reference"],
            "simulated_quote_path": str(quote_path),
            "status": "response_received"
        })

        print(
            f"SIMULATED RESPONSE: {rfq['supplier_name']} | "
            f"{rfq['rfq_reference']}"
        )

    output_path = SIM_RESPONSE_DIR / "simulated_supplier_responses.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": utc_now(),
            "total_simulated": len(simulated),
            "responses": simulated
        }, f, indent=2)

    print(f"Simulation summary written: {output_path}")
    return simulated


if __name__ == "__main__":
    simulate_supplier_responses()
