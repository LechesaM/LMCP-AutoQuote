#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

BEST_SUPPLIER_FILE = (
    RUNTIME_DIR
    / "live_supplier_responses"
    / "best_supplier_selection.json"
)

AWARD_RECOMMENDATION_FILE = (
    RUNTIME_DIR
    / "live_supplier_responses"
    / "supplier_award_recommendation.json"
)

EXEC_REPORT_FILE = (
    RUNTIME_DIR
    / "autonomous_procurement_execution"
    / "executive_bid_board_report.json"
)

OUT_DIR = RUNTIME_DIR / "final_tender_submission"

FINAL_PRICING_JSON = OUT_DIR / "final_tender_pricing_schedule.json"
FINAL_PRICING_CSV = OUT_DIR / "final_tender_pricing_schedule.csv"
SUPPLIER_AWARD_MATRIX = OUT_DIR / "supplier_award_matrix.json"
EXECUTIVE_APPROVAL_MEMO = OUT_DIR / "executive_tender_approval_memo.json"
SUMMARY_FILE = OUT_DIR / "final_tender_submission_summary.json"


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


def write_csv(path, rows):
    fields = [
        "line_no",
        "description",
        "category",
        "selected_supplier",
        "supplier_reliability",
        "original_submission_value",
        "final_supplier_quote",
        "saving",
        "saving_pct",
        "quotes_received",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for idx, row in enumerate(rows, start=1):
            writer.writerow({
                "line_no": idx,
                "description": row.get("description"),
                "category": row.get("category"),
                "selected_supplier": row.get("selected_supplier"),
                "supplier_reliability": row.get("selected_supplier_reliability"),
                "original_submission_value": row.get("original_submission_value"),
                "final_supplier_quote": row.get("selected_quote_value"),
                "saving": row.get("final_saving"),
                "saving_pct": row.get("final_saving_pct"),
                "quotes_received": row.get("quotes_received"),
            })


def build_approval_status(summary, exec_report):
    gate_status = exec_report.get("submission_gate_status")
    award_score = money(exec_report.get("award_probability_score"))
    saving_pct = money(summary.get("true_saving_pct"))

    if gate_status == "BLOCKED" and award_score < 45:
        return "HOLD_FOR_EXECUTIVE_REVIEW"

    if saving_pct >= 8 and award_score >= 40:
        return "APPROVE_AFTER_SUPPLIER_CONFIRMATION"

    return "REVIEW_REQUIRED"


def main():
    best_supplier = load_json(BEST_SUPPLIER_FILE, default={})
    award_recommendation = load_json(AWARD_RECOMMENDATION_FILE, default={})
    exec_report = load_json(EXEC_REPORT_FILE, default={})

    selected_lines = best_supplier.get("selected_lines", [])
    best_summary = best_supplier.get("summary", {})
    supplier_awards = award_recommendation.get("supplier_awards", [])

    total_original = money(best_summary.get("total_original_value"))
    total_final = money(best_summary.get("total_best_supplier_value"))
    total_saving = money(best_summary.get("true_saving"))
    saving_pct = money(best_summary.get("true_saving_pct"))

    approval_status = build_approval_status(best_summary, exec_report)

    generated_at = now_iso()

    pricing_output = {
        "generated_at": generated_at,
        "summary": {
            "final_submission_status": approval_status,
            "unique_items": len(selected_lines),
            "original_value": total_original,
            "final_supplier_value": total_final,
            "total_saving": total_saving,
            "saving_pct": saving_pct,
        },
        "pricing_schedule": selected_lines,
    }

    supplier_matrix = {
        "generated_at": generated_at,
        "supplier_awards": supplier_awards,
    }

    approval_memo = {
        "generated_at": generated_at,
        "approval_status": approval_status,
        "executive_decision_before_supplier_selection": exec_report.get("executive_decision"),
        "submission_gate_before_supplier_selection": exec_report.get("submission_gate_status"),
        "award_probability_score_before_supplier_selection": exec_report.get("award_probability_score"),
        "final_supplier_value": total_final,
        "realized_saving": total_saving,
        "realized_saving_pct": saving_pct,
        "recommended_next_actions": [
            "Obtain written supplier confirmations for selected prices.",
            "Confirm validity periods and delivery lead times.",
            "Update final BOQ submission pricing using selected supplier values.",
            "Rerun adjudication and award prediction after confirmed supplier quotes.",
            "Do not submit until all critical lines are backed by supplier confirmations.",
        ],
    }

    summary = {
        "generated_at": generated_at,
        "final_submission_status": approval_status,
        "unique_items": len(selected_lines),
        "original_value": total_original,
        "final_supplier_value": total_final,
        "total_saving": total_saving,
        "saving_pct": saving_pct,
        "supplier_count": len(supplier_awards),
        "pricing_csv": str(FINAL_PRICING_CSV),
        "pricing_json": str(FINAL_PRICING_JSON),
    }

    write_json(FINAL_PRICING_JSON, pricing_output)
    write_json(SUPPLIER_AWARD_MATRIX, supplier_matrix)
    write_json(EXECUTIVE_APPROVAL_MEMO, approval_memo)
    write_json(SUMMARY_FILE, summary)
    write_csv(FINAL_PRICING_CSV, selected_lines)

    print(f"Final pricing JSON written: {FINAL_PRICING_JSON}")
    print(f"Final pricing CSV written: {FINAL_PRICING_CSV}")
    print(f"Supplier award matrix written: {SUPPLIER_AWARD_MATRIX}")
    print(f"Executive approval memo written: {EXECUTIVE_APPROVAL_MEMO}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Status: {summary['final_submission_status']}")
    print(f"Unique items: {summary['unique_items']}")
    print(f"Final supplier value: R{summary['final_supplier_value']:,.2f}")
    print(f"Total saving: R{summary['total_saving']:,.2f}")
    print(f"Saving pct: {summary['saving_pct']}%")


if __name__ == "__main__":
    main()
