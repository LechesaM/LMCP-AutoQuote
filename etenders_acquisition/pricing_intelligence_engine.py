#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "boq_intelligence" / "deduplicated_boq_items.json"

OUT_DIR = RUNTIME_DIR / "pricing_engine"

OUTPUT_FILE = OUT_DIR / "pricing_candidates.json"
SUMMARY_FILE = OUT_DIR / "pricing_candidates_summary.json"


BRAND_PATTERNS = [
    "SKF",
    "FAG",
    "NSK",
    "TIMKEN",
    "SIEMENS",
    "ABB",
    "SCHNEIDER",
    "HELLERMANNTYTON",
    "3M",
]

UNIT_PRICE_HINTS = {
    "bearing": 450,
    "pump": 8500,
    "gasket": 120,
    "valve": 2500,
    "cable": 45,
    "pipe": 180,
    "helmet": 350,
    "glove": 40,
    "chair": 950,
    "desk": 2800,
    "toner": 1200,
    "printer": 6500,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean(v):
    if v is None:
        return ""

    v = str(v)
    v = v.replace("\n", " ").replace("\r", " ")
    v = re.sub(r"\s+", " ", v)

    return v.strip()


def extract_brand(text):
    upper = text.upper()

    for b in BRAND_PATTERNS:
        if b in upper:
            return b

    return None


def extract_dimensions(text):
    patterns = [
        r'(\d+(\.\d+)?)\s*MM',
        r'(\d+(\.\d+)?)\s*IN',
        r'(\d+(\.\d+)?)\s*KG',
        r'(\d+(\.\d+)?)\s*L',
    ]

    found = []

    upper = text.upper()

    for p in patterns:
        matches = re.findall(p, upper)

        for m in matches:
            found.append(m[0])

    return sorted(set(found))


def classify_product(description):
    d = description.lower()

    if "bearing" in d:
        return "bearing"

    if "pump" in d:
        return "pump"

    if "gasket" in d:
        return "gasket"

    if "valve" in d:
        return "valve"

    if "cable" in d:
        return "cable"

    if "pipe" in d:
        return "pipe"

    if "helmet" in d:
        return "helmet"

    if "glove" in d:
        return "glove"

    if "chair" in d:
        return "chair"

    if "desk" in d:
        return "desk"

    if "printer" in d:
        return "printer"

    if "toner" in d:
        return "toner"

    return "general"


def estimate_unit_price(product_type):
    return UNIT_PRICE_HINTS.get(product_type, 100)


def build_fingerprint(item):
    description = clean(item.get("description")).lower()

    description = re.sub(r'[^a-z0-9]+', ' ', description)
    description = re.sub(r'\s+', ' ', description)

    return description[:220]


def pricing_confidence(item, brand, dimensions):
    score = 0

    if item.get("confidence") == "HIGH":
        score += 40

    if item.get("quantity"):
        score += 20

    if item.get("unit"):
        score += 10

    if len(clean(item.get("description"))) > 30:
        score += 15

    if brand:
        score += 10

    if dimensions:
        score += 5

    if score >= 75:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    return "LOW"


def main():
    data = load_json(INPUT_FILE, default={})

    items = data.get("usable_pricing_items", [])

    pricing_items = []

    for item in items:
        description = clean(item.get("description"))

        product_type = classify_product(description)

        brand = extract_brand(description)

        dimensions = extract_dimensions(description)

        unit_price_estimate = estimate_unit_price(product_type)

        quantity = item.get("aggregate_quantity") or item.get("quantity") or 1

        try:
            quantity = float(quantity)
        except Exception:
            quantity = 1

        estimated_total = round(quantity * unit_price_estimate, 2)

        pricing_items.append({
            "description": description,
            "category": item.get("category"),
            "product_type": product_type,
            "brand": brand,
            "dimensions": dimensions,
            "quantity": quantity,
            "unit": item.get("unit"),
            "unit_price_estimate": unit_price_estimate,
            "estimated_total": estimated_total,
            "pricing_confidence": pricing_confidence(item, brand, dimensions),
            "fingerprint": build_fingerprint(item),
            "source_quality": item.get("confidence"),
            "dedupe_group_id": item.get("dedupe_group_id"),
        })

    product_type_counts = Counter(i["product_type"] for i in pricing_items)
    pricing_confidence_counts = Counter(i["pricing_confidence"] for i in pricing_items)
    category_counts = Counter(i["category"] for i in pricing_items)

    summary = {
        "generated_at": now_iso(),
        "pricing_candidates": len(pricing_items),
        "product_type_counts": dict(product_type_counts),
        "pricing_confidence_counts": dict(pricing_confidence_counts),
        "category_counts": dict(category_counts),
    }

    output = {
        "generated_at": now_iso(),
        "pricing_items": pricing_items,
        "summary": summary,
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Pricing candidates written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Pricing candidates: {len(pricing_items)}")

    print("\nPricing confidence:")
    for k, v in pricing_confidence_counts.items():
        print(f"- {k}: {v}")

    print("\nProduct types:")
    for k, v in product_type_counts.most_common(20):
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
