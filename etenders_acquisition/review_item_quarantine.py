#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
PRICING_SUMMARIES_DIR = RUNTIME_DIR / "pricing_summaries"

QUARANTINE_DIR = RUNTIME_DIR / "review_quarantine"
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

QUARANTINE_FILE = QUARANTINE_DIR / "review_item_quarantine.json"
QUARANTINE_SUMMARY_FILE = QUARANTINE_DIR / "review_item_quarantine_summary.json"

HIGH_TENDER_TOTAL_THRESHOLD = 50_000_000


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def money(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def main():
    pricing_files = sorted(PRICING_SUMMARIES_DIR.glob("*.json"))

    quarantined_tenders = []
    reviewed_tenders = []

    for pricing_file in pricing_files:
        data = load_json(pricing_file)

        if not isinstance(data, dict):
            continue

        tender_id = data.get("tender_id") or pricing_file.stem
        total_incl_vat = money(data.get("total_incl_vat"))
        total_excl_vat = money(data.get("total_excl_vat"))
        priced_items = int(data.get("priced_items") or 0)

        flags = data.get("flags") or []
        serious_flags = data.get("serious_flags") or []
        status = data.get("status", "UNKNOWN")
        requires_manual_review = bool(data.get("requires_manual_review"))

        quarantine_reasons = []

        if status == "REVIEW_REQUIRED":
            quarantine_reasons.append("status_review_required")

        if requires_manual_review:
            quarantine_reasons.append("requires_manual_review")

        if total_incl_vat >= HIGH_TENDER_TOTAL_THRESHOLD:
            quarantine_reasons.append("high_tender_total")

        for flag in serious_flags:
            if flag not in quarantine_reasons:
                quarantine_reasons.append(flag)

        tender_record = {
            "tender_id": tender_id,
            "source_file": str(pricing_file),
            "priced_items": priced_items,
            "total_excl_vat": total_excl_vat,
            "total_incl_vat": total_incl_vat,
            "status": status,
            "flags": flags,
            "serious_flags": serious_flags,
            "requires_manual_review": requires_manual_review,
            "quarantine_reasons": quarantine_reasons,
        }

        reviewed_tenders.append(tender_record)

        if quarantine_reasons:
            quarantined_tenders.append(tender_record)

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "quarantine_type": "tender_level",
        "quarantined_tenders": quarantined_tenders,
    }

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pricing_summary_files_scanned": len(pricing_files),
        "tenders_reviewed": len(reviewed_tenders),
        "quarantined_tenders": len(quarantined_tenders),
        "quarantined_tender_ids": [
            t["tender_id"] for t in quarantined_tenders
        ],
    }

    write_json(QUARANTINE_FILE, output)
    write_json(QUARANTINE_SUMMARY_FILE, summary)

    print("Review quarantine complete")
    print(f"Pricing summaries scanned: {len(pricing_files)}")
    print(f"Tenders reviewed: {len(reviewed_tenders)}")
    print(f"Quarantined tenders: {len(quarantined_tenders)}")

    for tender in quarantined_tenders:
        print(
            f"{tender['tender_id']}: "
            f"total=R{tender['total_incl_vat']:,.2f} "
            f"status={tender['status']} "
            f"reasons={tender['quarantine_reasons']}"
        )

    print(f"Summary file: {QUARANTINE_SUMMARY_FILE}")
    print(f"Quarantine file: {QUARANTINE_FILE}")


if __name__ == "__main__":
    main()
