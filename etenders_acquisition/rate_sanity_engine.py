#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "category_fallback_estimator"
    / "category_fallback_estimates.json"
)

OUT_DIR = RUNTIME_DIR / "rate_sanity"

OUTPUT_FILE = OUT_DIR / "rate_sanitized_estimates.json"
SUMMARY_FILE = OUT_DIR / "rate_sanity_summary.json"


BULK_MODIFIERS = [
    (1, 1.00),
    (10, 0.90),
    (100, 0.75),
    (1000, 0.55),
    (10000, 0.35),
]


KEYWORD_RATE_CAPS = [
    ("bitumen", 40),
    ("prime coat", 40),
    ("tack coat", 40),
    ("asphalt", 65),
    ("paper", 8),
    ("staples", 25),
    ("pen", 30),
    ("battery", 250),
    ("bearing", 10000),
    ("gasket", 2500),
    ("coupling", 15000),
    ("pulley", 25000),
    ("pump", 50000),
    ("cable", 250),
    ("pipe", 500),
    ("helmet", 800),
    ("glove", 150),
]


CATEGORY_RATE_CAPS = {
    "stationery": 500,
    "general_supply": 5000,
    "mechanical": 50000,
    "electrical": 30000,
    "building_material": 5000,
    "ppe": 3000,
    "ict": 80000,
    "furniture": 30000,
    "cleaning": 2000,
    "medical": 50000,
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


def normalized_text(value):
    value = str(value or "").lower()
    value = value.replace("/", " ")
    value = value.replace("-", " ")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def keyword_matches(description, keyword):
    desc = normalized_text(description)
    key = normalized_text(keyword)

    if not desc or not key:
        return False

    pattern = r"\b" + re.escape(key) + r"\b"

    return bool(re.search(pattern, desc))


def bulk_modifier(quantity):
    q = money(quantity)

    modifier = 1.0

    for threshold, value in BULK_MODIFIERS:
        if q >= threshold:
            modifier = value

    return modifier


def keyword_cap(description):
    for keyword, cap in KEYWORD_RATE_CAPS:
        if keyword_matches(description, keyword):
            return cap, f"keyword_cap:{keyword}"

    return None, None


def category_cap(category):
    return CATEGORY_RATE_CAPS.get(category or "general_supply", 5000)


def sanitize_item(item):
    quantity = money(item.get("quantity") or 1)
    original_unit_price = money(item.get("estimated_unit_price"))
    original_total = money(item.get("estimated_total"))

    description = item.get("description")
    category = item.get("category") or "general_supply"
    confidence = item.get("confidence")

    flags = list(item.get("risk_flags") or [])

    if quantity <= 0:
        quantity = 1
        flags.append("quantity_defaulted_to_1")

    if original_unit_price <= 0 and original_total > 0:
        original_unit_price = money(original_total / quantity)

    adjusted_unit_price = original_unit_price

    k_cap, k_reason = keyword_cap(description)
    c_cap = category_cap(category)

    cap_candidates = []

    if k_cap is not None:
        cap_candidates.append((k_cap, k_reason))

    if c_cap is not None:
        cap_candidates.append((c_cap, "category_cap"))

    if cap_candidates:
        applied_cap, applied_reason = min(cap_candidates, key=lambda x: x[0])

        if adjusted_unit_price > applied_cap:
            adjusted_unit_price = applied_cap
            flags.append(f"rate_capped:{applied_reason}")

    modifier = bulk_modifier(quantity)

    if quantity >= 100 and confidence in ["FALLBACK_LOW", "NO_MATCH"]:
        adjusted_unit_price = money(adjusted_unit_price * modifier)
        flags.append(f"bulk_modifier:{modifier}")

    if quantity > 10000 and adjusted_unit_price > 100:
        adjusted_unit_price = 100
        flags.append("large_quantity_rate_guard")

    adjusted_total = money(adjusted_unit_price * quantity)
    saving = money(original_total - adjusted_total)

    sanitized = dict(item)
    sanitized.update({
        "rate_sanity_status": "SANITIZED" if flags else "UNCHANGED",
        "original_unit_price": original_unit_price,
        "adjusted_unit_price": adjusted_unit_price,
        "original_total": original_total,
        "adjusted_total": adjusted_total,
        "rate_sanity_saving": saving,
        "rate_sanity_flags": sorted(set(flags)),
    })

    return sanitized


def main():
    data = load_json(INPUT_FILE, default={})
    items = data.get("estimates", [])

    sanitized = [sanitize_item(i) for i in items]

    changed = [
        i for i in sanitized
        if i.get("rate_sanity_status") == "SANITIZED"
    ]

    total_original = money(sum(money(i.get("original_total")) for i in sanitized))
    total_adjusted = money(sum(money(i.get("adjusted_total")) for i in sanitized))
    total_reduction = money(total_original - total_adjusted)

    status_counts = Counter(i.get("rate_sanity_status") for i in sanitized)
    confidence_counts = Counter(i.get("confidence") for i in sanitized)

    flag_counts = Counter()

    for item in sanitized:
        for flag in item.get("rate_sanity_flags", []):
            flag_counts[flag] += 1

    summary = {
        "generated_at": now_iso(),
        "input_items": len(items),
        "sanitized_items": len(changed),
        "unchanged_items": len(items) - len(changed),
        "original_total_value": total_original,
        "adjusted_total_value": total_adjusted,
        "total_reduction": total_reduction,
        "status_counts": dict(status_counts),
        "confidence_counts": dict(confidence_counts),
        "top_flags": dict(flag_counts.most_common(30)),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "items": sanitized,
        "sanitized_items": changed,
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Rate sanitized estimates written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Input items: {summary['input_items']}")
    print(f"Sanitized items: {summary['sanitized_items']}")
    print(f"Original total: R{summary['original_total_value']:,.2f}")
    print(f"Adjusted total: R{summary['adjusted_total_value']:,.2f}")
    print(f"Reduction: R{summary['total_reduction']:,.2f}")


if __name__ == "__main__":
    main()
