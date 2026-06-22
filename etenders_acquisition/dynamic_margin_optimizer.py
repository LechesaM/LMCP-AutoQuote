#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

PRICING_FILE = (
    RUNTIME_DIR
    / "procurement_category_ai"
    / "recategorized_pricing_schedule.json"
)

WIN_FILE = (
    RUNTIME_DIR
    / "commercial_intelligence"
    / "bid_win_probability_analysis.json"
)

OUT_DIR = RUNTIME_DIR / "commercial_intelligence"

OUTPUT_FILE = OUT_DIR / "dynamic_margin_optimized_bid.json"
SUMMARY_FILE = OUT_DIR / "dynamic_margin_optimizer_summary.json"


CATEGORY_FLOORS = {
    "stationery": 0.08,
    "general_supply": 0.10,
    "building_material": 0.10,
    "ppe": 0.12,
    "cleaning": 0.10,
    "furniture": 0.12,
    "electrical": 0.16,
    "mechanical": 0.18,
    "ict": 0.18,
    "medical": 0.20,
}

CATEGORY_TARGETS = {
    "stationery": 0.14,
    "general_supply": 0.16,
    "building_material": 0.15,
    "ppe": 0.18,
    "cleaning": 0.16,
    "furniture": 0.18,
    "electrical": 0.22,
    "mechanical": 0.25,
    "ict": 0.24,
    "medical": 0.28,
}

CATEGORY_CEILINGS = {
    "stationery": 0.22,
    "general_supply": 0.26,
    "building_material": 0.24,
    "ppe": 0.28,
    "cleaning": 0.24,
    "furniture": 0.28,
    "electrical": 0.32,
    "mechanical": 0.36,
    "ict": 0.35,
    "medical": 0.40,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    try:
        return round(float(value or 0), 2)
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


def clamp(value, low, high):
    return max(low, min(high, value))


def build_win_lookup(win_data):
    lookup = {}

    for line in win_data.get("line_analysis", []):
        lookup[int(line.get("line_no") or 0)] = line

    return lookup


def choose_margin(line, win):
    category = line.get("category") or "general_supply"

    floor = CATEGORY_FLOORS.get(category, 0.10)
    target = CATEGORY_TARGETS.get(category, 0.18)
    ceiling = CATEGORY_CEILINGS.get(category, 0.30)

    band = (win or {}).get("win_probability_band")
    risk_flags = (win or {}).get("risk_flags") or []

    margin = target
    reason = ["category_target"]

    if "above_market_mid" in risk_flags:
        margin -= 0.04
        reason.append("reduced_above_market_mid")

    if band == "LOW":
        margin -= 0.03
        reason.append("reduced_low_win_probability")

    if band in ["VERY_HIGH", "HIGH"]:
        margin += 0.02
        reason.append("increased_strong_win_probability")

    confidence = line.get("source_confidence")

    if confidence in ["FALLBACK_LOW", "LOW"]:
        margin += 0.03
        reason.append("risk_premium_low_confidence")

    if confidence in ["HIGH", "SKU_HIGH"]:
        margin -= 0.01
        reason.append("discount_high_confidence")

    margin = clamp(margin, floor, ceiling)

    return margin, reason


def optimize_line(line, win):
    cost_total = money(line.get("cost_total"))
    cost_unit = money(line.get("cost_unit_rate"))
    quantity = money(line.get("quantity") or 1)

    margin, reasons = choose_margin(line, win)

    optimized_unit = money(cost_unit * (1 + margin))
    optimized_total = money(optimized_unit * quantity)
    optimized_profit = money(optimized_total - cost_total)

    old_bid_total = money(line.get("bid_total"))
    old_profit = money(line.get("gross_profit"))

    return {
        "line_no": line.get("line_no"),
        "description": line.get("description"),
        "category": line.get("category"),
        "quantity": quantity,
        "unit": line.get("unit"),
        "source_confidence": line.get("source_confidence"),
        "cost_unit_rate": cost_unit,
        "cost_total": cost_total,
        "old_margin_pct": line.get("margin_pct"),
        "old_bid_total": old_bid_total,
        "old_gross_profit": old_profit,
        "optimized_margin_pct": round(margin * 100, 2),
        "optimized_unit_rate": optimized_unit,
        "optimized_bid_total": optimized_total,
        "optimized_gross_profit": optimized_profit,
        "bid_delta": money(optimized_total - old_bid_total),
        "profit_delta": money(optimized_profit - old_profit),
        "win_probability_score": (win or {}).get("win_probability_score"),
        "win_probability_band": (win or {}).get("win_probability_band"),
        "market_position": (win or {}).get("market_position"),
        "risk_flags": (win or {}).get("risk_flags") or [],
        "optimization_reasons": reasons,
    }


def main():
    pricing_data = load_json(PRICING_FILE, default={})
    win_data = load_json(WIN_FILE, default={})

    lines = pricing_data.get("pricing_schedule", [])
    win_lookup = build_win_lookup(win_data)

    optimized = []

    for line in lines:
        line_no = int(line.get("line_no") or 0)
        win = win_lookup.get(line_no)
        optimized.append(optimize_line(line, win))

    old_total = money(sum(x["old_bid_total"] for x in optimized))
    new_total = money(sum(x["optimized_bid_total"] for x in optimized))

    old_profit = money(sum(x["old_gross_profit"] for x in optimized))
    new_profit = money(sum(x["optimized_gross_profit"] for x in optimized))

    total_delta = money(new_total - old_total)
    profit_delta = money(new_profit - old_profit)

    margin_counts = Counter(x["optimized_margin_pct"] for x in optimized)
    category_counts = Counter(x["category"] or "unknown" for x in optimized)
    band_counts = Counter(x["win_probability_band"] or "unknown" for x in optimized)

    reason_counts = Counter()
    for line in optimized:
        for reason in line.get("optimization_reasons", []):
            reason_counts[reason] += 1

    summary = {
        "generated_at": now_iso(),
        "lines_optimized": len(optimized),
        "old_bid_total": old_total,
        "optimized_bid_total": new_total,
        "bid_delta": total_delta,
        "old_gross_profit": old_profit,
        "optimized_gross_profit": new_profit,
        "profit_delta": profit_delta,
        "old_average_margin_pct": round((old_profit / old_total) * 100, 2) if old_total else 0,
        "optimized_average_margin_pct": round((new_profit / new_total) * 100, 2) if new_total else 0,
        "category_counts": dict(category_counts),
        "win_band_counts": dict(band_counts),
        "top_margin_values": dict(margin_counts.most_common(20)),
        "optimization_reason_counts": dict(reason_counts.most_common(30)),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "optimized_lines": optimized,
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Dynamic margin optimized bid written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Lines optimized: {summary['lines_optimized']}")
    print(f"Old bid total: R{summary['old_bid_total']:,.2f}")
    print(f"Optimized bid total: R{summary['optimized_bid_total']:,.2f}")
    print(f"Bid delta: R{summary['bid_delta']:,.2f}")
    print(f"Old gross profit: R{summary['old_gross_profit']:,.2f}")
    print(f"Optimized gross profit: R{summary['optimized_gross_profit']:,.2f}")
    print(f"Profit delta: R{summary['profit_delta']:,.2f}")
    print(f"Optimized average margin: {summary['optimized_average_margin_pct']}%")


if __name__ == "__main__":
    main()
