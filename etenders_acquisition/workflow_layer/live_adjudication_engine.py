import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("runtime/workflow/workflow_layer.db")
QUOTE_INGESTION_PATH = Path("runtime/supplier_responses/quote_ingestion_summary.json")
ADJUDICATION_OUTPUT_PATH = Path("runtime/adjudication/live_adjudication_summary.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def load_quote_ingestion():
    if not QUOTE_INGESTION_PATH.exists():
        raise FileNotFoundError(
            f"Quote ingestion summary not found: {QUOTE_INGESTION_PATH}. "
            "Run quote_ingestor first."
        )

    with open(QUOTE_INGESTION_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("quotes", [])


def ensure_adjudication_table():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS adjudication_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tender_id TEXT,
        supplier_name TEXT NOT NULL,
        rfq_reference TEXT NOT NULL,
        decision TEXT,
        reason TEXT,
        commercial_score REAL,
        risk_score REAL,
        final_score REAL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def get_supplier_reliability(supplier_name):
    if supplier_name == "Bearing Man Group":
        return 75

    if supplier_name == "Builders Warehouse":
        return 65

    return 60


def calculate_commercial_score(variance_pct):
    if variance_pct <= -5:
        return 95
    if variance_pct <= -2:
        return 85
    if variance_pct <= 0:
        return 75
    if variance_pct <= 5:
        return 60
    if variance_pct <= 10:
        return 45
    return 25


def calculate_risk_score(supplier_reliability, variance_pct, response_status):
    score = 100

    if supplier_reliability < 70:
        score -= 15

    if variance_pct < -10:
        score -= 20

    if variance_pct > 5:
        score -= 20

    if response_status != "quote_ingested":
        score -= 30

    return max(score, 0)


def calculate_final_score(commercial_score, risk_score, supplier_reliability):
    return round(
        (commercial_score * 0.45)
        + (risk_score * 0.35)
        + (supplier_reliability * 0.20),
        2
    )


def recommendation_from_score(score, variance_pct):
    if score >= 80 and variance_pct <= 0:
        return "RECOMMEND_AWARD"

    if score >= 65:
        return "RECOMMEND_NEGOTIATE"

    return "HOLD_FOR_REVIEW"


def store_adjudication_decision(decision):
    """
    Idempotent persistence:
    one latest adjudication decision per RFQ reference.
    Refreshing the API will not duplicate rows.
    """

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    DELETE FROM adjudication_decisions
    WHERE rfq_reference = ?
    """, (decision["rfq_reference"],))

    cur.execute("""
    INSERT INTO adjudication_decisions (
        tender_id,
        supplier_name,
        rfq_reference,
        decision,
        reason,
        commercial_score,
        risk_score,
        final_score,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        decision["tender_id"],
        decision["supplier_name"],
        decision["rfq_reference"],
        decision["decision"],
        decision["reason"],
        decision["commercial_score"],
        decision["risk_score"],
        decision["final_score"],
        utc_now()
    ))

    conn.commit()
    conn.close()


def run_live_adjudication(tender_id="FINAL-TENDER"):
    ensure_adjudication_table()

    quotes = load_quote_ingestion()
    decisions = []

    for quote in quotes:
        supplier_name = quote["supplier_name"]
        variance_pct = float(quote.get("variance_pct") or 0)
        response_status = quote.get("status")

        supplier_reliability = get_supplier_reliability(supplier_name)
        commercial_score = calculate_commercial_score(variance_pct)

        risk_score = calculate_risk_score(
            supplier_reliability=supplier_reliability,
            variance_pct=variance_pct,
            response_status=response_status
        )

        final_score = calculate_final_score(
            commercial_score=commercial_score,
            risk_score=risk_score,
            supplier_reliability=supplier_reliability
        )

        decision = recommendation_from_score(
            score=final_score,
            variance_pct=variance_pct
        )

        reason = (
            f"Quoted total R{quote['quoted_total']:,.2f} versus target "
            f"R{quote['target_total']:,.2f}; variance {variance_pct:.2f}%; "
            f"supplier reliability {supplier_reliability}; "
            f"commercial score {commercial_score}; risk score {risk_score}."
        )

        decision_payload = {
            "tender_id": tender_id,
            "supplier_name": supplier_name,
            "rfq_reference": quote["rfq_reference"],
            "target_total": quote["target_total"],
            "quoted_total": quote["quoted_total"],
            "variance": quote["variance"],
            "variance_pct": variance_pct,
            "supplier_reliability": supplier_reliability,
            "commercial_score": commercial_score,
            "risk_score": risk_score,
            "final_score": final_score,
            "decision": decision,
            "reason": reason
        }

        store_adjudication_decision(decision_payload)
        decisions.append(decision_payload)

        print(
            f"ADJUDICATED: {supplier_name} | "
            f"{decision} | Score {final_score}"
        )

    ADJUDICATION_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "generated_at": utc_now(),
        "tender_id": tender_id,
        "total_decisions": len(decisions),
        "recommended_awards": sum(
            1 for d in decisions if d["decision"] == "RECOMMEND_AWARD"
        ),
        "recommended_negotiations": sum(
            1 for d in decisions if d["decision"] == "RECOMMEND_NEGOTIATE"
        ),
        "held_for_review": sum(
            1 for d in decisions if d["decision"] == "HOLD_FOR_REVIEW"
        ),
        "decisions": decisions
    }

    with open(ADJUDICATION_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Live adjudication summary written: {ADJUDICATION_OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    run_live_adjudication()
