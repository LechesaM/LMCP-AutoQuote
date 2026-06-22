import json
from pathlib import Path


QUOTE_PACK_DIR = Path("/Users/cash/Documents/runtime/manual_production/quote_packs")
OUTPUT_FILE = Path("/Users/cash/Documents/runtime/manual_production/quote_pack_index.json")


def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def main():
    packs = []

    for pack_dir in sorted(QUOTE_PACK_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue

        quote_summary_path = pack_dir / "quote_summary.json"
        pricing_summary_path = pack_dir / "pricing_summary.json"

        quote_summary = load_json(quote_summary_path) or {}
        pricing_summary = load_json(pricing_summary_path)

        tender_id = quote_summary.get("tender_id") or pack_dir.name

        has_pricing = pricing_summary is not None
        pricing_status = pricing_summary.get("status") if pricing_summary else "MISSING_PRICING"

        packs.append({
            "tender_id": tender_id,
            "pack_dir": str(pack_dir),
            "quote_summary_path": str(quote_summary_path),
            "pricing_summary_path": str(pricing_summary_path) if has_pricing else None,
            "quote_ready": quote_summary.get("quote_ready", False),
            "has_pricing": has_pricing,
            "pricing_status": pricing_status,
            "total_incl_vat": pricing_summary.get("total_incl_vat") if pricing_summary else None,
            "priced_items": pricing_summary.get("priced_items") if pricing_summary else 0,
            "flags": pricing_summary.get("flags") if pricing_summary else [],
        })

    index = {
        "total_quote_packs": len(packs),
        "priced_quote_packs": sum(1 for p in packs if p["has_pricing"]),
        "missing_pricing": sum(1 for p in packs if not p["has_pricing"]),
        "review_required": sum(1 for p in packs if p["pricing_status"] == "REVIEW_REQUIRED"),
        "ready_without_flags": sum(1 for p in packs if p["pricing_status"] == "OK"),
        "packs": packs,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"Quote pack index generated: {OUTPUT_FILE}")
    print(f"Total packs: {index['total_quote_packs']}")
    print(f"Priced packs: {index['priced_quote_packs']}")
    print(f"Missing pricing: {index['missing_pricing']}")
    print(f"Review required: {index['review_required']}")
    print(f"Ready without flags: {index['ready_without_flags']}")


if __name__ == "__main__":
    main()
