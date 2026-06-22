#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

ESTIMATES_FILE = (
    RUNTIME_DIR
    / "historical_price_estimator"
    / "estimated_pricing.json"
)

MEMORY_FILE = (
    RUNTIME_DIR
    / "supplier_price_memory"
    / "supplier_price_memory.json"
)

OUT_DIR = RUNTIME_DIR / "bid_strategy"

STRATEGY_FILE = OUT_DIR / "bid_strategy_report.json"
PROFITABILITY_FILE = OUT_DIR / "tender_profitability_report.json"
SUMMARY_FILE = OUT_DIR / "bid_strategy_summary.json"


BASE_MARGIN_BY_CATEGORY = {
    "general_supply": 0.18,
    "stationery": 0.16,
    "furniture": 0.20,
    "mechanical": 0.28,
    "electrical": 0.24,
    "ppe": 0.25,
    "building_material": 0.17,
    "cleaning": 0.18,
    "ict": 0.22,
    "medical": 0.30,
}


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


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def margin_for_item(item):
    category = item.get("category") or "general_supply"
    confidence = item.get("confidence") or "NO_MATCH"

    margin = BASE_MARGIN_BY_CATEGORY.get(category, 0.20)
    flags = []

    if confidence == "HIGH":
        margin -= 0.02
    elif confidence == "MEDIUM":
        margin += 0.02
        flags.append("medium_confidence")
    elif confidence == "LOW":
        margin += 0.06
        flags.append("low_confidence")
    else:
        margin += 0.12
        flags.append("no_match")

    if category in ["mechanical", "electrical", "medical"]:
        margin += 0.03
        flags.append("specialized_category")

    if item.get("matched_supplier") is None:
        margin += 0.05
        flags.append("no_supplier_match")

    margin = max(0.10, min(margin, 0.45))

    return margin, flags


def competitiveness(margin):
    pct = margin * 100

    if pct <= 15:
        return "VERY_COMPETITIVE"

    if pct <= 22:
        return "COMPETITIVE"

    if pct <= 30:
        return "BALANCED"

    if pct <= 38:
        return "RISKY"

    return "HIGH_RISK"


def line_decision(item, margin, flags):
    confidence = item.get("confidence")
    estimate_status = item.get("estimate_status")

    if estimate_status != "ESTIMATED":
        return "REVIEW"

    if confidence == "HIGH" and margin <= 0.30:
        return "SUBMIT"

    if confidence in ["MEDIUM", "LOW"]:
        return "REVIEW"

    if "no_supplier_match" in flags:
        return "REVIEW"

    return "REVIEW"


def build_strategy_lines(estimates):
    strategy_lines = []

    for item in estimates:
        estimated_total = money(item.get("estimated_total"))

        margin, margin_flags = margin_for_item(item)

        sell_price = money(estimated_total * (1 + margin))
        gross_profit = money(sell_price - estimated_total)

        decision = line_decision(item, margin, margin_flags)

        strategy_lines.append({
            "description": item.get("description"),
            "category": item.get("category"),
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
            "estimated_cost": estimated_total,
            "recommended_margin_pct": round(margin * 100, 2),
            "recommended_sell_price": sell_price,
            "gross_profit": gross_profit,
            "confidence": item.get("confidence"),
            "match_score": item.get("match_score"),
            "matched_supplier": item.get("matched_supplier"),
            "competitiveness": competitiveness(margin),
            "decision": decision,
            "risk_flags": margin_flags,
            "matched_description": item.get("matched_description"),
        })

    return strategy_lines


def main():
    estimate_data = load_json(ESTIMATES_FILE, default={})
    memory_data = load_json(MEMORY_FILE, default={})

    estimates = estimate_data.get("estimates", [])
    estimated = [
        e for e in estimates
        if e.get("estimate_status") == "ESTIMATED"
        and e.get("estimated_total") is not None
    ]

    lines = build_strategy_lines(estimated)

    total_cost = money(sum(x["estimated_cost"] for x in lines))
    total_sell = money(sum(x["recommended_sell_price"] for x in lines))
    total_profit = money(sum(x["gross_profit"] for x in lines))

    avg_margin = round((total_profit / total_cost) * 100, 2) if total_cost else 0

    decision_counts = Counter(x["decision"] for x in lines)
    confidence_counts = Counter(x["confidence"] for x in lines)
    category_counts = Counter(x["category"] or "unknown" for x in lines)
    competitiveness_counts = Counter(x["competitiveness"] for x in lines)

    submit_lines = [x for x in lines if x["decision"] == "SUBMIT"]
    review_lines = [x for x in lines if x["decision"] == "REVIEW"]

    submit_value = money(sum(x["recommended_sell_price"] for x in submit_lines))
    review_value = money(sum(x["recommended_sell_price"] for x in review_lines))

    total_candidates = estimate_data.get("summary", {}).get("candidate_items", len(estimates))
    coverage_pct = round((len(estimated) / total_candidates) * 100, 2) if total_candidates else 0

    if coverage_pct >= 70 and decision_counts.get("SUBMIT", 0) >= decision_counts.get("REVIEW", 0):
        overall_decision = "SUBMIT"
    elif coverage_pct >= 45:
        overall_decision = "REVIEW"
    else:
        overall_decision = "DO_NOT_SUBMIT"

    summary = {
        "generated_at": now_iso(),
        "total_candidate_items": total_candidates,
        "estimated_items_used": len(lines),
        "pricing_coverage_pct": coverage_pct,
        "total_estimated_cost": total_cost,
        "total_recommended_sell_value": total_sell,
        "total_projected_profit": total_profit,
        "average_margin_pct": avg_margin,
        "submit_lines": len(submit_lines),
        "review_lines": len(review_lines),
        "submit_value": submit_value,
        "review_value": review_value,
        "overall_decision": overall_decision,
        "decision_counts": dict(decision_counts),
        "confidence_counts": dict(confidence_counts),
        "category_counts": dict(category_counts),
        "competitiveness_counts": dict(competitiveness_counts),
        "supplier_memory_records": len(memory_data.get("price_memory", {})),
    }

    report = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "strategy_lines": lines,
        "submit_lines": submit_lines,
        "review_lines": review_lines[:500],
    }

    profitability = {
        "generated_at": summary["generated_at"],
        "overall_decision": overall_decision,
        "total_estimated_cost": total_cost,
        "total_recommended_sell_value": total_sell,
        "total_projected_profit": total_profit,
        "average_margin_pct": avg_margin,
        "pricing_coverage_pct": coverage_pct,
        "category_counts": dict(category_counts),
        "decision_counts": dict(decision_counts),
    }

    write_json(STRATEGY_FILE, report)
    write_json(PROFITABILITY_FILE, profitability)
    write_json(SUMMARY_FILE, summary)

    print(f"Bid strategy written: {STRATEGY_FILE}")
    print(f"Profitability report written: {PROFITABILITY_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Overall decision: {overall_decision}")
    print(f"Pricing coverage: {coverage_pct}%")
    print(f"Estimated cost: R{total_cost:,.2f}")
    print(f"Recommended sell: R{total_sell:,.2f}")
    print(f"Projected profit: R{total_profit:,.2f}")
    print(f"Average margin: {avg_margin}%")


if __name__ == "__main__":
    main()
