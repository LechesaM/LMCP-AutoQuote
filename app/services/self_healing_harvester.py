import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.live_rfq_store import LiveRFQStore

logger = logging.getLogger(__name__)

PAUSE_FILE = os.getenv("HARVESTER_PAUSE_FILE", "runtime/harvester.paused")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_harvester_paused() -> bool:
    return os.path.exists(PAUSE_FILE)


def rfq_is_eligible(rfq: Dict[str, Any]) -> bool:
    """
    LMCP harvesting rule:
    - keep email-only submissions
    - keep portal-only submissions
    - reject anything with compulsory briefing
    """
    submission_type = str(rfq.get("submission_type") or "").strip().lower()
    briefing_required = bool(rfq.get("briefing_required", False))

    if submission_type not in {"email", "portal"}:
        return False

    if briefing_required:
        return False

    return True


def normalize_harvested_rfq(
    raw_rfq: Dict[str, Any],
    portal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Normalizes a harvested RFQ into the structure expected by LiveRFQStore.
    """
    portal = portal or {}

    return {
        "rfq_id": raw_rfq.get("rfq_id"),
        "external_id": raw_rfq.get("external_id"),
        "title": raw_rfq.get("title"),
        "description": raw_rfq.get("description"),
        "buyer_name": raw_rfq.get("buyer_name"),
        "province": raw_rfq.get("province"),
        "category": raw_rfq.get("category"),
        "submission_type": raw_rfq.get("submission_type"),
        "briefing_required": raw_rfq.get("briefing_required", False),
        "published_at": raw_rfq.get("published_at"),
        "closing_at": raw_rfq.get("closing_at"),
        "source_name": raw_rfq.get("source_name") or portal.get("portal_name") or portal.get("portal_slug"),
        "source_url": raw_rfq.get("source_url"),
        "portal_slug": raw_rfq.get("portal_slug") or portal.get("portal_slug"),
        "contact_email": raw_rfq.get("contact_email"),
        "contact_phone": raw_rfq.get("contact_phone"),
        "document_urls": raw_rfq.get("document_urls") or [],
        "raw": raw_rfq,
        "status": raw_rfq.get("status", "live"),
        "created_at": raw_rfq.get("created_at") or _now_iso(),
    }


def _write_live_rfq_if_eligible(rfq: Dict[str, Any]) -> bool:
    """
    Writes RFQ to live store only if it meets LMCP eligibility rules.
    Returns True if written, otherwise False.
    """
    if not rfq_is_eligible(rfq):
        return False

    LiveRFQStore.upsert_rfq(rfq)
    return True


def process_portal_results(
    portal: Dict[str, Any],
    harvested_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Process all harvested RFQs for a portal:
    - normalize
    - filter
    - immediately write accepted RFQs to runtime/live_rfqs.json
    """
    accepted = 0
    rejected = 0
    written = 0
    errors = 0
    accepted_rfqs: List[Dict[str, Any]] = []

    for raw_rfq in harvested_items:
        try:
            rfq = normalize_harvested_rfq(raw_rfq, portal)

            if not rfq_is_eligible(rfq):
                rejected += 1
                continue

            accepted += 1
            accepted_rfqs.append(rfq)

            try:
                LiveRFQStore.upsert_rfq(rfq)
                written += 1
                logger.info(
                    "Live RFQ stored | portal=%s | title=%s",
                    portal.get("portal_slug"),
                    rfq.get("title"),
                )
            except Exception as exc:
                errors += 1
                logger.exception(
                    "Failed to auto-write RFQ to live store | portal=%s | error=%s",
                    portal.get("portal_slug"),
                    exc,
                )

        except Exception as exc:
            errors += 1
            logger.exception(
                "Failed processing RFQ | portal=%s | error=%s",
                portal.get("portal_slug"),
                exc,
            )

    return {
        "portal_slug": portal.get("portal_slug"),
        "portal_name": portal.get("portal_name"),
        "accepted": accepted,
        "rejected": rejected,
        "written": written,
        "errors": errors,
        "accepted_rfqs": accepted_rfqs,
    }


def harvest_portal(portal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Safe placeholder harvester.

    Current behavior:
    - if portal contains 'mock_items', return them
    - otherwise return empty list

    Replace this later with your real scraper/extractor logic.
    """
    mock_items = portal.get("mock_items")
    if isinstance(mock_items, list):
        return mock_items

    return []


def harvester_cycle(portals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Runs one full harvest cycle across all portals.
    """
    results: List[Dict[str, Any]] = []
    total_portals = len(portals)
    total_accepted = 0
    total_rejected = 0
    total_written = 0
    total_errors = 0

    for portal in portals:
        if is_harvester_paused():
            logger.info("Harvester paused via %s. Sleeping 30 seconds.", PAUSE_FILE)
            time.sleep(30)
            continue

        portal_slug = portal.get("portal_slug")
        logger.info("Starting harvest for portal=%s", portal_slug)

        try:
            harvested_items = harvest_portal(portal)
            portal_result = process_portal_results(portal, harvested_items)

            total_accepted += portal_result["accepted"]
            total_rejected += portal_result["rejected"]
            total_written += portal_result["written"]
            total_errors += portal_result["errors"]

            results.append(
                {
                    "portal_slug": portal_result["portal_slug"],
                    "portal_name": portal_result["portal_name"],
                    "accepted": portal_result["accepted"],
                    "rejected": portal_result["rejected"],
                    "written": portal_result["written"],
                    "errors": portal_result["errors"],
                }
            )

            logger.info(
                "Completed harvest | portal=%s | accepted=%s | rejected=%s | written=%s | errors=%s",
                portal_slug,
                portal_result["accepted"],
                portal_result["rejected"],
                portal_result["written"],
                portal_result["errors"],
            )

        except Exception as exc:
            total_errors += 1
            logger.exception("Harvester failed for portal=%s | error=%s", portal_slug, exc)
            results.append(
                {
                    "portal_slug": portal_slug,
                    "portal_name": portal.get("portal_name"),
                    "accepted": 0,
                    "rejected": 0,
                    "written": 0,
                    "errors": 1,
                    "error": str(exc),
                }
            )

    return {
        "ok": True,
        "total_portals": total_portals,
        "total_accepted": total_accepted,
        "total_rejected": total_rejected,
        "total_written": total_written,
        "total_errors": total_errors,
        "results": results,
    }


def self_healing_harvester(
    portals: Optional[List[Dict[str, Any]]] = None,
    sleep_seconds: int = 60,
    run_once: bool = True,
) -> Dict[str, Any]:
    """
    Main harvester entrypoint.

    Modes:
    - run_once=True: runs a single harvest cycle and returns the result
    - run_once=False: loops forever with pause-file support

    This function is safe for API wiring and background worker usage.
    """
    portals = portals or []

    if run_once:
        return harvester_cycle(portals)

    last_result: Dict[str, Any] = {
        "ok": True,
        "message": "Harvester started in continuous mode.",
        "results": [],
    }

    while True:
        try:
            if is_harvester_paused():
                logger.info("Harvester paused via %s. Sleeping 30 seconds.", PAUSE_FILE)
                time.sleep(30)
                continue

            last_result = harvester_cycle(portals)
        except Exception as exc:
            logger.exception("Continuous harvester cycle failed: %s", exc)
            last_result = {
                "ok": False,
                "error": str(exc),
                "results": [],
            }

        time.sleep(max(1, sleep_seconds))


def get_live_rfqs_for_api() -> Dict[str, Any]:
    """
    Returns live RFQs from runtime store.
    Used by Supply Command API.
    """
    from app.services.live_rfq_store import LiveRFQStore
    return LiveRFQStore.get_all()


__all__ = [
    "is_harvester_paused",
    "rfq_is_eligible",
    "normalize_harvested_rfq",
    "process_portal_results",
    "harvest_portal",
    "harvester_cycle",
    "self_healing_harvester",
    "run_harvester",
    "get_live_rfqs_for_api",   # ✅ ADD THIS
]

def run_harvester(portals: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Compatibility wrapper for Supply Command and existing API endpoints.

    This ensures older parts of the system still work while using the new live RFQ system.
    """
    result = harvester_cycle(portals or [])

    # 🔁 IMPORTANT: normalize output for API expectations
    return {
        "ok": True,
        "rfqs": result.get("results", []),   # keeps old structure alive
        "summary": {
            "total_portals": result.get("total_portals"),
            "accepted": result.get("total_accepted"),
            "rejected": result.get("total_rejected"),
            "written": result.get("total_written"),
            "errors": result.get("total_errors"),
        },
        "raw": result,
    }
