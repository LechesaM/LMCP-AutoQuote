#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

PRICE_MEMORY_FILE = (
    RUNTIME_DIR
    / "supplier_price_memory"
    / "supplier_price_memory.json"
)

ESTIMATE_FILE = (
    RUNTIME_DIR
    / "historical_price_estimator"
    / "estimated_pricing.json"
)

OUT_DIR = RUNTIME_DIR / "supplier_expansion"

CATALOG_FILE = OUT_DIR / "supplier_catalog_index.json"
PART_NUMBER_FILE = OUT_DIR / "manufacturer_part_index.json"
SUBSTITUTION_FILE = OUT_DIR / "part_substitution_index.json"
SUMMARY_FILE = OUT_DIR / "supplier_expansion_summary.json"


PART_PATTERNS = [
    r"\b[A-Z]{1,5}[0-9]{2,10}[A-Z0-9\-\/]*\b",
    r"\b[0-9]{3,}[A-Z0-9\-\/]+\b",
    r"\b[A-Z0-9]+\-[A-Z0-9\-]+\b",
]


OEM_HINTS = [
    "SKF",
    "FAG",
    "NSK",
    "TIMKEN",
    "SIEMENS",
    "ABB",
    "SCHNEIDER",
    "BOSCH",
    "LINATEX",
    "HOFFMAN",
]


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


def normalize(text):
    text = str(text or "").upper()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_part_numbers(text):
    text = normalize(text)

    parts = set()

    for pattern in PART_PATTERNS:
        matches = re.findall(pattern, text)

        for m in matches:
            m = m.strip()

            if len(m) >= 4:
                parts.add(m)

    return sorted(parts)


def detect_oem(text):
    text = normalize(text)

    found = []

    for oem in OEM_HINTS:
        if oem in text:
            found.append(oem)

    return found


def build_supplier_catalog(memory):
    catalog = defaultdict(list)

    for desc_key, rows in memory.get("price_memory", {}).items():
        for row in rows:
            supplier = row.get("supplier") or "UNKNOWN"

            entry = {
                "description": row.get("description"),
                "unit_price": row.get("unit_price"),
                "total_price": row.get("total_price"),
                "quantity": row.get("quantity"),
                "unit": row.get("unit"),
            }

            catalog[supplier].append(entry)

    return catalog


def build_part_index(memory):
    part_index = defaultdict(list)

    for desc_key, rows in memory.get("price_memory", {}).items():
        for row in rows:
            description = row.get("description") or ""

            parts = extract_part_numbers(description)
            oems = detect_oem(description)

            for part in parts:
                part_index[part].append({
                    "supplier": row.get("supplier"),
                    "description": description,
                    "unit_price": row.get("unit_price"),
                    "unit": row.get("unit"),
                    "oems": oems,
                })

    return part_index


def build_substitutions(part_index):
    substitutions = defaultdict(list)

    grouped = defaultdict(set)

    for part, rows in part_index.items():
        for row in rows:
            desc = normalize(row.get("description"))

            grouped[desc].add(part)

    for desc, parts in grouped.items():
        parts = sorted(parts)

        if len(parts) > 1:
            for p in parts:
                substitutions[p].extend(
                    [x for x in parts if x != p]
                )

    final = {}

    for part, subs in substitutions.items():
        final[part] = sorted(set(subs))

    return final


def analyze_unmatched(estimates):
    unmatched = []

    for item in estimates.get("estimates", []):
        if item.get("estimate_status") == "NO_MATCH":
            unmatched.append({
                "description": item.get("description"),
                "category": item.get("category"),
                "quantity": item.get("quantity"),
                "unit": item.get("unit"),
            })

    return unmatched


def main():
    memory = load_json(PRICE_MEMORY_FILE, default={})
    estimates = load_json(ESTIMATE_FILE, default={})

    supplier_catalog = build_supplier_catalog(memory)
    part_index = build_part_index(memory)
    substitutions = build_substitutions(part_index)

    unmatched = analyze_unmatched(estimates)

    catalog_output = {
        "generated_at": now_iso(),
        "supplier_catalog": dict(supplier_catalog),
    }

    part_output = {
        "generated_at": now_iso(),
        "manufacturer_part_index": dict(part_index),
    }

    substitution_output = {
        "generated_at": now_iso(),
        "substitutions": substitutions,
    }

    supplier_counts = {
        supplier: len(items)
        for supplier, items in supplier_catalog.items()
    }

    oem_counter = Counter()

    for rows in part_index.values():
        for row in rows:
            for oem in row.get("oems", []):
                oem_counter[oem] += 1

    summary = {
        "generated_at": now_iso(),
        "suppliers_indexed": len(supplier_catalog),
        "catalog_items": sum(len(v) for v in supplier_catalog.values()),
        "manufacturer_parts": len(part_index),
        "substitution_groups": len(substitutions),
        "unmatched_items": len(unmatched),
        "supplier_counts": supplier_counts,
        "top_oems": dict(oem_counter.most_common(20)),
    }

    write_json(CATALOG_FILE, catalog_output)
    write_json(PART_NUMBER_FILE, part_output)
    write_json(SUBSTITUTION_FILE, substitution_output)
    write_json(SUMMARY_FILE, summary)

    print(f"Catalog written: {CATALOG_FILE}")
    print(f"Part index written: {PART_NUMBER_FILE}")
    print(f"Substitution index written: {SUBSTITUTION_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")

    print(f"Suppliers indexed: {summary['suppliers_indexed']}")
    print(f"Catalog items: {summary['catalog_items']}")
    print(f"Manufacturer parts: {summary['manufacturer_parts']}")
    print(f"Substitution groups: {summary['substitution_groups']}")
    print(f"Unmatched items: {summary['unmatched_items']}")

    print("\nTop OEMs:")
    for oem, count in summary["top_oems"].items():
        print(f"- {oem}: {count}")


if __name__ == "__main__":
    main()
