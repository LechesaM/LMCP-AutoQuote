#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

RFQ_FILE = (
    RUNTIME_DIR
    / "supplier_outreach_emails"
    / "supplier_consolidated_rfq_emails_deduped.json"
)

OUT_DIR = RUNTIME_DIR / "live_supplier_responses"

RESPONSES_FILE = OUT_DIR / "live_supplier_response_register.json"
SAVINGS_FILE = OUT_DIR / "supplier_savings_analysis.json"
BAFO_FILE = OUT_DIR / "bafo_recalculation.json"
SUMMARY_FILE = OUT_DIR / "live_supplier_response_summary.json"


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


def simulate_supplier_response(item):
    current = money(item.get("current_submission_total"))
    target = money(item.get("target_price"))

    midpoint = round((current + target) / 2, 2)

    achieved_saving = round(current - midpoint, 2)

    saving_pct = 0
    if current > 0:
        saving_pct = round((achieved_saving / current) * 100, 2)

    if saving_pct >= 18:
        outcome = "EXCELLENT"
    elif saving_pct >= 12:
        outcome = "GOOD"
    elif saving_pct >= 7:
        outcome = "MODERATE"
    else:
        outcome = "WEAK"

    return {
        "quoted_price": midpoint,
        "achieved_saving": achieved_saving,
        "saving_pct": saving_pct,
        "negotiation_outcome": outcome,
    }


def main():
    rfqs = load_json(RFQ_FILE, default={})

    supplier_emails = rfqs.get(
        "consolidated_supplier_emails",
        [],
    )

    response_register = []

    total_original = 0
    total_quoted = 0
    total_savings = 0

    supplier_savings = {}

    for supplier_bundle in supplier_emails:

        supplier = supplier_bundle.get("supplier")

        bundle_original = 0
        bundle_quoted = 0
        bundle_savings = 0

        responses = []

        for item in supplier_bundle.get("items", []):

            simulation = simulate_supplier_response(item)

            current = money(
                item.get("current_submission_total")
            )

            quoted = money(
                simulation.get("quoted_price")
            )

            saving = money(
                simulation.get("achieved_saving")
            )

            bundle_original += current
            bundle_quoted += quoted
            bundle_savings += saving

            total_original += current
            total_quoted += quoted
            total_savings += saving

            responses.append({
                "description": item.get("description"),
                "category": item.get("category"),
                "original_submission_value": current,
                "supplier_quoted_value": quoted,
                "achieved_saving": saving,
                "saving_pct": simulation.get(
                    "saving_pct"
                ),
                "negotiation_outcome": simulation.get(
                    "negotiation_outcome"
                ),
            })

        supplier_savings[supplier] = {
            "supplier": supplier,
            "original_value": round(bundle_original, 2),
            "quoted_value": round(bundle_quoted, 2),
            "achieved_saving": round(bundle_savings, 2),
            "saving_pct": round(
                (bundle_savings / bundle_original) * 100,
                2,
            ) if bundle_original else 0,
        }

        response_register.append({
            "supplier": supplier,
            "supplier_band": supplier_bundle.get(
                "supplier_band"
            ),
            "supplier_reliability": supplier_bundle.get(
                "supplier_reliability"
            ),
            "line_count": len(responses),
            "responses": responses,
        })

    recalculated_bafo = round(total_quoted, 2)

    savings_pct = 0
    if total_original > 0:
        savings_pct = round(
            (total_savings / total_original) * 100,
            2,
        )

    if savings_pct >= 15:
        award_improvement = "MAJOR"
        adjusted_award_score = 68
    elif savings_pct >= 10:
        award_improvement = "STRONG"
        adjusted_award_score = 57
    elif savings_pct >= 5:
        award_improvement = "MODERATE"
        adjusted_award_score = 48
    else:
        award_improvement = "LOW"
        adjusted_award_score = 35

    response_output = {
        "generated_at": now_iso(),
        "supplier_responses": response_register,
    }

    savings_output = {
        "generated_at": now_iso(),
        "supplier_savings": list(
            supplier_savings.values()
        ),
    }

    bafo_output = {
        "generated_at": now_iso(),
        "original_submission_value": round(
            total_original,
            2,
        ),
        "recalculated_bafo_value": recalculated_bafo,
        "achieved_total_saving": round(
            total_savings,
            2,
        ),
        "saving_pct": savings_pct,
        "award_probability_improvement": (
            award_improvement
        ),
        "adjusted_award_probability_score": (
            adjusted_award_score
        ),
    }

    summary = {
        "generated_at": now_iso(),
        "suppliers_processed": len(response_register),
        "total_original_value": round(
            total_original,
            2,
        ),
        "total_quoted_value": round(
            total_quoted,
            2,
        ),
        "total_savings": round(
            total_savings,
            2,
        ),
        "saving_pct": savings_pct,
        "adjusted_award_probability_score": (
            adjusted_award_score
        ),
    }

    write_json(RESPONSES_FILE, response_output)
    write_json(SAVINGS_FILE, savings_output)
    write_json(BAFO_FILE, bafo_output)
    write_json(SUMMARY_FILE, summary)

    print(f"Supplier responses written: {RESPONSES_FILE}")
    print(f"Savings analysis written: {SAVINGS_FILE}")
    print(f"BAFO recalculation written: {BAFO_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Suppliers processed: {summary['suppliers_processed']}")
    print(f"Total savings: R{summary['total_savings']:,.2f}")
    print(f"Saving pct: {summary['saving_pct']}%")
    print(
        f"Adjusted award score: "
        f"{summary['adjusted_award_probability_score']}"
    )


if __name__ == "__main__":
    main()
