import json
import time
from collections import defaultdict

from app.db.models import BOQItem
from app.db.session import SessionLocal


MAX_ITEMS = 10000

DEFAULT_RATES = {
    "supply": 2500.0,
    "deliver": 850.0,
    "delivery": 850.0,
    "install": 1200.0,
    "installation": 1200.0,
    "repair": 950.0,
    "replace": 1100.0,
    "construct": 2500.0,
    "excavate": 1800.0,
    "paint": 650.0,
    "test": 450.0,
    "commission": 750.0,
    "maintain": 900.0,
    "service": 900.0,
}

FALLBACK_RATE = 1000.0
MARKUP = 0.25
VAT = 0.15


def is_priceable(item):
    return '"priceable": true' in (item.raw_row_json or "")


def pick_rate(description):
    desc = (description or "").lower()

    for keyword, rate in DEFAULT_RATES.items():
        if keyword in desc:
            return rate, keyword

    return FALLBACK_RATE, "fallback"


def quantity(item):
    if item.quantity and item.quantity > 0:
        return float(item.quantity)

    return 1.0


def main():
    priced = 0
    totals = defaultdict(float)

    with SessionLocal() as session:
        items = session.query(BOQItem).limit(MAX_ITEMS).all()

        for item in items:
            if not is_priceable(item):
                continue

            qty = quantity(item)
            rate, basis = pick_rate(item.description)
            subtotal = qty * rate
            markup_amount = subtotal * MARKUP
            total_excl_vat = subtotal + markup_amount
            vat_amount = total_excl_vat * VAT
            total_incl_vat = total_excl_vat + vat_amount

            raw = json.loads(item.raw_row_json)

            raw["pricing"] = {
                "quantity": qty,
                "rate": rate,
                "rate_basis": basis,
                "subtotal": subtotal,
                "markup_percent": MARKUP,
                "markup_amount": markup_amount,
                "total_excl_vat": total_excl_vat,
                "vat_percent": VAT,
                "vat_amount": vat_amount,
                "total_incl_vat": total_incl_vat,
                "priced_at": time.time(),
                "pricing_mode": "rule_based_default",
            }

            item.raw_row_json = json.dumps(raw, ensure_ascii=False, default=str)

            totals[item.tender_id] += total_incl_vat
            priced += 1

        session.commit()

    print(f"Pricing engine complete | priced_items={priced}")

    print("\nTender totals:")
    for tender_id, total in sorted(totals.items()):
        print(f"{tender_id}: R{total:,.2f}")


if __name__ == "__main__":
    main()
