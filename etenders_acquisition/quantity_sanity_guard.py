import json
import re
from statistics import median

from app.db.models import BOQItem
from app.db.session import SessionLocal


MAX_REASONABLE_QTY = 100000
MAX_REASONABLE_RATE = 1000000
MAX_REASONABLE_TOTAL = 50000000


def clean_number(value):
    if value is None:
        return None

    try:
        text = str(value)
        text = text.replace(",", "")
        text = re.sub(r"[^\d.\-]", "", text)

        if not text:
            return None

        return float(text)
    except Exception:
        return None


def suspicious_quantity(qty):
    if qty is None:
        return False

    if qty <= 0:
        return True

    if qty > MAX_REASONABLE_QTY:
        return True

    return False


def suspicious_rate(rate):
    if rate is None:
        return False

    if rate <= 0:
        return True

    if rate > MAX_REASONABLE_RATE:
        return True

    return False


def suspicious_total(total):
    if total is None:
        return False

    if total > MAX_REASONABLE_TOTAL:
        return True

    return False


def main():
    flagged = 0
    corrected = 0

    with SessionLocal() as session:
        items = session.query(BOQItem).all()

        quantities = []

        for item in items:
            qty = clean_number(item.quantity)

            if qty and qty > 0 and qty < MAX_REASONABLE_QTY:
                quantities.append(qty)

        median_qty = median(quantities) if quantities else 1

        for item in items:
            qty = clean_number(item.quantity)
            rate = clean_number(getattr(item, "rate", None))
            total = clean_number(getattr(item, "total_price", None))

            flags = []

            if suspicious_quantity(qty):
                flags.append("extreme_quantity")

            if suspicious_rate(rate):
                flags.append("extreme_rate")

            if suspicious_total(total):
                flags.append("extreme_total")

            if flags:
                flagged += 1

                raw = {}

                try:
                    raw = json.loads(item.raw_row_json or "{}")
                except Exception:
                    raw = {}

                raw["sanity_flags"] = flags

                if "extreme_quantity" in flags:
                    raw["original_quantity"] = qty
                    item.quantity = median_qty
                    corrected += 1

                item.raw_row_json = json.dumps(raw)

        session.commit()

    print(
        f"Quantity sanity guard complete | flagged={flagged} corrected={corrected}"
    )


if __name__ == "__main__":
    main()
