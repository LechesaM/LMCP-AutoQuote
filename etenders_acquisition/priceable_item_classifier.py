import re
import time

from app.db.models import BOQItem
from app.db.session import SessionLocal


MAX_ITEMS = 10000


NON_PRICEABLE_PATTERNS = [
    r"annexure",
    r"note:",
    r"prices must be",
    r"department reserves",
    r"for purposes of this tender",
    r"schools as listed",
    r"specifications",
    r"bid document",
    r"tender document",
    r"page ",
    r"signature",
    r"company name",
    r"total for",
    r"grand total",
    r"subtotal",
]


PRICEABLE_HINTS = [
    "supply",
    "deliver",
    "delivery",
    "install",
    "installation",
    "repair",
    "replace",
    "provide",
    "construct",
    "excavate",
    "paint",
    "fix",
    "remove",
    "test",
    "commission",
    "maintain",
    "service",
]


def is_priceable(item):
    desc = (item.description or "").strip()
    desc_lower = desc.lower()

    if len(desc) < 15:
        return False

    for pattern in NON_PRICEABLE_PATTERNS:
        if re.search(pattern, desc_lower):
            return False

    if item.quantity is not None and item.quantity > 0:
        return True

    if item.unit:
        return True

    return any(hint in desc_lower for hint in PRICEABLE_HINTS)


def main():
    checked = 0
    priceable = 0
    non_priceable = 0

    with SessionLocal() as session:
        items = session.query(BOQItem).limit(MAX_ITEMS).all()

        for item in items:
            checked += 1

            raw = item.raw_row_json or "{}"

            if is_priceable(item):
                item.raw_row_json = raw.replace(
                    '"priceable": false',
                    '"priceable": true'
                ) if '"priceable": false' in raw else raw[:-1] + ', "priceable": true}'
                priceable += 1
            else:
                item.raw_row_json = raw.replace(
                    '"priceable": true',
                    '"priceable": false'
                ) if '"priceable": true' in raw else raw[:-1] + ', "priceable": false}'
                non_priceable += 1

        session.commit()

    print(
        "Priceable item classifier complete | "
        f"checked={checked} "
        f"priceable={priceable} "
        f"non_priceable={non_priceable}"
    )


if __name__ == "__main__":
    main()
