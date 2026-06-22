#!/usr/bin/env python3
import json
import statistics
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

BOOSTED_FILE = (
    RUNTIME_DIR
    / "sku_pricing_booster"
    / "boosted_pricing_estimates.json"
)

MEMORY_FILE = (
    RUNTIME_DIR
    / "supplier_price_memory"
    / "supplier_price_memory.json"
)

DEDUPED_FILE = (
    RUNTIME_DIR
    / "boq_intelligence"
    / "deduplicated_boq_items.json"
)

OUT_DIR = RUNTIME_DIR / "category_fallback_estimator"

OUTPUT_FILE = OUT_DIR / "category_fallback_estimates.json"
SUMMARY_FILE = OUT_DIR / "category_fallback_summary.json"


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


def unit_price_from_record(row):
    unit_price = row.get("unit_price")
    total_price = row.get("total_price")
    qty = row.get("quantity") or 1

    if unit_price is not None:
        return money(unit_price)

    try:
        qty = float(qty or 1)
    except Exception:
        qty = 1

    if total_price is not None and qty > 0:
        return money(float(total_price) / qty)

    return None


def infer_category(description):
    d = str(description or "").lower()

    if any(x in d for x in ["bearing", "coupling", "pulley", "pump", "gasket", "shaft", "sleeve", "bush"]):
        return "mechanical"

    if any(x in d for x in ["cable", "electrical", "transformer", "voltage", "battery", "charger", "light"]):
        return "electrical"

    if any(x in d for x in ["brick", "cement", "concrete", "slab", "pipe", "paint", "timber"]):
        return "building_material"

    if any(x in d for x in ["ppe", "helmet", "glove", "overall", "boot", "protective"]):
        return "ppe"

    if any(x in d for x in ["laptop", "scanner", "network", "server", "printer", "computer"]):
        return "ict"

    if any(x in d for x in ["desk", "chair", "cabinet", "table"]):
        return "furniture"

    if any(x in d for x in ["soap", "clean", "detergent", "disinfectant"]):
        return "cleaning"

    if any(x in d for x in ["pen", "paper", "file", "stapler", "stationery"]):
        return "stationery"

    return "general_supply"


def build_description_category_map(deduped):
    lookup = {}

    for item in deduped.get("usable_pricing_items", []):
        desc = item.get("description")
        if desc:
            lookup[desc] = item.get("category") or infer_category(desc)

    return lookup


def build_price_stats(memory, desc_category_lookup):
    by_category_unit = defaultdict(list)
    by_category = defaultdict(list)
    global_prices = []

    for _, rows in memory.get("price_memory", {}).items():
        for row in rows:
            price = unit_price_from_record(row)
            if price is None or price <= 0:
                continue

            desc = row.get("description")
            category = desc_category_lookup.get(desc) or infer_category(desc)
            unit = row.get("unit") or "missing"

            by_category_unit[(category, unit)].append(price)
            by_category[category].append(price)
            global_prices.append(price)

    def summarize(values):
        if not values:
            return None
        values = sorted(values)
        return {
            "count": len(values),
            "min": money(min(values)),
            "median": money(statistics.median(values)),
            "mean": money(statistics.mean(values)),
            "max": money(max(values)),
        }

    return {
        "by_category_unit": {
            f"{k[0]}||{k[1]}": summarize(v)
            for k, v in by_category_unit.items()
        },
        "by_category": {
            k: summarize(v)
            for k, v in by_category.items()
        },
        "global": summarize(global_prices),
    }


def fallback_price(item, stats):
    category = item.get("category") or infer_category(item.get("description"))
    unit = item.get("unit") or "missing"

    key = f"{category}||{unit}"

    if key in stats["by_category_unit"] and stats["by_category_unit"][key]:
        s = stats["by_category_unit"][key]
        return s["median"], "category_unit_median", s

    if category in stats["by_category"] and stats["by_category"][category]:
        s = stats["by_category"][category]
        return s["median"], "category_median", s

    if stats["global"]:
        s = stats["global"]
        return s["median"], "global_median", s

    return None, "no_fallback_available", None


def main():
    boosted_data = load_json(BOOSTED_FILE, default={})
    memory = load_json(MEMORY_FILE, default={})
    deduped = load_json(DEDUPED_FILE, default={})

    desc_category_lookup = build_description_category_map(deduped)
    stats = build_price_stats(memory, desc_category_lookup)

    estimates = boosted_data.get("estimates", [])

    final_items = []
    fallback_count = 0

    for item in estimates:
        if item.get("estimate_status") in ["ESTIMATED", "SKU_ESTIMATED"]:
            final_items.append(item)
            continue

        unit_price, method, stat = fallback_price(item, stats)

        if unit_price is None:
            final_items.append(item)
            continue

        qty = item.get("quantity") or 1
        try:
            qty = float(qty or 1)
        except Exception:
            qty = 1

        updated = dict(item)
        updated.update({
            "estimate_status": "CATEGORY_FALLBACK_ESTIMATED",
            "estimated_unit_price": unit_price,
            "estimated_total": money(unit_price * qty),
            "confidence": "FALLBACK_LOW",
            "match_score": 0.35,
            "matched_supplier": None,
            "matched_description": None,
            "fallback_method": method,
            "fallback_stats": stat,
            "pricing_source": "category_price_memory",
        })

        final_items.append(updated)
        fallback_count += 1

    estimated_items = [
        i for i in final_items
        if i.get("estimate_status") in [
            "ESTIMATED",
            "SKU_ESTIMATED",
            "CATEGORY_FALLBACK_ESTIMATED",
        ]
    ]

    no_match = [
        i for i in final_items
        if i.get("estimate_status") == "NO_MATCH"
    ]

    total_value = money(sum(money(i.get("estimated_total")) for i in estimated_items))

    status_counts = Counter(i.get("estimate_status") for i in final_items)
    confidence_counts = Counter(i.get("confidence") for i in final_items)
    category_counts = Counter(i.get("category") or infer_category(i.get("description")) for i in final_items)

    summary = {
        "generated_at": now_iso(),
        "input_items": len(estimates),
        "fallback_estimated_items": fallback_count,
        "estimated_items_total": len(estimated_items),
        "remaining_no_match": len(no_match),
        "coverage_pct": round((len(estimated_items) / len(final_items)) * 100, 2) if final_items else 0,
        "total_estimated_value": total_value,
        "status_counts": dict(status_counts),
        "confidence_counts": dict(confidence_counts),
        "category_counts": dict(category_counts),
        "price_stats_category_count": len(stats["by_category"]),
        "price_stats_category_unit_count": len(stats["by_category_unit"]),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "price_stats": stats,
        "estimates": final_items,
        "fallback_estimated": [
            i for i in final_items
            if i.get("estimate_status") == "CATEGORY_FALLBACK_ESTIMATED"
        ],
        "remaining_no_match_sample": no_match[:500],
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Category fallback estimates written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Fallback estimated items: {summary['fallback_estimated_items']}")
    print(f"Estimated items total: {summary['estimated_items_total']}")
    print(f"Remaining no match: {summary['remaining_no_match']}")
    print(f"Coverage: {summary['coverage_pct']}%")
    print(f"Total estimated value: R{summary['total_estimated_value']:,.2f}")


if __name__ == "__main__":
    main()
