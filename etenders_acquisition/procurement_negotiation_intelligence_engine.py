#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SUPPLIER_LEARNING_FILE = (
    RUNTIME_DIR
    / "supplier_learning"
    / "supplier_feedback_register.json"
)

SUPPLIER_RELIABILITY_FILE = (
    RUNTIME_DIR
    / "supplier_market_intelligence"
    / "supplier_reliability_v2_scorecards.json"
)

SUBMISSION_FILE = (
    RUNTIME_DIR
    / "submission_pack"
    / "final_submission_pricing_schedule.json"
)

OUT_DIR = RUNTIME_DIR / "procurement_negotiation_intelligence"

NEGOTIATION_FILE = OUT_DIR / "procurement_negotiation_plan.json"
BAFO_FILE = OUT_DIR / "best_and_final_offer_simulation.json"
SUMMARY_FILE = OUT_DIR / "procurement_negotiation_summary.json"


CATEGORY_DISCOUNT_BANDS = {
    "stationery": (0.08, 0.18),
    "general_supply": (0.05, 0.12),
    "building_material": (0.04, 0.10),
    "ppe": (0.06, 0.16),
    "cleaning": (0.06, 0.14),
    "furniture": (0.05, 0.12),
    "electrical": (0.03, 0.08),
    "mechanical": (0.02, 0.07),
    "ict": (0.03, 0.10),
    "medical": (0.02, 0.06),
}

LEVERAGE_BY_PRIORITY = {
    "CRITICAL": 0.04,
    "HIGH": 0.03,
    "MEDIUM": 0.015,
    "LOW": 0.00,
}


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


def build_reliability_lookup(data):
    lookup = {}

    for card in data.get("supplier_scorecards", []):
        lookup[card.get("supplier")] = card

    return lookup


def select_target_suppliers(category, reliability_lookup):
    suppliers = list(reliability_lookup.values())

    if not suppliers:
        return []

    preferred = []

    for s in suppliers:
        supplier = s.get("supplier", "")

        if category == "mechanical" and (
            "Bearing" in supplier or "BMG" in supplier
        ):
            preferred.append(s)

        elif category in ["building_material", "general_supply", "stationery"] and (
            "Builders" in supplier or "RS" in supplier
        ):
            preferred.append(s)

        elif category == "electrical" and (
            "RS" in supplier or "BMG" in supplier
        ):
            preferred.append(s)

        elif category == "ppe":
            preferred.append(s)

    if not preferred:
        preferred = suppliers

    preferred = sorted(
        preferred,
        key=lambda x: x.get("adjusted_reliability_score", 0),
        reverse=True,
    )

    return [
        {
            "supplier": x.get("supplier"),
            "reliability_score": x.get("adjusted_reliability_score"),
            "reliability_band": x.get("adjusted_reliability_band"),
        }
        for x in preferred[:3]
    ]


def discount_band(category, priority):
    low, high = CATEGORY_DISCOUNT_BANDS.get(
        category or "general_supply",
        (0.04, 0.10),
    )

    leverage = LEVERAGE_BY_PRIORITY.get(priority or "LOW", 0)

    low = min(0.30, low + leverage)
    high = min(0.35, high + leverage)

    return low, high


def negotiate_line(item, reliability_lookup):
    category = item.get("category") or "general_supply"
    priority = item.get("priority") or "LOW"
    value = money(item.get("submission_total"))

    low_disc, high_disc = discount_band(category, priority)

    conservative_saving = money(value * low_disc)
    aggressive_saving = money(value * high_disc)

    recommended_saving = money((conservative_saving + aggressive_saving) / 2)

    target_suppliers = select_target_suppliers(category, reliability_lookup)

    walkaway_discount = round(high_disc + 0.03, 4)
    walkaway_price = money(value * (1 - walkaway_discount))

    if priority == "CRITICAL":
        strategy = "MANDATORY_NEGOTIATION_BEFORE_SUBMISSION"
    elif priority == "HIGH":
        strategy = "NEGOTIATE_BEFORE_FINAL_PRICE"
    elif priority == "MEDIUM":
        strategy = "VALIDATE_AND_NEGOTIATE_IF_TIME_ALLOWS"
    else:
        strategy = "STANDARD_PROCUREMENT"

    return {
        "line_no": item.get("line_no"),
        "feedback_type": item.get("feedback_type"),
        "priority": priority,
        "category": category,
        "description": item.get("description"),
        "current_submission_total": value,
        "target_suppliers": target_suppliers,
        "conservative_discount_pct": round(low_disc * 100, 2),
        "aggressive_discount_pct": round(high_disc * 100, 2),
        "conservative_saving": conservative_saving,
        "aggressive_saving": aggressive_saving,
        "recommended_target_saving": recommended_saving,
        "walkaway_discount_pct": round(walkaway_discount * 100, 2),
        "walkaway_price": walkaway_price,
        "negotiation_strategy": strategy,
        "recommended_questions": [
            "Can you improve pricing based on volume?",
            "Confirm validity period and delivery lead time.",
            "Confirm specification compliance and brand/OEM equivalence.",
            "Confirm whether transport, escalation, and packaging are included.",
        ],
    }


def main():
    feedback_data = load_json(SUPPLIER_LEARNING_FILE, default={})
    reliability_data = load_json(SUPPLIER_RELIABILITY_FILE, default={})
    submission_data = load_json(SUBMISSION_FILE, default={})

    reliability_lookup = build_reliability_lookup(reliability_data)

    feedback_items = feedback_data.get("feedback_register", [])

    negotiation_lines = [
        negotiate_line(item, reliability_lookup)
        for item in feedback_items
    ]

    total_current_value = money(
        sum(x["current_submission_total"] for x in negotiation_lines)
    )

    total_conservative_saving = money(
        sum(x["conservative_saving"] for x in negotiation_lines)
    )

    total_aggressive_saving = money(
        sum(x["aggressive_saving"] for x in negotiation_lines)
    )

    total_recommended_saving = money(
        sum(x["recommended_target_saving"] for x in negotiation_lines)
    )

    current_bid = money(
        submission_data.get("summary", {}).get("final_submission_value")
    )

    bafo_conservative = money(current_bid - total_conservative_saving)
    bafo_recommended = money(current_bid - total_recommended_saving)
    bafo_aggressive = money(current_bid - total_aggressive_saving)

    priority_counts = Counter(x["priority"] for x in negotiation_lines)
    category_counts = Counter(x["category"] for x in negotiation_lines)
    strategy_counts = Counter(x["negotiation_strategy"] for x in negotiation_lines)

    summary = {
        "generated_at": now_iso(),
        "negotiation_lines": len(negotiation_lines),
        "current_bid_value": current_bid,
        "negotiation_exposure_value": total_current_value,
        "conservative_saving_potential": total_conservative_saving,
        "recommended_saving_target": total_recommended_saving,
        "aggressive_saving_potential": total_aggressive_saving,
        "bafo_conservative_value": bafo_conservative,
        "bafo_recommended_value": bafo_recommended,
        "bafo_aggressive_value": bafo_aggressive,
        "priority_counts": dict(priority_counts),
        "category_counts": dict(category_counts),
        "strategy_counts": dict(strategy_counts),
    }

    negotiation_plan = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "negotiation_lines": negotiation_lines,
    }

    bafo = {
        "generated_at": summary["generated_at"],
        "current_bid_value": current_bid,
        "bafo_scenarios": {
            "conservative": {
                "saving": total_conservative_saving,
                "bafo_value": bafo_conservative,
            },
            "recommended": {
                "saving": total_recommended_saving,
                "bafo_value": bafo_recommended,
            },
            "aggressive": {
                "saving": total_aggressive_saving,
                "bafo_value": bafo_aggressive,
            },
        },
    }

    write_json(NEGOTIATION_FILE, negotiation_plan)
    write_json(BAFO_FILE, bafo)
    write_json(SUMMARY_FILE, summary)

    print(f"Negotiation plan written: {NEGOTIATION_FILE}")
    print(f"BAFO simulation written: {BAFO_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Negotiation lines: {summary['negotiation_lines']}")
    print(f"Current bid value: R{summary['current_bid_value']:,.2f}")
    print(f"Recommended saving target: R{summary['recommended_saving_target']:,.2f}")
    print(f"BAFO recommended value: R{summary['bafo_recommended_value']:,.2f}")


if __name__ == "__main__":
    main()
