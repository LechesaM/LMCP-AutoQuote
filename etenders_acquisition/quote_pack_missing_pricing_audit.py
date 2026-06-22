#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
MANUAL_PRODUCTION_DIR = RUNTIME_DIR / "manual_production"

QUOTE_PACK_INDEX_FILE = MANUAL_PRODUCTION_DIR / "quote_pack_index.json"
OUTPUT_FILE = MANUAL_PRODUCTION_DIR / "missing_pricing_audit.json"


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_packs(index_data):
    if isinstance(index_data, list):
        return index_data

    if not isinstance(index_data, dict):
        return []

    for key in ["quote_packs", "packs", "items", "quote_pack_index", "data", "results"]:
        value = index_data.get(key)
        if isinstance(value, list):
            return value

    return []


def is_priced(pack):
    return bool(
        pack.get("pricing_attached")
        or pack.get("has_pricing")
        or pack.get("priced")
        or pack.get("pricing_summary_file")
        or pack.get("pricing_summary_path")
        or pack.get("pricing")
    )


def classify_missing_reason(pack):
    text_blob = json.dumps(pack, default=str).lower()

    if "boq" not in text_blob and "bill" not in text_blob and "schedule" not in text_blob:
        return "no_detected_boq"

    if "pdf" in text_blob and ("image" in text_blob or "scan" in text_blob or "ocr" in text_blob):
        return "likely_scanned_pdf_or_ocr_required"

    if "extraction" in text_blob and ("failed" in text_blob or "error" in text_blob):
        return "extraction_failed"

    if "no rows" in text_blob or "empty" in text_blob:
        return "boq_extracted_no_rows"

    if "non_priceable" in text_blob or "non-priceable" in text_blob:
        return "classified_non_priceable"

    if "quantity" not in text_blob and "qty" not in text_blob:
        return "missing_quantities"

    if "rate" not in text_blob and "price" not in text_blob:
        return "missing_rates"

    return "unknown_missing_pricing_reason"


def tender_id(pack):
    return (
        pack.get("tender_id")
        or pack.get("tender_ref")
        or pack.get("reference")
        or pack.get("bid_number")
        or pack.get("title")
        or "UNKNOWN"
    )


def main():
    index_data = load_json(QUOTE_PACK_INDEX_FILE, default={})
    packs = extract_packs(index_data)

    missing = []
    reason_counts = {}

    for pack in packs:
        if not isinstance(pack, dict):
            continue

        if is_priced(pack):
            continue

        reason = classify_missing_reason(pack)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

        missing.append({
            "tender_id": tender_id(pack),
            "missing_reason": reason,
            "pack_path": pack.get("quote_pack_path")
            or pack.get("pack_path")
            or pack.get("path")
            or pack.get("file"),
            "source": pack,
        })

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_quote_packs": len(packs),
        "missing_pricing": len(missing),
        "reason_counts": reason_counts,
        "missing_pricing_items": missing,
    }

    write_json(OUTPUT_FILE, output)

    print(f"Missing pricing audit generated: {OUTPUT_FILE}")
    print(f"Total packs: {len(packs)}")
    print(f"Missing pricing: {len(missing)}")

    print("\nReason counts:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"- {reason}: {count}")


if __name__ == "__main__":
    main()
