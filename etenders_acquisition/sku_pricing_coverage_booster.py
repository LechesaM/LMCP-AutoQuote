#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

ESTIMATES_FILE = (
    RUNTIME_DIR
    / "historical_price_estimator"
    / "estimated_pricing.json"
)

PART_INDEX_FILE = (
    RUNTIME_DIR
    / "supplier_expansion"
    / "filtered_manufacturer_part_index_v2.json"
)

OUT_DIR = RUNTIME_DIR / "sku_pricing_booster"

OUTPUT_FILE = OUT_DIR / "boosted_pricing_estimates.json"
SUMMARY_FILE = OUT_DIR / "sku_pricing_booster_summary.json"


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


def clean_text(value):
    value = str(value or "").upper()
    value = re.sub(r"[^A-Z0-9\-\/]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def build_sku_index(part_data):
    index = {}

    true_parts = part_data.get("true_part_numbers", {})

    for sku, records in true_parts.items():
        valid_prices = []

        for r in records:
            unit_price = r.get("unit_price")

            if unit_price is not None:
                valid_prices.append({
                    "supplier": r.get("supplier"),
                    "unit_price": money(unit_price),
                    "description": r.get("description"),
                    "unit": r.get("unit"),
                })

        if valid_prices:
            valid_prices = sorted(valid_prices, key=lambda x: x["unit_price"])
            index[sku.upper()] = valid_prices[0]

    return index


def find_sku_matches(description, sku_index):
    text = clean_text(description)

    matches = []

    for sku in sku_index.keys():
        if len(sku) < 4:
            continue

        pattern = r"(^|[^A-Z0-9])" + re.escape(sku) + r"([^A-Z0-9]|$)"

        if re.search(pattern, text):
            matches.append(sku)

    return sorted(matches, key=len, reverse=True)


def boost_estimate(item, sku_index):
    if item.get("estimate_status") == "ESTIMATED":
        return item, False

    desc = item.get("description")
    qty = item.get("quantity") or 1

    try:
        qty = float(qty or 1)
    except Exception:
        qty = 1

    sku_matches = find_sku_matches(desc, sku_index)

    if not sku_matches:
        return item, False

    sku = sku_matches[0]
    record = sku_index[sku]

    unit_price = money(record.get("unit_price"))
    total = money(unit_price * qty)

    boosted = dict(item)
    boosted.update({
        "estimate_status": "SKU_ESTIMATED",
        "estimated_unit_price": unit_price,
        "estimated_total": total,
        "confidence": "SKU_HIGH",
        "match_score": 0.90,
        "matched_supplier": record.get("supplier"),
        "matched_description": record.get("description"),
        "matched_unit": record.get("unit"),
        "matched_sku": sku,
        "sku_match_candidates": sku_matches[:10],
        "pricing_source": "supplier_part_index",
    })

    return boosted, True


def main():
    estimates_data = load_json(ESTIMATES_FILE, default={})
    part_data = load_json(PART_INDEX_FILE, default={})

    estimates = estimates_data.get("estimates", [])

    sku_index = build_sku_index(part_data)

    boosted_items = []
    boost_count = 0

    for item in estimates:
        boosted, did_boost = boost_estimate(item, sku_index)
        boosted_items.append(boosted)

        if did_boost:
            boost_count += 1

    estimated_items = [
        i for i in boosted_items
        if i.get("estimate_status") in ["ESTIMATED", "SKU_ESTIMATED"]
    ]

    no_match_items = [
        i for i in boosted_items
        if i.get("estimate_status") == "NO_MATCH"
    ]

    total_estimated_value = money(
        sum(money(i.get("estimated_total")) for i in estimated_items)
    )

    confidence_counts = Counter(i.get("confidence") for i in boosted_items)
    status_counts = Counter(i.get("estimate_status") for i in boosted_items)

    summary = {
        "generated_at": now_iso(),
        "input_items": len(estimates),
        "sku_index_size": len(sku_index),
        "sku_boosted_items": boost_count,
        "estimated_items_total": len(estimated_items),
        "remaining_no_match": len(no_match_items),
        "coverage_pct": round(
            (len(estimated_items) / len(estimates)) * 100,
            2
        ) if estimates else 0,
        "total_estimated_value": total_estimated_value,
        "status_counts": dict(status_counts),
        "confidence_counts": dict(confidence_counts),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "estimates": boosted_items,
        "sku_boosted": [
            i for i in boosted_items
            if i.get("estimate_status") == "SKU_ESTIMATED"
        ],
        "remaining_no_match_sample": no_match_items[:500],
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Boosted pricing estimates written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"SKU index size: {summary['sku_index_size']}")
    print(f"SKU boosted items: {summary['sku_boosted_items']}")
    print(f"Estimated items total: {summary['estimated_items_total']}")
    print(f"Remaining no match: {summary['remaining_no_match']}")
    print(f"Coverage: {summary['coverage_pct']}%")
    print(f"Total estimated value: R{summary['total_estimated_value']:,.2f}")


if __name__ == "__main__":
    main()
