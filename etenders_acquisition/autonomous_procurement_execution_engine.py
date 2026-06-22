#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

NEGOTIATION_FILE = (
    RUNTIME_DIR
    / "procurement_negotiation_intelligence"
    / "procurement_negotiation_plan.json"
)

AWARD_FILE = (
    RUNTIME_DIR
    / "award_prediction"
    / "tender_award_prediction_summary.json"
)

SUPPLIER_FILE = (
    RUNTIME_DIR
    / "supplier_market_intelligence"
    / "supplier_reliability_v2_scorecards.json"
)

LEARNING_FILE = (
    RUNTIME_DIR
    / "supplier_learning"
    / "supplier_feedback_register.json"
)

OUT_DIR = RUNTIME_DIR / "autonomous_procurement_execution"

EXECUTION_QUEUE_FILE = OUT_DIR / "procurement_execution_queue.json"
SUPPLIER_OUTREACH_FILE = OUT_DIR / "supplier_outreach_plan.json"
EXECUTIVE_REPORT_FILE = OUT_DIR / "executive_bid_board_report.json"
SUBMISSION_GATE_FILE = OUT_DIR / "submission_readiness_gate.json"
SUMMARY_FILE = OUT_DIR / "autonomous_procurement_execution_summary.json"


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


def execution_priority(priority):
    if priority == "CRITICAL":
        return 1
    if priority == "HIGH":
        return 2
    if priority == "MEDIUM":
        return 3
    return 4


def readiness_gate(award_summary, feedback_register):
    score = award_summary.get("base_award_probability_score", 0)

    open_critical = sum(
        1 for x in feedback_register
        if x.get("priority") == "CRITICAL"
    )

    open_high = sum(
        1 for x in feedback_register
        if x.get("priority") == "HIGH"
    )

    if score < 35:
        return {
            "status": "BLOCKED",
            "decision": "DO_NOT_SUBMIT",
            "reason": "Award probability too low",
        }

    if open_critical > 0:
        return {
            "status": "BLOCKED",
            "decision": "NEGOTIATE_AND_REVIEW",
            "reason": "Critical unresolved commercial lines",
        }

    if open_high > 5:
        return {
            "status": "REVIEW_REQUIRED",
            "decision": "PROCUREMENT_REVIEW",
            "reason": "High-risk procurement exposure remains",
        }

    return {
        "status": "READY",
        "decision": "SUBMIT",
        "reason": "Commercial governance checks passed",
    }


def build_execution_queue(negotiation_lines):
    deduped = {}

    for line in negotiation_lines:
        key = (
            str(line.get("line_no") or "").strip(),
            str(line.get("description") or "").strip().lower(),
        )

        item = {
            "created_at": now_iso(),
            "line_no": line.get("line_no"),
            "execution_priority": execution_priority(line.get("priority")),
            "priority": line.get("priority"),
            "category": line.get("category"),
            "description": line.get("description"),
            "current_submission_total": line.get("current_submission_total"),
            "recommended_target_saving": line.get("recommended_target_saving"),
            "walkaway_price": line.get("walkaway_price"),
            "strategy": line.get("negotiation_strategy"),
            "assigned_to": "PROCUREMENT_AI",
            "execution_status": "OPEN",
            "merged_duplicate_count": 1,
        }

        if key not in deduped:
            deduped[key] = item
            continue

        existing = deduped[key]
        existing["merged_duplicate_count"] += 1

        if item["execution_priority"] < existing["execution_priority"]:
            item["merged_duplicate_count"] = existing["merged_duplicate_count"]
            deduped[key] = item
        else:
            existing["recommended_target_saving"] = max(
                money(existing.get("recommended_target_saving")),
                money(item.get("recommended_target_saving")),
            )
            existing["walkaway_price"] = min(
                money(existing.get("walkaway_price")),
                money(item.get("walkaway_price")),
            )

    queue = sorted(
        deduped.values(),
        key=lambda x: (x["execution_priority"], -money(x.get("recommended_target_saving"))),
    )

    return queue


def build_supplier_outreach(negotiation_lines):
    outreach = []

    for line in negotiation_lines:

        for supplier in line.get("target_suppliers", []):

            outreach.append({
                "created_at": now_iso(),
                "supplier": supplier.get("supplier"),
                "supplier_reliability": supplier.get(
                    "reliability_score"
                ),
                "supplier_band": supplier.get(
                    "reliability_band"
                ),
                "line_description": line.get("description"),
                "category": line.get("category"),
                "target_price": line.get("walkaway_price"),
                "current_submission_total": line.get(
                    "current_submission_total"
                ),
                "recommended_questions": line.get(
                    "recommended_questions"
                ),
                "outreach_status": "PENDING_RFQ",
            })

    return outreach


def executive_report(
    award_summary,
    negotiation_summary,
    gate,
    supplier_cards,
):
    top_suppliers = [
        {
            "supplier": x.get("supplier"),
            "score": x.get("adjusted_reliability_score"),
            "band": x.get("adjusted_reliability_band"),
        }
        for x in supplier_cards[:5]
    ]

    return {
        "generated_at": now_iso(),
        "executive_decision": gate["decision"],
        "submission_gate_status": gate["status"],
        "decision_reason": gate["reason"],
        "award_probability_score": award_summary.get(
            "base_award_probability_score"
        ),
        "award_probability_band": award_summary.get(
            "base_award_probability_band"
        ),
        "recommended_bafo_value": negotiation_summary.get(
            "bafo_recommended_value"
        ),
        "saving_opportunity": negotiation_summary.get(
            "recommended_saving_target"
        ),
        "top_suppliers": top_suppliers,
        "board_recommendations": [
            "Obtain live supplier quotations",
            "Resolve all critical commercial review items",
            "Reduce commodity exposure before submission",
            "Recalculate submission after negotiated pricing",
            "Run adjudication review again before final submission",
        ],
    }


def main():
    negotiation = load_json(NEGOTIATION_FILE, default={})
    award = load_json(AWARD_FILE, default={})
    suppliers = load_json(SUPPLIER_FILE, default={})
    learning = load_json(LEARNING_FILE, default={})

    negotiation_summary = negotiation.get("summary", {})
    negotiation_lines = negotiation.get("negotiation_lines", [])

    award_summary = award
    supplier_cards = suppliers.get("supplier_scorecards", [])
    feedback_register = learning.get("feedback_register", [])

    gate = readiness_gate(
        award_summary,
        feedback_register
    )

    execution_queue = build_execution_queue(
        negotiation_lines
    )

    outreach = build_supplier_outreach(
        negotiation_lines
    )

    executive = executive_report(
        award_summary,
        negotiation_summary,
        gate,
        supplier_cards,
    )

    summary = {
        "generated_at": now_iso(),
        "execution_tasks": len(execution_queue),
        "supplier_outreach_events": len(outreach),
        "submission_gate_status": gate["status"],
        "submission_decision": gate["decision"],
        "award_probability_score": award_summary.get(
            "base_award_probability_score"
        ),
        "recommended_bafo_value": negotiation_summary.get(
            "bafo_recommended_value"
        ),
        "priority_counts": dict(
            Counter(x["priority"] for x in execution_queue)
        ),
    }

    write_json(EXECUTION_QUEUE_FILE, {
        "generated_at": summary["generated_at"],
        "execution_queue": execution_queue,
    })

    write_json(SUPPLIER_OUTREACH_FILE, {
        "generated_at": summary["generated_at"],
        "supplier_outreach": outreach,
    })

    write_json(EXECUTIVE_REPORT_FILE, executive)
    write_json(SUBMISSION_GATE_FILE, gate)
    write_json(SUMMARY_FILE, summary)

    print(f"Execution queue written: {EXECUTION_QUEUE_FILE}")
    print(f"Supplier outreach written: {SUPPLIER_OUTREACH_FILE}")
    print(f"Executive report written: {EXECUTIVE_REPORT_FILE}")
    print(f"Submission gate written: {SUBMISSION_GATE_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Execution tasks: {summary['execution_tasks']}")
    print(f"Supplier outreach events: {summary['supplier_outreach_events']}")
    print(f"Submission gate: {summary['submission_gate_status']}")
    print(f"Submission decision: {summary['submission_decision']}")


if __name__ == "__main__":
    main()
