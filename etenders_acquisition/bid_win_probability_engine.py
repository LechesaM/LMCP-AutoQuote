#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "commercial_intelligence"
    / "competitor_price_simulation.json"
)

OUT_DIR = RUNTIME_DIR / "commercial_intelligence"

OUTPUT_FILE = OUT_DIR / "bid_win_probability_analysis.json"
SUMMARY_FILE = OUT_DIR / "bid_win_probability_summary.json"


CATEGORY_WEIGHT = {
    "mechanical": 1.15,
    "electrical": 1.10,
    "ict": 1.20,
    "medical": 1.25,
    "building_material": 1.00,
    "stationery": 0.90,
    "general_supply": 0.95,
    "ppe": 0.95,
    "furniture": 1.00,
    "cleaning": 0.90,
}


POSITION_SCORE = {
    "VERY_COMPETITIVE": 92,
    "COMPETITIVE": 78,
    "MARKET_ALIGNED": 61,
    "EXPENSIVE": 35,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def clamp(v, low, high):
    return max(low, min(high, v))


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


def win_band(score):
    if score >= 85:
        return "VERY_HIGH"
    if score >= 70:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    if score >= 40:
        return "LOW"

    return "VERY_LOW"


def analyze_line(line):
    category = line.get("category") or "general_supply"

    market_position = line.get("market_position")
    our_bid = money(line.get("our_bid_total"))
    cost_total = money(line.get("cost_total"))

    scenarios = line.get("competitor_scenarios") or {}

    market_low = money(scenarios.get("market_low"))
    market_mid = money(scenarios.get("market_mid"))
    aggressive = money(scenarios.get("aggressive"))

    base_score = POSITION_SCORE.get(market_position, 50)

    category_modifier = CATEGORY_WEIGHT.get(category, 1.0)

    score = base_score * category_modifier

    margin = 0

    if our_bid > 0:
        margin = ((our_bid - cost_total) / our_bid) * 100

    risk_flags = []

    if margin > 45:
        score -= 12
        risk_flags.append("high_margin_risk")

    if our_bid > market_mid:
        score -= 8
        risk_flags.append("above_market_mid")

    if our_bid <= aggressive:
        score += 10
        risk_flags.append("beats_aggressive_market")

    if margin < 8:
        score -= 10
        risk_flags.append("thin_margin")

    if our_bid < cost_total:
        score -= 40
        risk_flags.append("below_cost")

    score = clamp(round(score, 2), 1, 99)

    expected_award_probability = score / 100

    expected_profit = money(
        (our_bid - cost_total) * expected_award_probability
    )

    return {
        "line_no": line.get("line_no"),
        "description": line.get("description"),
        "category": category,
        "market_position": market_position,
        "our_bid_total": our_bid,
        "cost_total": cost_total,
        "market_low": market_low,
        "market_mid": market_mid,
        "aggressive_market": aggressive,
        "estimated_margin_pct": round(margin, 2),
        "win_probability_score": score,
        "win_probability_band": win_band(score),
        "expected_award_probability": round(expected_award_probability, 4),
        "expected_profit_value": expected_profit,
        "risk_flags": risk_flags,
    }


def main():
    data = load_json(INPUT_FILE, default={})

    lines = data.get("simulated_lines", [])

    analyzed = [analyze_line(line) for line in lines]

    avg_score = round(
        sum(x["win_probability_score"] for x in analyzed) / max(len(analyzed), 1),
        2
    )

    total_bid = money(sum(x["our_bid_total"] for x in analyzed))
    total_expected_profit = money(
        sum(x["expected_profit_value"] for x in analyzed)
    )

    band_counts = Counter(x["win_probability_band"] for x in analyzed)
    category_counts = Counter(x["category"] for x in analyzed)

    risk_counter = Counter()

    for line in analyzed:
        for flag in line["risk_flags"]:
            risk_counter[flag] += 1

    summary = {
        "generated_at": now_iso(),
        "lines_analyzed": len(analyzed),
        "average_win_probability_score": avg_score,
        "portfolio_win_band": win_band(avg_score),
        "portfolio_bid_value": total_bid,
        "portfolio_expected_profit": total_expected_profit,
        "band_counts": dict(band_counts),
        "category_counts": dict(category_counts),
        "risk_counts": dict(risk_counter),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "line_analysis": analyzed,
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Bid win analysis written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Lines analyzed: {summary['lines_analyzed']}")
    print(f"Average score: {summary['average_win_probability_score']}")
    print(f"Portfolio win band: {summary['portfolio_win_band']}")
    print(f"Expected portfolio profit: R{summary['portfolio_expected_profit']:,.2f}")

    print("\nBand counts:")
    for k, v in band_counts.items():
        print(f"- {k}: {v}")

    print("\nRisk counts:")
    for k, v in risk_counter.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
