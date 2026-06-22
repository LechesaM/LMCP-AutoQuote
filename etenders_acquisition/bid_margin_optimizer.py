#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_quote_adjudication"
    / "award_recommendations.json"
)

OUT_DIR = RUNTIME_DIR / "bid_margin_strategy"

OUTPUT_FILE = OUT_DIR / "optimized_bid_strategy.json"
SUMMARY_FILE = OUT_DIR / "optimized_bid_summary.json"


TARGET_MARGIN_RULES = {
    "general_supply": 0.22,
    "mechanical": 0.28,
    "electrical": 0.25,
    "building_material": 0.18,
    "ppe": 0.35,
    "ict": 0.30,
    "furniture": 0.24,
    "cleaning": 0.20,
    "stationery": 0.18,
    "medical": 0.32,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path):
    if not path.exists():
        return {}

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


def infer_category(desc):
    d = (desc or "").lower()

    if any(x in d for x in ["bearing", "coupling", "pulley", "pump", "gasket"]):
        return "mechanical"

    if any(x in d for x in ["cable", "electrical", "transformer", "voltage"]):
        return "electrical"

    if any(x in d for x in ["brick", "cement", "concrete", "slab"]):
        return "building_material"

    if any(x in d for x in ["ppe", "helmet", "glove", "overall"]):
        return "ppe"

    if any(x in d for x in ["laptop", "scanner", "network", "server"]):
        return "ict"

    if any(x in d for x in ["desk", "chair", "cabinet"]):
        return "furniture"

    if any(x in d for x in ["soap", "clean", "detergent"]):
        return "cleaning"

    if any(x in d for x in ["pen", "paper", "file", "stapler"]):
        return "stationery"

    if any(x in d for x in ["medical", "clinic", "syringe"]):
        return "medical"

    return "general_supply"


def competitiveness_score(margin_pct):
    if margin_pct <= 12:
        return "VERY_COMPETITIVE"

    if margin_pct <= 18:
        return "COMPETITIVE"

    if margin_pct <= 25:
        return "MODERATE"

    if margin_pct <= 35:
        return "RISKY"

    return "HIGH_RISK"


def optimize_line(rec):
    base_cost = money(rec.get("recommended_total"))

    category = infer_category(rec.get("description"))

    margin = TARGET_MARGIN_RULES.get(category, 0.22)

    sell_price = money(base_cost * (1 + margin))

    gross_profit = money(sell_price - base_cost)

    return {
        "description": rec.get("description"),
        "recommended_supplier": rec.get("recommended_supplier"),
        "category": category,
        "base_cost": base_cost,
        "target_margin_pct": round(margin * 100, 2),
        "recommended_sell_price": sell_price,
        "gross_profit": gross_profit,
        "competitiveness": competitiveness_score(margin * 100),
        "risk_flags": rec.get("risk_flags", []),
        "quantity": rec.get("quantity"),
        "unit": rec.get("unit"),
    }


def main():
    data = load_json(INPUT_FILE)

    recommendations = data.get("recommendations", [])

    optimized = [
        optimize_line(r)
        for r in recommendations
        if r.get("recommended_total") is not None
    ]

    total_cost = money(sum(x["base_cost"] for x in optimized))
    total_sell = money(sum(x["recommended_sell_price"] for x in optimized))
    total_profit = money(sum(x["gross_profit"] for x in optimized))

    avg_margin = round(
        (total_profit / total_cost) * 100,
        2
    ) if total_cost else 0

    summary = {
        "generated_at": now_iso(),
        "optimized_lines": len(optimized),
        "total_cost_base": total_cost,
        "total_sell_value": total_sell,
        "total_projected_profit": total_profit,
        "average_margin_pct": avg_margin,
    }

    write_json(OUTPUT_FILE, {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "optimized_lines": optimized,
    })

    write_json(SUMMARY_FILE, summary)

    print(f"Optimized strategy written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Optimized lines: {summary['optimized_lines']}")
    print(f"Base cost: R{summary['total_cost_base']:,.2f}")
    print(f"Sell value: R{summary['total_sell_value']:,.2f}")
    print(f"Projected profit: R{summary['total_projected_profit']:,.2f}")
    print(f"Average margin: {summary['average_margin_pct']}%")


if __name__ == "__main__":
    main()
