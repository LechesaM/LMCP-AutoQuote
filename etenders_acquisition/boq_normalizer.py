#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "boq_intelligence" / "excel_boq_parse_results.json"
OUT_DIR = RUNTIME_DIR / "boq_intelligence"

OUTPUT_FILE = OUT_DIR / "normalized_boq_items.json"
SUMMARY_FILE = OUT_DIR / "normalized_boq_summary.json"


BAD_DESCRIPTION_HINTS = [
    "signature",
    "signed",
    "initial",
    "witness",
    "page",
    "date",
    "name of bidder",
    "company name",
    "registration number",
    "tax compliance",
    "bbbee",
    "b-bbee",
    "cidb",
    "declaration",
    "returnable",
    "yes/no",
    "tick",
    "comply",
    "non-compliance",
    "evaluation",
    "risk assessment",
    "baseline risk",
    "environmental",
    "health and safety",
    "safety file",
    "tenderer",
    "supplier quality",
    "quality management",
    "local content",
    "imports declaration",
]

GOOD_DESCRIPTION_HINTS = [
    "supply",
    "delivery",
    "provide",
    "install",
    "item",
    "material",
    "equipment",
    "consumable",
    "furniture",
    "stationery",
    "ppe",
    "tool",
    "kit",
    "battery",
    "cartridge",
    "toner",
    "computer",
    "laptop",
    "desktop",
    "printer",
    "pump",
    "valve",
    "motor",
    "bearing",
    "gasket",
    "seal",
    "cable",
    "light",
    "uniform",
    "gloves",
    "boots",
]

UNITS = {
    "each", "ea", "no", "nr", "unit", "units", "item",
    "m", "mm", "cm", "km", "m2", "m²", "sqm", "m3", "m³",
    "kg", "g", "ton", "tons", "l", "litre", "litres",
    "box", "pack", "set", "pair", "roll", "bag", "ream",
    "month", "months", "day", "days", "hour", "hours",
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


def clean(value):
    value = "" if value is None else str(value)
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_text(value):
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9\s./&()+\-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def numeric(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        pass

    s = clean(value)
    s = s.replace(",", "")
    s = re.sub(r"[^\d.\-]", "", s)

    if s in ["", ".", "-", "-."]:
        return None

    try:
        return float(s)
    except Exception:
        return None


def detect_unit(description, explicit_unit):
    explicit = normalize_text(explicit_unit)

    if explicit in UNITS:
        return explicit

    words = normalize_text(description).split()

    for w in words:
        if w in UNITS:
            return w

    return explicit or ""


def classify_quality(description, quantity, unit, rate, source_filename):
    text = normalize_text(description)
    filename = normalize_text(source_filename)

    score = 0
    flags = []

    if len(text) >= 15:
        score += 10
    else:
        flags.append("short_description")

    if quantity is not None:
        score += 20
    else:
        flags.append("missing_quantity")

    if unit:
        score += 10
    else:
        flags.append("missing_unit")

    if rate is not None:
        score += 5

    for h in GOOD_DESCRIPTION_HINTS:
        if h in text:
            score += 5

    for h in BAD_DESCRIPTION_HINTS:
        if h in text:
            score -= 15
            flags.append(f"bad_hint:{h}")

    if any(h in filename for h in ["boq", "pricing", "price", "bill of quantities", "schedule"]):
        score += 20

    if any(h in filename for h in ["risk assessment", "returnable", "quality", "environmental"]):
        score -= 25
        flags.append("weak_source_document")

    if quantity is not None and quantity <= 0:
        flags.append("non_positive_quantity")
        score -= 10

    if quantity is not None and quantity > 100000:
        flags.append("very_high_quantity")
        score -= 10

    if score >= 45:
        quality = "HIGH"
    elif score >= 25:
        quality = "MEDIUM"
    elif score >= 10:
        quality = "LOW"
    else:
        quality = "REJECT"

    return quality, score, flags


def make_item_id(source_file, sheet_name, row_number, description):
    raw = f"{source_file}|{sheet_name}|{row_number}|{description}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def infer_category(description):
    text = normalize_text(description)

    rules = [
        ("ict", ["laptop", "desktop", "computer", "printer", "server", "tablet", "monitor", "keyboard", "mouse"]),
        ("ppe", ["ppe", "gloves", "boots", "helmet", "overall", "protective", "uniform"]),
        ("stationery", ["stationery", "paper", "pen", "ream", "file", "toner", "cartridge"]),
        ("electrical", ["cable", "light", "led", "switch", "breaker", "battery", "transformer"]),
        ("mechanical", ["pump", "valve", "bearing", "motor", "gasket", "seal", "bolt"]),
        ("furniture", ["chair", "table", "desk", "cabinet", "furniture", "boardroom"]),
        ("building_material", ["cement", "brick", "sand", "aggregate", "paint", "timber", "steel"]),
        ("medical", ["medical", "surgical", "dialysis", "implant", "consumable", "gloves"]),
        ("cleaning", ["cleaning", "detergent", "soap", "disinfectant", "mop", "broom"]),
    ]

    for category, hints in rules:
        if any(h in text for h in hints):
            return category

    return "general_supply"


def normalize_items():
    data = load_json(INPUT_FILE, default={})
    results = data.get("results", [])

    normalized = []
    rejected = []

    for workbook in results:
        if not workbook.get("success"):
            continue

        source_path = workbook.get("path")
        source_filename = workbook.get("filename")

        for sheet in workbook.get("sheets", []):
            sheet_name = sheet.get("sheet_name")

            for item in sheet.get("items", []):
                description = clean(item.get("description"))
                quantity = numeric(item.get("quantity"))
                unit = detect_unit(description, item.get("unit"))
                rate = numeric(item.get("rate"))

                quality, score, flags = classify_quality(
                    description,
                    quantity,
                    unit,
                    rate,
                    source_filename,
                )

                normalized_item = {
                    "item_id": make_item_id(
                        source_filename,
                        sheet_name,
                        item.get("source_row_number"),
                        description,
                    ),
                    "description": description,
                    "description_normalized": normalize_text(description),
                    "quantity": quantity,
                    "quantity_raw": item.get("quantity_raw"),
                    "unit": unit,
                    "rate": rate,
                    "rate_raw": item.get("rate_raw"),
                    "category": infer_category(description),
                    "quality": quality,
                    "quality_score": score,
                    "flags": flags,
                    "source": {
                        "workbook": source_filename,
                        "path": source_path,
                        "sheet": sheet_name,
                        "row_number": item.get("source_row_number"),
                        "tender_folder": Path(source_path).parent.name if source_path else None,
                    },
                    "raw_row_values": item.get("row_values", []),
                }

                if quality == "REJECT":
                    rejected.append(normalized_item)
                else:
                    normalized.append(normalized_item)

    return normalized, rejected


def main():
    normalized, rejected = normalize_items()

    category_counts = Counter(i["category"] for i in normalized)
    quality_counts = Counter(i["quality"] for i in normalized)
    unit_counts = Counter(i["unit"] or "missing" for i in normalized)

    output = {
        "generated_at": now_iso(),
        "total_normalized_items": len(normalized),
        "total_rejected_items": len(rejected),
        "category_counts": dict(category_counts),
        "quality_counts": dict(quality_counts),
        "unit_counts": dict(unit_counts),
        "items": normalized,
        "rejected_items_sample": rejected[:500],
    }

    summary = {
        "generated_at": output["generated_at"],
        "total_normalized_items": len(normalized),
        "total_rejected_items": len(rejected),
        "category_counts": dict(category_counts),
        "quality_counts": dict(quality_counts),
        "unit_counts_top_30": dict(unit_counts.most_common(30)),
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"BOQ normalized items written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Normalized items: {len(normalized)}")
    print(f"Rejected items: {len(rejected)}")
    print("Quality counts:")
    for k, v in quality_counts.most_common():
        print(f"- {k}: {v}")
    print("Category counts:")
    for k, v in category_counts.most_common():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
