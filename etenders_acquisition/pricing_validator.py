import json
from collections import defaultdict

from app.db.models import BOQItem
from app.db.session import SessionLocal


HIGH_TOTAL_THRESHOLD = 50_000_000
HIGH_ITEM_THRESHOLD = 1_000_000
HIGH_QTY_THRESHOLD = 10_000


def load_raw(item):
    try:
        return json.loads(item.raw_row_json or "{}")
    except Exception:
        return {}


def main():
    tender_totals = defaultdict(float)
    tender_items = defaultdict(int)
    tender_flags = defaultdict(list)

    with SessionLocal() as session:
        items = session.query(BOQItem).all()

        for item in items:
            raw = load_raw(item)
            pricing = raw.get("pricing")

            if not pricing:
                continue

            tender_id = item.tender_id or "UNKNOWN"
            total = float(pricing.get("total_incl_vat") or 0)
            qty = float(pricing.get("quantity") or 0)
            basis = pricing.get("rate_basis")

            tender_totals[tender_id] += total
            tender_items[tender_id] += 1

            flags = []

            if total > HIGH_ITEM_THRESHOLD:
                flags.append("high_item_total")

            if qty > HIGH_QTY_THRESHOLD:
                flags.append("extreme_quantity")

            if basis == "fallback":
                flags.append("fallback_rate_used")

            if flags:
                raw["pricing_validation"] = {
                    "status": "review_required",
                    "flags": flags,
                }
                item.raw_row_json = json.dumps(raw, ensure_ascii=False, default=str)

        for tender_id, total in tender_totals.items():
            if total > HIGH_TOTAL_THRESHOLD:
                tender_flags[tender_id].append("high_tender_total")

        session.commit()

    print("Pricing validation complete")

    print("\nTender validation summary:")
    for tender_id, total in sorted(tender_totals.items()):
        flags = tender_flags.get(tender_id, [])
        status = "REVIEW_REQUIRED" if flags else "OK"
        print(
            f"{tender_id}: "
            f"items={tender_items[tender_id]} "
            f"total=R{total:,.2f} "
            f"status={status} "
            f"flags={flags}"
        )


if __name__ == "__main__":
    main()
