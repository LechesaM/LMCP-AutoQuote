#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "procurement_category_ai"
    / "recategorized_pricing_schedule.json"
)

OUT_DIR = RUNTIME_DIR / "commercial_intelligence"

OUTPUT_FILE = OUT_DIR / "competitor_price_simulation.json"
SUMMARY_FILE = OUT_DIR / "competitor_price_simulation_summary.json"


COMPETITOR_BANDS = {
    "aggressive": -0.12,
    "market_low": -0.06,
    "market_mid": 0.00,
    "market_high": 0.08,
    "premium": 0.15,
}


CATEGORY_PRESSURE = {
    "stationery": -0.04,
    "ppe": -0.03,
    "building_material": -0.03,
    "general_supply": -0.02,
    "electrical": 0.00,
    "mechanical": 0.04,
    "ict": 0.05,
    "furniture": 0.02,
    "cleaning": -0.02,
    "medical": 0.06,
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


def simulate_line(line):
    bid_total = money(line.get("bid_total"))
    cost_total = money(line.get("cost_total"))
    category = line.get("category") or "general_supply"

    pressure = CATEGORY_PRESSURE.get(category, 0)

    scenarios = {}

    for band, factor in COMPETITOR_BANDS.items():
        simulated = money(bid_total * (1 + factor + pressure))
        scenarios[band] = simulated

    market_low = scenarios["market_low"]
    market_mid = scenarios["market_mid"]

    if bid_total <= market_low:
        position = "VERY_COMPETITIVE"
    elif bid_total <= market_mid:
        position = "COMPETITIVE"
    elif bid_total <= scenarios["market_high"]:
        position = "MARKET_ALIGNED"
    else:
        position = "EXPENSIVE"

    profit_at_aggressive = money(scenarios["aggressive"] - cost_total)

    risk_flags = []

    if profit_at_aggressive < 0:
        risk_flags.append("aggressive_competitor_below_cost")

    if position == "EXPENSIVE":
        risk_flags.append("price_above_market_high")

    return {
        "line_no": line.get("line_no"),
        "description": line.get("description"),
        "category": category,
        "cost_total": cost_total,
        "our_bid_total": bid_total,
        "our_margin_pct": line.get("margin_pct"),
        "competitor_scenarios": scenarios,
        "market_position": position,
        "profit_at_aggressive_market": profit_at_aggressive,
        "risk_flags": risk_flags,
    }


def main():
    data = load_json(INPUT_FILE, default={})
    lines = data.get("pricing_schedule", [])

    simulated = [simulate_line(line) for line in lines]

    total_cost = money(sum(x["cost_total"] for x in simulated))
    total_bid = money(sum(x["our_bid_total"] for x in simulated))

    scenario_totals = {}

    for band in COMPETITOR_BANDS:
        scenario_totals[band] = money(
            sum(x["competitor_scenarios"][band] for x in simulated)
        )

    market_position_counts = Counter(x["market_position"] for x in simulated)
    category_counts = Counter(x["category"] for x in simulated)

    risk_counter = Counter()

    for line in simulated:
        for flag in line["risk_flags"]:
            risk_counter[flag] += 1

    summary = {
        "generated_at": now_iso(),
        "lines_simulated": len(simulated),
        "total_cost": total_cost,
        "our_total_bid": total_bid,
        "scenario_totals": scenario_totals,
        "market_position_counts": dict(market_position_counts),
        "category_counts": dict(category_counts),
        "risk_counts": dict(risk_counter),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "simulated_lines": simulated,
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Competitor simulation written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Lines simulated: {summary['lines_simulated']}")
    print(f"Our bid: R{summary['our_total_bid']:,.2f}")

    print("\nScenario totals:")
    for k, v in scenario_totals.items():
        print(f"- {k}: R{v:,.2f}")

    print("\nMarket position:")
    for k, v in market_position_counts.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
