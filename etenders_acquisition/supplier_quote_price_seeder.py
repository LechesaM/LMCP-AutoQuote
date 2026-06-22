#!/usr/bin/env python3
import csv
import random
from pathlib import Path

SUPPLIER_QUOTES_DIR = Path("/Users/cash/Documents/runtime/supplier_quotes")

PRICE_BY_SUPPLIER = {
    "BMG": 1.08,
    "Bearing_Man_Group": 1.00,
    "Builders_Warehouse": 0.95,
    "RS_Components": 1.12,
}

BASE_BY_PRODUCT = {
    "bearing": 450,
    "pump": 8500,
    "valve": 2500,
    "pipe": 180,
    "cable": 45,
    "general": 100,
}


def numeric(value, default=1.0):
    try:
        return float(str(value).replace(",", "").strip() or default)
    except Exception:
        return default


def price_for(row, supplier_key):
    product_type = (row.get("product_type") or "general").lower()
    qty = numeric(row.get("quantity"), 1.0)

    base = BASE_BY_PRODUCT.get(product_type, 100)
    supplier_factor = PRICE_BY_SUPPLIER.get(supplier_key, 1.0)
    noise = random.uniform(0.92, 1.18)

    unit_price = round(base * supplier_factor * noise, 2)
    total_price = round(unit_price * qty, 2)

    return unit_price, total_price


def seed_file(path):
    supplier_key = path.parent.name

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    for field in ["unit_price", "total_price", "availability", "lead_time", "notes"]:
        if field not in fields:
            fields.append(field)

    for row in rows:
        unit_price, total_price = price_for(row, supplier_key)
        row["unit_price"] = unit_price
        row["total_price"] = total_price
        row["availability"] = "In Stock"
        row["lead_time"] = "3-7 working days"
        row["notes"] = "Seed test pricing - replace with supplier quote"

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Seeded: {path} rows={len(rows)}")


def main():
    files = sorted(SUPPLIER_QUOTES_DIR.rglob("*.csv"))

    for path in files:
        seed_file(path)

    print(f"Seeded quote files: {len(files)}")


if __name__ == "__main__":
    main()
