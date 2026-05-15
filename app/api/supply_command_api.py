from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query

from app.services.live_rfq_store import LiveRFQStore
from app.services.self_healing_harvester import (
    get_live_rfqs_for_api,
    harvester_cycle,
    self_healing_harvester,
)

router = APIRouter(prefix="/supply-command", tags=["Supply Command"])


@router.get("/health")
def supply_command_health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "supply_command",
        "message": "Supply Command API is running.",
    }


@router.get("/status")
def supply_command_status() -> Dict[str, Any]:
    live_data = LiveRFQStore.get_all()
    return {
        "ok": True,
        "service": "supply_command",
        "live_rfqs_count": live_data.get("count", 0),
        "live_rfqs_updated_at": live_data.get("updated_at"),
    }


@router.get("/live-rfqs")
def get_live_rfqs(
    limit: Optional[int] = Query(default=None, ge=1),
) -> Dict[str, Any]:
    data = get_live_rfqs_for_api()

    if limit is None:
        return data

    items = data.get("items", [])
    return {
        "updated_at": data.get("updated_at"),
        "count": min(len(items), limit),
        "items": items[:limit],
    }


@router.post("/live-rfqs/clear")
def clear_live_rfqs() -> Dict[str, Any]:
    return LiveRFQStore.clear()


@router.post("/live-rfqs/upsert")
def upsert_live_rfq(
    rfq: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    saved = LiveRFQStore.upsert_rfq(rfq)
    return {
        "ok": True,
        "message": "RFQ upserted into live store.",
        "item": saved,
    }


@router.post("/live-rfqs/bulk-upsert")
def bulk_upsert_live_rfqs(
    rfqs: List[Dict[str, Any]] = Body(...),
) -> Dict[str, Any]:
    written = 0
    for rfq in rfqs:
        LiveRFQStore.upsert_rfq(rfq)
        written += 1

    data = LiveRFQStore.get_all()
    return {
        "ok": True,
        "written": written,
        "live_count": data.get("count", 0),
        "updated_at": data.get("updated_at"),
    }


@router.post("/run")
def run_supply_command(
    portals: Optional[List[Dict[str, Any]]] = Body(default=[]),
) -> Dict[str, Any]:
    result = harvester_cycle(portals or [])
    return {
        "ok": True,
        "mode": "run_once",
        "summary": {
            "total_portals": result.get("total_portals", 0),
            "total_accepted": result.get("total_accepted", 0),
            "total_rejected": result.get("total_rejected", 0),
            "total_written": result.get("total_written", 0),
            "total_errors": result.get("total_errors", 0),
        },
        "results": result.get("results", []),
    }


@router.post("/test-run")
def test_run_supply_command() -> Dict[str, Any]:
    mock_portals = [
        {
            "portal_slug": "demo-portal",
            "portal_name": "Demo Portal",
            "mock_items": [
                {
                    "rfq_id": "demo-rfq-001",
                    "external_id": "demo-rfq-001",
                    "title": "Supply and Delivery of PPE",
                    "description": "Demo RFQ for PPE supply.",
                    "buyer_name": "Demo Municipality",
                    "province": "Free State",
                    "category": "ppe",
                    "submission_type": "email",
                    "briefing_required": False,
                    "published_at": "2026-03-20T08:00:00Z",
                    "closing_at": "2026-03-28T11:00:00Z",
                    "source_name": "Demo Portal",
                    "source_url": "https://example.com/rfq/demo-rfq-001",
                    "portal_slug": "demo-portal",
                    "contact_email": "supply@example.com",
                    "contact_phone": None,
                    "document_urls": [],
                    "status": "live",
                },
                {
                    "rfq_id": "demo-rfq-002",
                    "external_id": "demo-rfq-002",
                    "title": "Supply and Delivery of Stationery",
                    "description": "Demo RFQ for stationery supply.",
                    "buyer_name": "Demo Department",
                    "province": "Gauteng",
                    "category": "stationery_office",
                    "submission_type": "portal",
                    "briefing_required": False,
                    "published_at": "2026-03-20T09:00:00Z",
                    "closing_at": "2026-03-29T10:00:00Z",
                    "source_name": "Demo Portal",
                    "source_url": "https://example.com/rfq/demo-rfq-002",
                    "portal_slug": "demo-portal",
                    "contact_email": None,
                    "contact_phone": None,
                    "document_urls": [],
                    "status": "live",
                },
                {
                    "rfq_id": "demo-rfq-003",
                    "external_id": "demo-rfq-003",
                    "title": "Compulsory Briefing Demo RFQ",
                    "description": "This one should be rejected by filter.",
                    "buyer_name": "Demo Entity",
                    "province": "KwaZulu-Natal",
                    "category": "general",
                    "submission_type": "email",
                    "briefing_required": True,
                    "published_at": "2026-03-20T10:00:00Z",
                    "closing_at": "2026-03-30T12:00:00Z",
                    "source_name": "Demo Portal",
                    "source_url": "https://example.com/rfq/demo-rfq-003",
                    "portal_slug": "demo-portal",
                    "contact_email": "briefing@example.com",
                    "contact_phone": None,
                    "document_urls": [],
                    "status": "live",
                },
            ],
        }
    ]

    result = harvester_cycle(mock_portals)
    return {
        "ok": True,
        "mode": "test_run",
        "summary": {
            "total_portals": result.get("total_portals", 0),
            "total_accepted": result.get("total_accepted", 0),
            "total_rejected": result.get("total_rejected", 0),
            "total_written": result.get("total_written", 0),
            "total_errors": result.get("total_errors", 0),
        },
        "results": result.get("results", []),
        "live_rfqs": LiveRFQStore.get_all(),
    }


@router.post("/start")
def start_supply_command(
    portals: Optional[List[Dict[str, Any]]] = Body(default=[]),
    sleep_seconds: int = Query(default=60, ge=1),
) -> Dict[str, Any]:
    return {
        "ok": True,
        "message": (
            "Use the background worker or scheduler to run continuous harvesting. "
            "This endpoint returns the configuration only."
        ),
        "config": {
            "run_once": False,
            "sleep_seconds": sleep_seconds,
            "portals_supplied": len(portals or []),
        },
    }


@router.get("/demo")
def supply_command_demo() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "supply_command",
        "message": "Supply Command demo endpoint is available.",
        "available_routes": [
            "/supply-command/health",
            "/supply-command/status",
            "/supply-command/live-rfqs",
            "/supply-command/live-rfqs/clear",
            "/supply-command/live-rfqs/upsert",
            "/supply-command/live-rfqs/bulk-upsert",
            "/supply-command/run",
            "/supply-command/test-run",
            "/supply-command/start",
        ],
    }
