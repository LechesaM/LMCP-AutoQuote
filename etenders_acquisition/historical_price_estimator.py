#!/usr/bin/env python3
import json
import re
import difflib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

ITEMS_FILE = RUNTIME_DIR / "boq_intelligence" / "deduplicated_boq_items.json"
MEMORY_FILE = RUNTIME_DIR / "supplier_price_memory" / "supplier_price_memory.json"

OUT_DIR = RUNTIME_DIR / "historical_price_estimator"
OUTPUT_FILE = OUT_DIR / "estimated_pricing.json"
SUMMARY_FILE = OUT_DIR / "historical_price_estimator_summary.json"

MIN_SIMILARITY = 0.55


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


def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def norm(text):
    text = str(text or "").lower()
    text = re.sub(r"vendors are responsible.*", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:220]


def unit_price_from_record(record):
    unit_price = record.get("unit_price")
    total_price = record.get("total_price")
    quantity = record.get("quantity") or 1

    if unit_price is not None:
        return money(unit_price)

    try:
        quantity = float(quantity or 1)
    except Exception:
        quantity = 1

    if total_price is not None and quantity > 0:
        return money(float(total_price) / quantity)

    return None


def build_memory_index(memory):
    records = []

    price_memory = memory.get("price_memory", {})

    for desc_key, rows in price_memory.items():
        for row in rows:
            unit_price = unit_price_from_record(row)

            if unit_price is None or unit_price <= 0:
                continue

            records.append({
                "description_key": desc_key,
                "description": row.get("description") or desc_key,
                "description_norm": norm(row.get("description") or desc_key),
                "supplier": row.get("supplier"),
                "unit_price": unit_price,
                "unit": row.get("unit"),
                "source_total_price": row.get("total_price"),
                "source_quantity": row.get("quantity"),
                "availability": row.get("availability"),
                "lead_time": row.get("lead_time"),
            })

    return records


def find_best_match(item_desc, item_unit, memory_records):
    item_norm = norm(item_desc)
    item_tokens = set(item_norm.split())

    best = None

    for rec in memory_records:
        rec_norm = rec["description_norm"]
        rec_tokens = set(rec_norm.split())

        ratio = difflib.SequenceMatcher(None, item_norm, rec_norm).ratio()

        overlap = 0
        if item_tokens and rec_tokens:
            overlap = len(item_tokens & rec_tokens) / max(len(item_tokens), 1)

        unit_bonus = 0.05 if item_unit and rec.get("unit") == item_unit else 0

        score = round((ratio * 0.7) + (overlap * 0.25) + unit_bonus, 4)

        if best is None or score > best["match_score"]:
            best = {
                "match_score": score,
                "memory_record": rec,
            }

    return best


def confidence_from_score(score):
    if score >= 0.82:
        return "HIGH"

    if score >= 0.68:
        return "MEDIUM"

    if score >= MIN_SIMILARITY:
        return "LOW"

    return "NO_MATCH"


def estimate_item(item, memory_records):
    desc = item.get("description")
    qty = item.get("aggregate_quantity") or item.get("quantity") or 1
    unit = item.get("unit")

    try:
        qty = float(qty or 1)
    except Exception:
        qty = 1

    best = find_best_match(desc, unit, memory_records)

    if not best or best["match_score"] < MIN_SIMILARITY:
        return {
            "description": desc,
            "quantity": qty,
            "unit": unit,
            "category": item.get("category"),
            "estimate_status": "NO_MATCH",
            "estimated_unit_price": None,
            "estimated_total": None,
            "confidence": "NO_MATCH",
            "match_score": best["match_score"] if best else None,
        }

    rec = best["memory_record"]
    unit_price = rec["unit_price"]
    total = money(unit_price * qty)

    confidence = confidence_from_score(best["match_score"])

    return {
        "description": desc,
        "quantity": qty,
        "unit": unit,
        "category": item.get("category"),
        "estimate_status": "ESTIMATED",
        "estimated_unit_price": unit_price,
        "estimated_total": total,
        "confidence": confidence,
        "match_score": best["match_score"],
        "matched_supplier": rec.get("supplier"),
        "matched_description": rec.get("description"),
        "matched_unit": rec.get("unit"),
        "availability": rec.get("availability"),
        "lead_time": rec.get("lead_time"),
    }


def main():
    item_data = load_json(ITEMS_FILE, default={})
    memory_data = load_json(MEMORY_FILE, default={})

    candidate_items = item_data.get("usable_pricing_items", [])

    memory_records = build_memory_index(memory_data)

    estimates = []

    for item in candidate_items:
        estimates.append(estimate_item(item, memory_records))

    estimated = [e for e in estimates if e["estimate_status"] == "ESTIMATED"]
    no_match = [e for e in estimates if e["estimate_status"] == "NO_MATCH"]

    confidence_counts = Counter(e["confidence"] for e in estimates)
    category_counts = Counter(e.get("category") or "unknown" for e in estimates)

    total_estimated_value = money(
        sum(money(e.get("estimated_total")) for e in estimated)
    )

    summary = {
        "generated_at": now_iso(),
        "candidate_items": len(candidate_items),
        "memory_records": len(memory_records),
        "estimated_items": len(estimated),
        "no_match_items": len(no_match),
        "total_estimated_value": total_estimated_value,
        "confidence_counts": dict(confidence_counts),
        "category_counts": dict(category_counts),
    }

    output = {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "estimates": estimates,
        "estimated": estimated,
        "no_match_sample": no_match[:500],
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Historical estimates written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Candidate items: {summary['candidate_items']}")
    print(f"Memory records: {summary['memory_records']}")
    print(f"Estimated items: {summary['estimated_items']}")
    print(f"No match items: {summary['no_match_items']}")
    print(f"Total estimated value: R{summary['total_estimated_value']:,.2f}")


if __name__ == "__main__":
    main()
