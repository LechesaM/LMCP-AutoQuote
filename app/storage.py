from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime

# In-memory storage (safe for prototype)
_OPPORTUNITIES: List[Dict[str, Any]] = []


def _extract_release_id(release: Dict[str, Any]) -> str:
    return (
        release.get("ocid")
        or release.get("id")
        or f"unknown-{len(_OPPORTUNITIES)+1}"
    )


def _extract_title(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return tender.get("title") or tender.get("description") or "Untitled"


def _extract_buyer(release: Dict[str, Any]) -> str:
    buyer = release.get("buyer") or {}
    return buyer.get("name") or "Unknown Buyer"


def _extract_published_date(release: Dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    return (
        tender.get("datePublished")
        or release.get("date")
        or datetime.utcnow().isoformat()
    )


# ------------------------------------------------------------------
# PRIMARY STORAGE FUNCTION (used by system)
# ------------------------------------------------------------------
def store_opportunities(releases: List[Dict[str, Any]]) -> int:
    """
    Store filtered opportunities.
    Returns number stored.
    """
    global _OPPORTUNITIES

    before = len(_OPPORTUNITIES)

    for r in releases:
        record = {
            "release_id": _extract_release_id(r),
            "title": _extract_title(r),
            "buyer": _extract_buyer(r),
            "published_date": _extract_published_date(r),
            "raw": r,
        }

        # prevent duplicates
        if not any(x["release_id"] == record["release_id"] for x in _OPPORTUNITIES):
            _OPPORTUNITIES.append(record)

    return len(_OPPORTUNITIES) - before


# ------------------------------------------------------------------
# 🔥 CRITICAL COMPATIBILITY FIX
# tasks.py expects save_opportunities
# ------------------------------------------------------------------
def save_opportunities(opportunities: List[Dict[str, Any]]) -> int:
    """
    Backwards-compatible alias.
    DO NOT REMOVE — required by tasks.py
    """
    return store_opportunities(opportunities)


# ------------------------------------------------------------------
# READ HELPERS
# ------------------------------------------------------------------
def list_opportunities() -> List[Dict[str, Any]]:
    return list(_OPPORTUNITIES)


def clear_opportunities() -> None:
    _OPPORTUNITIES.clear()
