#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from statistics import mean

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

PRICE_MEMORY_FILE = (
    RUNTIME_DIR
    / "supplier_price_memory"
    / "supplier_price_memory.json"
)

SUPPLIER_EXPANSION_FILE = (
    RUNTIME_DIR
    / "supplier_expansion"
    / "supplier_catalog_index.json"
)

ADJUDICATION_FILE = (
    RUNTIME_DIR
    / "ai_tender_adjudication"
    / "ai_tender_adjudication_review.json"
)

DEFENSE_FILE = (
    RUNTIME_DIR
    / "bid_defense"
    / "intelligent_bid_defense_report.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_market_intelligence"

SUPPLIER_SCORECARD_FILE = OUT_DIR / "supplier_scorecards.json"
MARKET_VOLATILITY_FILE = OUT_DIR / "market_volatility_analysis.json"
SUPPLIER_RISK_FILE = OUT_DIR / "supplier_risk_analysis.json"
OEM_ANALYSIS_FILE = OUT_DIR / "oem_market_analysis.json"
SUMMARY_FILE = OUT_DIR / "supplier_market_intelligence_summary.json"


VOLATILE_COMMODITIES = {
    "bitumen": 0.95,
    "fuel": 0.90,
    "diesel": 0.88,
    "steel": 0.82,
    "copper": 0.85,
    "ppe": 0.75,
    "shoe": 0.72,
    "glove": 0.70,
    "paper": 0.60,
    "electrical": 0.65,
    "bearing": 0.55,
    "rubber": 0.78,
}

OEM_KEYWORDS = [
    "SKF",
    "ABB",
    "FAG",
    "NSK",
    "LINATEX",
    "SIEMENS",
    "BOSCH",
    "SCHNEIDER",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def pct(v):
    return round(v * 100, 2)


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


def contains_keywords(text, keywords):
    t = str(text or "").lower()
    return [k for k in keywords if k.lower() in t]


def supplier_reliability_score(stats):
    score = 100

    if stats["fallback_items"] > 50:
        score -= 25

    if stats["high_risk_items"] > 20:
        score -= 20

    if stats["critical_risk_items"] > 0:
        score -= 25

    if stats["catalog_items"] < 20:
        score -= 10

    if stats["oem_items"] > 10:
        score += 10

    score = max(0, min(100, score))
    return score


def reliability_band(score):
    if score >= 85:
        return "EXCELLENT"
    if score >= 70:
        return "GOOD"
    if score >= 55:
        return "MODERATE"
    if score >= 40:
        return "RISKY"
    return "HIGH_RISK"


def main():
    price_memory = load_json(PRICE_MEMORY_FILE, default={})
    supplier_catalog = load_json(SUPPLIER_EXPANSION_FILE, default={})
    adjudication = load_json(ADJUDICATION_FILE, default={})
    defense = load_json(DEFENSE_FILE, default={})

    price_data = price_memory.get("price_memory", {})
    catalog_index = supplier_catalog.get("supplier_catalog", {})
    reviewed_lines = adjudication.get("reviewed_lines", [])
    defense_lines = defense.get("defense_lines", [])

    supplier_stats = defaultdict(lambda: {
        "catalog_items": 0,
        "quoted_items": 0,
        "fallback_items": 0,
        "high_risk_items": 0,
        "critical_risk_items": 0,
        "oem_items": 0,
        "avg_price": [],
        "categories": Counter(),
        "commodity_exposure": Counter(),
    })

    volatility_analysis = []
    oem_analysis = defaultdict(list)

    # Supplier catalog analysis
    for supplier, items in catalog_index.items():

        for item in items:
            supplier_stats[supplier]["catalog_items"] += 1

            unit_price = money(item.get("unit_price"))
            if unit_price:
                supplier_stats[supplier]["avg_price"].append(unit_price)

            category = item.get("category", "unknown")
            supplier_stats[supplier]["categories"][category] += 1

            desc = item.get("description", "")

            for commodity in VOLATILE_COMMODITIES:
                if commodity in desc.lower():
                    supplier_stats[supplier]["commodity_exposure"][commodity] += 1

            oems = contains_keywords(desc, OEM_KEYWORDS)

            if oems:
                supplier_stats[supplier]["oem_items"] += 1

                for oem in oems:
                    oem_analysis[oem].append({
                        "supplier": supplier,
                        "description": desc,
                        "unit_price": unit_price,
                    })

    # Adjudication analysis
    for line in reviewed_lines:
        desc = line.get("description", "")
        confidence = line.get("confidence")
        risk_level = line.get("risk_level")

        matched_supplier = None

        for supplier in supplier_stats.keys():
            if supplier.lower() in desc.lower():
                matched_supplier = supplier
                break

        if matched_supplier:
            supplier_stats[matched_supplier]["quoted_items"] += 1

            if confidence in ["LOW", "FALLBACK_LOW"]:
                supplier_stats[matched_supplier]["fallback_items"] += 1

            if risk_level == "HIGH":
                supplier_stats[matched_supplier]["high_risk_items"] += 1

            elif risk_level == "CRITICAL":
                supplier_stats[matched_supplier]["critical_risk_items"] += 1

    # Volatility analysis
    for line in defense_lines:
        desc = line.get("description", "")
        total = money(line.get("submission_total"))

        matched = contains_keywords(desc, VOLATILE_COMMODITIES.keys())

        if matched:
            for commodity in matched:
                volatility_analysis.append({
                    "commodity": commodity,
                    "volatility_score": VOLATILE_COMMODITIES[commodity],
                    "description": desc,
                    "submission_total": total,
                    "risk_level": line.get("risk_level"),
                })

    supplier_scorecards = []

    for supplier, stats in supplier_stats.items():

        reliability_score = supplier_reliability_score(stats)

        avg_price = round(mean(stats["avg_price"]), 2) \
            if stats["avg_price"] else 0

        supplier_scorecards.append({
            "supplier": supplier,
            "reliability_score": reliability_score,
            "reliability_band": reliability_band(reliability_score),
            "catalog_items": stats["catalog_items"],
            "quoted_items": stats["quoted_items"],
            "fallback_items": stats["fallback_items"],
            "high_risk_items": stats["high_risk_items"],
            "critical_risk_items": stats["critical_risk_items"],
            "oem_items": stats["oem_items"],
            "average_unit_price": avg_price,
            "category_distribution": dict(stats["categories"]),
            "commodity_exposure": dict(stats["commodity_exposure"]),
        })

    supplier_scorecards = sorted(
        supplier_scorecards,
        key=lambda x: x["reliability_score"],
        reverse=True
    )

    volatility_counter = Counter(
        x["commodity"] for x in volatility_analysis
    )

    avg_volatility = round(
        mean([x["volatility_score"] for x in volatility_analysis]),
        2
    ) if volatility_analysis else 0

    summary = {
        "generated_at": now_iso(),
        "suppliers_analyzed": len(supplier_scorecards),
        "volatility_lines": len(volatility_analysis),
        "average_market_volatility": avg_volatility,
        "high_volatility_exposure": sum(
            1 for x in volatility_analysis
            if x["volatility_score"] >= 0.80
        ),
        "top_commodity_exposure": dict(volatility_counter.most_common(20)),
        "supplier_bands": dict(
            Counter(x["reliability_band"] for x in supplier_scorecards)
        ),
        "top_suppliers": [
            {
                "supplier": x["supplier"],
                "score": x["reliability_score"],
                "band": x["reliability_band"],
            }
            for x in supplier_scorecards[:10]
        ],
        "oems_detected": len(oem_analysis),
    }

    write_json(SUPPLIER_SCORECARD_FILE, {
        "generated_at": now_iso(),
        "supplier_scorecards": supplier_scorecards,
    })

    write_json(MARKET_VOLATILITY_FILE, {
        "generated_at": now_iso(),
        "volatility_analysis": volatility_analysis,
    })

    write_json(SUPPLIER_RISK_FILE, {
        "generated_at": now_iso(),
        "supplier_risk_analysis": supplier_scorecards,
    })

    write_json(OEM_ANALYSIS_FILE, {
        "generated_at": now_iso(),
        "oem_market_analysis": oem_analysis,
    })

    write_json(SUMMARY_FILE, summary)

    print(f"Supplier scorecards written: {SUPPLIER_SCORECARD_FILE}")
    print(f"Volatility analysis written: {MARKET_VOLATILITY_FILE}")
    print(f"Supplier risk written: {SUPPLIER_RISK_FILE}")
    print(f"OEM analysis written: {OEM_ANALYSIS_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Suppliers analyzed: {summary['suppliers_analyzed']}")
    print(f"Volatility lines: {summary['volatility_lines']}")
    print(f"Average market volatility: {summary['average_market_volatility']}")

    print("\nSupplier bands:")
    for k, v in summary["supplier_bands"].items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
