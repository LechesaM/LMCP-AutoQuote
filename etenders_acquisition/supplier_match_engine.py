#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "pricing_engine" / "pricing_candidates.json"

OUT_DIR = RUNTIME_DIR / "supplier_matching"

OUTPUT_FILE = OUT_DIR / "supplier_matches.json"
SUMMARY_FILE = OUT_DIR / "supplier_match_summary.json"


SUPPLIERS = [
    {
        "supplier": "Bearing Man Group",
        "specialties": ["bearing", "mechanical"],
        "brands": ["SKF", "FAG", "NSK", "TIMKEN"],
        "regions": ["South Africa"]
    },
    {
        "supplier": "BMG",
        "specialties": ["bearing", "pump", "valve", "mechanical"],
        "brands": ["SKF", "FAG"],
        "regions": ["South Africa"]
    },
    {
        "supplier": "RS Components",
        "specialties": ["electrical", "cable", "ict"],
        "brands": ["ABB", "SIEMENS", "SCHNEIDER"],
        "regions": ["Global"]
    },
    {
        "supplier": "Voltex",
        "specialties": ["electrical", "cable"],
        "brands": ["ABB", "SCHNEIDER"],
        "regions": ["South Africa"]
    },
    {
        "supplier": "Builders Warehouse",
        "specialties": ["building_material", "pipe"],
        "brands": [],
        "regions": ["South Africa"]
    },
]


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

    return re.sub(r"\s+", " ", str(v)).strip()


def score_supplier(item, supplier):
    score = 0

    product_type = item.get("product_type")
    category = item.get("category")
    brand = item.get("brand")

    if product_type in supplier["specialties"]:
        score += 50

    if category in supplier["specialties"]:
        score += 25

    if brand and brand in supplier["brands"]:
        score += 25

    return score


def confidence(score):
    if score >= 75:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    return "LOW"


def main():
    data = load_json(INPUT_FILE, default={})

    pricing_items = data.get("pricing_items", [])

    matches = []

    supplier_counter = Counter()
    confidence_counter = Counter()

    for item in pricing_items:
        scored = []

        for supplier in SUPPLIERS:
            s = score_supplier(item, supplier)

            if s > 0:
                scored.append({
                    "supplier": supplier["supplier"],
                    "score": s,
                    "confidence": confidence(s),
                    "regions": supplier["regions"],
                })

        scored = sorted(scored, key=lambda x: x["score"], reverse=True)

        if scored:
            best = scored[0]

            supplier_counter[best["supplier"]] += 1
            confidence_counter[best["confidence"]] += 1

            matches.append({
                "description": item.get("description"),
                "product_type": item.get("product_type"),
                "category": item.get("category"),
                "brand": item.get("brand"),
                "quantity": item.get("quantity"),
                "unit": item.get("unit"),
                "estimated_total": item.get("estimated_total"),
                "pricing_confidence": item.get("pricing_confidence"),
                "matched_supplier": best["supplier"],
                "match_score": best["score"],
                "supplier_confidence": best["confidence"],
                "all_matches": scored[:5],
            })

    summary = {
        "generated_at": now_iso(),
        "matched_items": len(matches),
        "supplier_counts": dict(supplier_counter),
        "confidence_counts": dict(confidence_counter),
    }

    output = {
        "generated_at": now_iso(),
        "matches": matches,
        "summary": summary,
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Supplier matches written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"\nMatched items: {len(matches)}")

    print("\nTop suppliers:")
    for k, v in supplier_counter.most_common():
        print(f"- {k}: {v}")

    print("\nConfidence:")
    for k, v in confidence_counter.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
