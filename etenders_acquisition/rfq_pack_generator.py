#!/usr/bin/env python3
import csv
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "supplier_matching" / "supplier_matches.json"

OUT_DIR = RUNTIME_DIR / "rfq_packs"
INDEX_FILE = OUT_DIR / "rfq_pack_index.json"
SUMMARY_FILE = OUT_DIR / "rfq_pack_summary.json"


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


def safe_slug(value):
    value = str(value or "unknown")
    value = re.sub(r"[^\w\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")[:100] or "unknown"


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "line_no",
        "description",
        "product_type",
        "category",
        "brand",
        "quantity",
        "unit",
        "estimated_total",
        "pricing_confidence",
        "supplier_confidence",
        "match_score",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for i, row in enumerate(rows, start=1):
            writer.writerow({
                "line_no": i,
                "description": row.get("description"),
                "product_type": row.get("product_type"),
                "category": row.get("category"),
                "brand": row.get("brand"),
                "quantity": row.get("quantity"),
                "unit": row.get("unit"),
                "estimated_total": row.get("estimated_total"),
                "pricing_confidence": row.get("pricing_confidence"),
                "supplier_confidence": row.get("supplier_confidence"),
                "match_score": row.get("match_score"),
            })


def make_supplier_letter(supplier, items, estimated_total):
    return f"""REQUEST FOR QUOTATION

Supplier:
{supplier}

Date:
{datetime.now().strftime("%Y-%m-%d")}

Dear Supplier,

Please provide your best quotation for the listed items.

Summary:
- Total line items: {len(items)}
- Estimated procurement value: R{estimated_total:,.2f}
- Required response: Unit price, availability, delivery lead time, VAT status, and validity period.

Instructions:
1. Quote all items you can supply.
2. Clearly mark unavailable items.
3. Include delivery cost if applicable.
4. Confirm brand, model, or equivalent alternative.
5. Provide lead time per item.
6. State quotation validity period.

Regards,
LMCP AutoQuote
"""


def main():
    data = load_json(INPUT_FILE, default={})
    matches = data.get("matches", [])

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    grouped = defaultdict(list)

    for item in matches:
        supplier = item.get("matched_supplier") or "Unknown Supplier"
        grouped[supplier].append(item)

    rfq_packs = []

    for supplier, items in sorted(grouped.items()):
        supplier_dir = OUT_DIR / safe_slug(supplier)
        supplier_dir.mkdir(parents=True, exist_ok=True)

        estimated_total = money(sum(money(i.get("estimated_total")) for i in items))

        category_counts = Counter(i.get("category") or "unknown" for i in items)
        product_type_counts = Counter(i.get("product_type") or "unknown" for i in items)
        confidence_counts = Counter(i.get("supplier_confidence") or "unknown" for i in items)

        rfq_json = {
            "generated_at": now_iso(),
            "supplier": supplier,
            "item_count": len(items),
            "estimated_total_value": estimated_total,
            "category_counts": dict(category_counts),
            "product_type_counts": dict(product_type_counts),
            "supplier_confidence_counts": dict(confidence_counts),
            "rfq_status": "READY_FOR_SUPPLIER_PRICING",
            "items": items,
        }

        json_path = supplier_dir / "rfq_pack.json"
        csv_path = supplier_dir / "rfq_items.csv"
        letter_path = supplier_dir / "rfq_request_letter.txt"

        write_json(json_path, rfq_json)
        write_csv(csv_path, items)

        with letter_path.open("w", encoding="utf-8") as f:
            f.write(make_supplier_letter(supplier, items, estimated_total))

        rfq_packs.append({
            "supplier": supplier,
            "item_count": len(items),
            "estimated_total_value": estimated_total,
            "rfq_json": str(json_path),
            "rfq_csv": str(csv_path),
            "rfq_letter": str(letter_path),
            "category_counts": dict(category_counts),
            "product_type_counts": dict(product_type_counts),
            "supplier_confidence_counts": dict(confidence_counts),
        })

    total_items = sum(p["item_count"] for p in rfq_packs)
    total_estimated_value = money(sum(p["estimated_total_value"] for p in rfq_packs))

    index = {
        "generated_at": now_iso(),
        "source_file": str(INPUT_FILE),
        "total_rfq_packs": len(rfq_packs),
        "total_items": total_items,
        "total_estimated_value": total_estimated_value,
        "packs": rfq_packs,
    }

    summary = {
        "generated_at": index["generated_at"],
        "total_rfq_packs": len(rfq_packs),
        "total_items": total_items,
        "total_estimated_value": total_estimated_value,
        "suppliers": [
            {
                "supplier": p["supplier"],
                "item_count": p["item_count"],
                "estimated_total_value": p["estimated_total_value"],
            }
            for p in rfq_packs
        ],
    }

    write_json(INDEX_FILE, index)
    write_json(SUMMARY_FILE, summary)

    print(f"RFQ packs generated: {OUT_DIR}")
    print(f"Index: {INDEX_FILE}")
    print(f"Summary: {SUMMARY_FILE}")
    print(f"RFQ packs: {len(rfq_packs)}")
    print(f"Total items: {total_items}")
    print(f"Estimated value: R{total_estimated_value:,.2f}")

    for p in rfq_packs:
        print(f"- {p['supplier']}: items={p['item_count']} value=R{p['estimated_total_value']:,.2f}")


if __name__ == "__main__":
    main()
