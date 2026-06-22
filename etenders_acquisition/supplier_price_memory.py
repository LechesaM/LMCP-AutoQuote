#!/usr/bin/env python3

import json
import re

from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = (
    RUNTIME_DIR
    / "supplier_quote_ingestion"
    / "supplier_quote_comparison_matrix.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_price_memory"

MEMORY_FILE = OUT_DIR / "supplier_price_memory.json"
SUMMARY_FILE = OUT_DIR / "supplier_price_memory_summary.json"


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


def safe_float(v):
    try:
        if v is None or v == "":
            return None

        return float(v)

    except Exception:
        return None


def normalize_description(text):
    text = str(text or "").lower()

    text = re.sub(r"vendors are responsible.*", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()[:220]


def build_memory(comparison_lines):
    memory = defaultdict(list)

    for line in comparison_lines:
        desc_key = line.get("description_key") or normalize_description(
            line.get("description")
        )

        desc = line.get("description")

        for quote in line.get("quotes", []):
            supplier = quote.get("supplier")

            unit_price = safe_float(quote.get("unit_price"))
            total_price = safe_float(quote.get("total_price"))

            if not supplier:
                continue

            if not desc_key:
                continue

            if unit_price is None and total_price is None:
                continue

            memory[desc_key].append({
                "description": desc,
                "supplier": supplier,
                "unit_price": unit_price,
                "total_price": total_price,
                "quantity": quote.get("quantity"),
                "unit": quote.get("unit"),
                "availability": quote.get("availability"),
                "lead_time": quote.get("lead_time"),
                "notes": quote.get("notes"),
                "source_file": quote.get("source_file"),
                "captured_at": now_iso(),
            })

    return dict(memory)


def summarize(memory):
    supplier_counts = defaultdict(int)

    total_prices = 0
    items_with_pricing = 0

    for _, rows in memory.items():
        total_prices += len(rows)

        priced = [
            r for r in rows
            if r.get("unit_price") is not None
            or r.get("total_price") is not None
        ]

        if priced:
            items_with_pricing += 1

        for r in rows:
            supplier_counts[r["supplier"]] += 1

    return {
        "generated_at": now_iso(),
        "unique_items": len(memory),
        "total_price_records": total_prices,
        "items_with_pricing": items_with_pricing,
        "supplier_record_counts": dict(
            sorted(
                supplier_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ),
    }


def main():
    data = load_json(INPUT_FILE)

    comparison_lines = data.get("comparison", [])

    memory = build_memory(comparison_lines)

    summary = summarize(memory)

    write_json(
        MEMORY_FILE,
        {
            "generated_at": now_iso(),
            "source_file": str(INPUT_FILE),
            "price_memory": memory,
        },
    )

    write_json(SUMMARY_FILE, summary)

    print(f"Price memory written: {MEMORY_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Unique items: {summary['unique_items']}")
    print(f"Total price records: {summary['total_price_records']}")
    print(f"Items with pricing: {summary['items_with_pricing']}")

    print("Supplier counts:")

    for supplier, count in summary["supplier_record_counts"].items():
        print(f"- {supplier}: {count}")


if __name__ == "__main__":
    main()

