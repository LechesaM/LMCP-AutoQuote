#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "boq_intelligence" / "normalized_boq_items.json"
OUT_DIR = RUNTIME_DIR / "boq_intelligence"

OUTPUT_FILE = OUT_DIR / "sanitized_boq_items.json"
SUMMARY_FILE = OUT_DIR / "sanitized_boq_summary.json"

VALID_UNITS = {
    "ea", "each", "no", "nr", "unit", "units", "item", "set", "pair",
    "box", "pack", "roll", "bag", "ream", "bundle", "lot", "l/sum", "sum",
    "m", "mm", "cm", "km", "m2", "m²", "sqm", "m3", "m³",
    "kg", "g", "ton", "tons", "l", "lt", "litre", "litres", "ml",
    "month", "months", "day", "days", "hour", "hours",
}

UNIT_NORMALIZATION = {
    "e.a": "ea",
    "each.": "each",
    "nos": "no",
    "number": "no",
    "nr.": "nr",
    "unit.": "unit",
    "units.": "units",
    "pairs": "pair",
    "boxes": "box",
    "packs": "pack",
    "rolls": "roll",
    "bags": "bag",
    "reams": "ream",
    "metre": "m",
    "meter": "m",
    "meters": "m",
    "metres": "m",
    "square meter": "m2",
    "square metre": "m2",
    "sqm.": "sqm",
    "cubic meter": "m3",
    "cubic metre": "m3",
    "kilogram": "kg",
    "kilograms": "kg",
    "grams": "g",
    "liter": "litre",
    "liters": "litres",
    "lts": "lt",
    "ltrs": "lt",
}

UNIT_PATTERN = re.compile(
    r"\b(each|ea|no|nr|unit|units|set|pair|box|pack|roll|bag|ream|m2|m²|sqm|m3|m³|mm|cm|km|m|kg|g|ton|tons|litre|litres|lt|l|ml|month|months|day|days|hour|hours)\b",
    re.I,
)

BAD_UNIT_PATTERN = re.compile(r"^\d+(\.\d+)?$|^/+\d+$|^\d+[a-z]{0,2}$", re.I)


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


def norm(value):
    return clean(value).lower().strip(". ")


def is_bad_unit(unit):
    u = norm(unit)

    if not u:
        return False

    if u in VALID_UNITS:
        return False

    if u in UNIT_NORMALIZATION:
        return False

    if BAD_UNIT_PATTERN.match(u):
        return True

    if len(u) > 20:
        return True

    return False


def normalize_unit(unit, description):
    u = norm(unit)

    if u in UNIT_NORMALIZATION:
        u = UNIT_NORMALIZATION[u]

    if u in VALID_UNITS:
        return u, "explicit_unit"

    if is_bad_unit(u):
        u = ""

    desc = clean(description)
    match = UNIT_PATTERN.search(desc)

    if match:
        found = norm(match.group(1))
        found = UNIT_NORMALIZATION.get(found, found)
        return found, "description_unit"

    return u, "missing_or_unknown"


def sanity_quantity(quantity):
    flags = []

    if quantity is None:
        flags.append("missing_quantity")
        return None, flags

    try:
        q = float(quantity)
    except Exception:
        flags.append("invalid_quantity")
        return None, flags

    if q < 0:
        flags.append("negative_quantity")

    if q == 0:
        flags.append("zero_quantity")

    if q > 100000:
        flags.append("very_high_quantity")

    if 0 < q < 0.001:
        flags.append("very_small_quantity")

    return q, flags


def item_status(item, flags):
    quality = item.get("quality")

    serious = {
        "negative_quantity",
        "invalid_quantity",
        "very_high_quantity",
        "bad_unit",
    }

    if any(f in flags for f in serious):
        return "REVIEW"

    if quality == "LOW":
        return "REVIEW"

    if "missing_quantity" in flags:
        return "INCOMPLETE"

    return "USABLE"


def main():
    data = load_json(INPUT_FILE, default={})
    items = data.get("items", [])

    sanitized = []
    review = []
    incomplete = []

    for item in items:
        flags = list(item.get("flags") or [])

        unit, unit_source = normalize_unit(
            item.get("unit"),
            item.get("description"),
        )

        if item.get("unit") and is_bad_unit(item.get("unit")):
            flags.append("bad_unit")

        quantity, quantity_flags = sanity_quantity(item.get("quantity"))
        flags.extend(quantity_flags)

        status = item_status(item, flags)

        clean_item = dict(item)
        clean_item["quantity"] = quantity
        clean_item["unit"] = unit
        clean_item["unit_source"] = unit_source
        clean_item["sanity_flags"] = sorted(set(flags))
        clean_item["sanity_status"] = status

        if status == "USABLE":
            sanitized.append(clean_item)
        elif status == "INCOMPLETE":
            incomplete.append(clean_item)
        else:
            review.append(clean_item)

    all_items = sanitized + incomplete + review

    status_counts = Counter(i["sanity_status"] for i in all_items)
    unit_counts = Counter(i.get("unit") or "missing" for i in all_items)
    category_counts = Counter(i.get("category") for i in all_items)

    output = {
        "generated_at": now_iso(),
        "total_input_items": len(items),
        "usable_items": len(sanitized),
        "incomplete_items": len(incomplete),
        "review_items": len(review),
        "status_counts": dict(status_counts),
        "unit_counts": dict(unit_counts),
        "category_counts": dict(category_counts),
        "items": all_items,
        "usable": sanitized,
        "incomplete": incomplete[:1000],
        "review": review[:1000],
    }

    summary = {
        "generated_at": output["generated_at"],
        "total_input_items": len(items),
        "usable_items": len(sanitized),
        "incomplete_items": len(incomplete),
        "review_items": len(review),
        "status_counts": dict(status_counts),
        "unit_counts_top_30": dict(unit_counts.most_common(30)),
        "category_counts": dict(category_counts),
    }

    write_json(OUTPUT_FILE, output)
    write_json(SUMMARY_FILE, summary)

    print(f"Sanitized BOQ items written: {OUTPUT_FILE}")
    print(f"Summary written: {SUMMARY_FILE}")
    print(f"Input items: {len(items)}")
    print(f"Usable items: {len(sanitized)}")
    print(f"Incomplete items: {len(incomplete)}")
    print(f"Review items: {len(review)}")


if __name__ == "__main__":
    main()
