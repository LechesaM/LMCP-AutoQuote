from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set, Tuple


def safe_str(value: Any) -> str:
    """
    Safely convert any value to a stripped string.
    """
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(value: Any) -> str:
    """
    Normalize text for duplicate comparison.
    """
    text = safe_str(value).lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()


def similarity(a: str, b: str) -> float:
    """
    Return a similarity ratio between two strings.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def tender_key(tender: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Exact-match duplicate key using normalized title, issuer, and deadline.
    """
    title = normalize_text(tender.get("title"))
    issuer = normalize_text(tender.get("issuer"))
    deadline = safe_str(tender.get("deadline"))
    return (title, issuer, deadline)


def is_probable_duplicate(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """
    Check if two tenders are probably duplicates.
    """
    a_title = normalize_text(a.get("title"))
    b_title = normalize_text(b.get("title"))

    a_issuer = normalize_text(a.get("issuer"))
    b_issuer = normalize_text(b.get("issuer"))

    a_deadline = safe_str(a.get("deadline"))
    b_deadline = safe_str(b.get("deadline"))

    # Exact match
    if a_title and b_title and a_title == b_title and a_issuer == b_issuer and a_deadline == b_deadline:
        return True

    # Fuzzy match
    title_match = similarity(a_title, b_title) >= 0.92
    issuer_match = (not a_issuer and not b_issuer) or similarity(a_issuer, b_issuer) >= 0.90
    deadline_match = a_deadline == b_deadline and a_deadline != ""

    return title_match and issuer_match and deadline_match


def deduplicate_tenders(tenders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate tenders from a list.
    """
    unique: List[Dict[str, Any]] = []
    seen_exact: Set[Tuple[str, str, str]] = set()

    for tender in tenders:
        key = tender_key(tender)

        if key in seen_exact:
            continue

        duplicate_found = False
        for existing in unique:
            if is_probable_duplicate(existing, tender):
                duplicate_found = True
                break

        if duplicate_found:
            continue

        seen_exact.add(key)
        unique.append(tender)

    return unique
