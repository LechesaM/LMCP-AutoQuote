from __future__ import annotations

import re
from typing import Optional


SUPPLY_KEYWORDS = [
    "supply",
    "supply and delivery",
    "supply & delivery",
    "deliver",
    "delivery",
    "supply, deliver",
    "supply and install",  # optional inclusion
    "supply of",
    "appointment of a service provider for supply",
    "procurement of",
    "purchase of",
    "provision of",
]

EXCLUDE_KEYWORDS = [
    "construction",
    "building works",
    "civil works",
    "maintenance of roads",
    "repair works",
    "professional services",
    "consulting services",
    "security services",
    "cleaning services",
    "training services",
    "lease of office space",
    "property management",
]


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def is_supply_delivery(title: Optional[str], description: Optional[str]) -> bool:
    text = normalize_text(f"{title or ''} {description or ''}")

    if not text:
        return False

    has_supply_signal = any(keyword in text for keyword in SUPPLY_KEYWORDS)
    has_excluded_signal = any(keyword in text for keyword in EXCLUDE_KEYWORDS)

    if has_supply_signal and not has_excluded_signal:
        return True

    return False
