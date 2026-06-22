#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SUPPLIER_RELIABILITY_FILE = (
    RUNTIME_DIR
    / "supplier_market_intelligence"
    / "supplier_reliability_v2_scorecards.json"
)

QUOTE_INGESTION_FILE = (
    RUNTIME_DIR
    / "supplier_quote_ingestion"
    / "supplier_quote_ingestion_summary.json"
)

BID_DEFENSE_FILE = (
    RUNTIME_DIR
    / "bid_defense"
    / "intelligent_bid_defense_report.json"
)

ADJUDICATION_FILE = (
    RUNTIME_DIR
    / "ai_tender_adjudication"
    / "ai_tender_adjudication_review.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_learning"

LEARNING_MEMORY_FILE = OUT_DIR / "supplier_learning_memory.json"
SUPPLIER_FEEDBACK_FILE = OUT_DIR / "supplier_feedback_register.json"
AWARD_OUTCOME_TEMPLATE_FILE = OUT_DIR / "award_outcome_template.json"
SUMMARY_FILE = OUT_DIR / "supplier_learning_summary.json"


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


def build_supplier_memory(scorecards):
    memory = {}

    for card in scorecards:
        supplier = card.get("supplier")

        memory[supplier] = {
            "supplier": supplier,
            "current_reliability_score": card.get("adjusted_reliability_score"),
            "current_reliability_band": card.get("adjusted_reliability_band"),
            "catalog_items": card.get("catalog_items"),
            "oem_items": card.get("oem_items"),
            "learning_status": "SEEDED_BASELINE",
            "real_response_history": card.get("real_response_history", 0),
            "quote_events": [],
            "negotiation_events": [],
            "delivery_events": [],
            "award_events": [],
            "performance_flags": card.get("reliability_v2_flags", []),
        }

    return memory


def build_feedback_register(defense, adjudication):
    defense_lines = defense.get("defense_lines", [])
    reviewed_lines = adjudication.get("reviewed_lines", [])

    feedback = []

    for line in defense_lines:
        priority = line.get("negotiation_priority")

        if priority in ["CRITICAL", "HIGH"]:
            feedback.append({
                "created_at": now_iso(),
                "feedback_type": "NEGOTIATION_REQUIRED",
                "line_no": line.get("line_no"),
                "category": line.get("category"),
                "description": line.get("description"),
                "submission_total": line.get("submission_total"),
                "priority": priority,
                "recommended_actions": line.get("negotiation_actions", []),
                "status": "OPEN",
                "supplier": None,
                "actual_supplier_response": None,
                "negotiated_unit_rate": None,
                "negotiated_total": None,
                "learning_note": None,
            })

    for line in reviewed_lines:
        if line.get("adjudication_band") == "HIGH_RISK_REVIEW":
            feedback.append({
                "created_at": now_iso(),
                "feedback_type": "ADJUDICATION_RISK",
                "line_no": line.get("line_no"),
                "category": line.get("category"),
                "description": line.get("description"),
                "submission_total": line.get("submission_total"),
                "priority": "CRITICAL",
                "recommended_actions": [
                    "Obtain validated supplier quote",
                    "Confirm commercial sustainability",
                    "Record final bid-board decision",
                ],
                "status": "OPEN",
                "supplier": None,
                "actual_supplier_response": None,
                "negotiated_unit_rate": None,
                "negotiated_total": None,
                "learning_note": None,
            })

    return feedback


def award_outcome_template():
    return {
        "created_at": now_iso(),
        "instructions": "Populate this file after bid submission, client adjudication, award, supplier negotiation, or project delivery.",
        "outcomes": [
            {
                "tender_reference": None,
                "submission_value": None,
                "award_status": "PENDING",
                "awarded_value": None,
                "winning_bid_known": None,
                "winning_bid_value": None,
                "client_feedback": None,
                "clarifications_received": [],
                "supplier_events": [
                    {
                        "supplier": None,
                        "response_status": None,
                        "response_time_hours": None,
                        "quoted_value": None,
                        "negotiated_value": None,
                        "accepted": None,
                        "delivery_performance": None,
                        "quality_issues": None,
                        "notes": None,
                    }
                ],
                "post_award_costs": [
                    {
                        "line_no": None,
                        "description": None,
                        "quoted_total": None,
                        "actual_cost_total": None,
                        "variance_reason": None,
                    }
                ],
            }
        ],
    }


def main():
    reliability_data = load_json(SUPPLIER_RELIABILITY_FILE, default={})
    quote_summary = load_json(QUOTE_INGESTION_FILE, default={})
    defense = load_json(BID_DEFENSE_FILE, default={})
    adjudication = load_json(ADJUDICATION_FILE, default={})

    scorecards = reliability_data.get("supplier_scorecards", [])

    supplier_memory = build_supplier_memory(scorecards)
    feedback_register = build_feedback_register(defense, adjudication)
    outcome_template = award_outcome_template()

    feedback_counts = Counter(x["feedback_type"] for x in feedback_register)
    priority_counts = Counter(x["priority"] for x in feedback_register)

    summary = {
        "generated_at": now_iso(),
        "suppliers_in_learning_memory": len(supplier_memory),
        "feedback_items_opened": len(feedback_register),
        "feedback_type_counts": dict(feedback_counts),
        "priority_counts": dict(priority_counts),
        "seeded_environment_detected": quote_summary.get("priced_items", 0)
        == quote_summary.get("items_ingested", -1),
        "learning_phase": "BASELINE_CREATED_AWAITING_REAL_EVENTS",
    }

    write_json(LEARNING_MEMORY_FILE, {
        "generated_at": summary["generated_at"],
        "supplier_learning_memory": supplier_memory,
    })

    write_json(SUPPLIER_FEEDBACK_FILE, {
        "generated_at": summary["generated_at"],
        "feedback_register": feedback_register,
    })

    write_json(AWARD_OUTCOME_TEMPLATE_FILE, outcome_template)
    write_json(SUMMARY_FILE, summary)

    print(f"Supplier learning memory written: {LEARNING_MEMORY_FILE}")
    print(f"Supplier feedback register written: {SUPPLIER_FEEDBACK_FILE}")
    print(f"Award outcome template written: {AWARD_OUTCOME_TEMPLATE_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Suppliers in memory: {summary['suppliers_in_learning_memory']}")
    print(f"Feedback items opened: {summary['feedback_items_opened']}")
    print(f"Learning phase: {summary['learning_phase']}")


if __name__ == "__main__":
    main()
