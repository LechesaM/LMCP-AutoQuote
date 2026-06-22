import json
from collections import defaultdict
from pathlib import Path

from app.db.models import BOQItem
from app.db.session import SessionLocal


OUTPUT_DIR = Path("/Users/cash/Documents/runtime/pricing_summaries")

HIGH_TOTAL_THRESHOLD = 50_000_000

SERIOUS_FLAGS = {
    "high_tender_total",
    "high_item_total",
    "extreme_quantity",
}


def load_raw(item):
    try:
        return json.loads(item.raw_row_json or "{}")
    except Exception:
        return {}


def safe_filename(tender_id):
    return tender_id.replace("/", "_")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summaries = defaultdict(lambda: {
        "tender_id": None,
        "priced_items": 0,
        "total_excl_vat": 0.0,
        "vat_amount": 0.0,
        "total_incl_vat": 0.0,
        "flags": [],
        "serious_flags": [],
        "status": "OK",
        "pricing_mode": "rule_based_default",
        "requires_manual_review": False,
    })

    with SessionLocal() as session:
        items = session.query(BOQItem).all()

        for item in items:
            raw = load_raw(item)
            pricing = raw.get("pricing")

            if not pricing:
                continue

            tender_id = item.tender_id or "UNKNOWN"
            summary = summaries[tender_id]

            summary["tender_id"] = tender_id
            summary["priced_items"] += 1
            summary["total_excl_vat"] += float(pricing.get("total_excl_vat") or 0)
            summary["vat_amount"] += float(pricing.get("vat_amount") or 0)
            summary["total_incl_vat"] += float(pricing.get("total_incl_vat") or 0)

            validation = raw.get("pricing_validation", {})
            for flag in validation.get("flags", []):
                if flag not in summary["flags"]:
                    summary["flags"].append(flag)

    for tender_id, summary in summaries.items():
        if summary["total_incl_vat"] > HIGH_TOTAL_THRESHOLD:
            if "high_tender_total" not in summary["flags"]:
                summary["flags"].append("high_tender_total")

        summary["serious_flags"] = [
            flag for flag in summary["flags"]
            if flag in SERIOUS_FLAGS
        ]

        if summary["serious_flags"]:
            summary["status"] = "REVIEW_REQUIRED"
            summary["requires_manual_review"] = True
        else:
            summary["status"] = "OK"
            summary["requires_manual_review"] = False

        output_path = OUTPUT_DIR / f"{safe_filename(tender_id)}.json"

        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(
            f"{tender_id}: "
            f"items={summary['priced_items']} "
            f"total=R{summary['total_incl_vat']:,.2f} "
            f"status={summary['status']} "
            f"serious_flags={summary['serious_flags']} "
            f"file={output_path}"
        )


if __name__ == "__main__":
    main()
