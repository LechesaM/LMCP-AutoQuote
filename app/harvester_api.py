from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.cycle_state_store import load_cycle_state
from app.services.portal_registry import (
    get_active_procurement_portals,
    get_active_supply_delivery_portals,
    get_registry_summary,
)

router = APIRouter(prefix="/harvester", tags=["harvester"])


@router.get("/registry")
def harvester_registry() -> Dict[str, Any]:
    portals = get_active_procurement_portals()
    return {
        "ok": True,
        "message": "Harvester registry loaded successfully.",
        "data": {
            "summary": get_registry_summary(),
            "total_portals": len(portals),
            "portals": portals,
        },
    }


@router.get("/registry/supply-delivery")
def harvester_supply_delivery_registry() -> Dict[str, Any]:
    portals = get_active_supply_delivery_portals()
    return {
        "ok": True,
        "message": "Supply-and-delivery registry loaded successfully.",
        "data": {
            "total_portals": len(portals),
            "portals": portals,
        },
    }


@router.get("/cycle-state")
def harvester_cycle_state() -> Dict[str, Any]:
    state = load_cycle_state()
    return {
        "ok": True,
        "message": "Cycle state loaded successfully.",
        "data": state,
    }


@router.get("/status")
def harvester_status() -> Dict[str, Any]:
    portals = get_active_procurement_portals()
    state = load_cycle_state()

    return {
        "ok": True,
        "message": "Harvester status loaded successfully.",
        "data": {
            "registry_summary": get_registry_summary(),
            "active_portals": len(portals),
            "cycle_number": state.get("cycle_number", 0),
            "last_cycle_at": state.get("last_cycle_at"),
            "last_selected_count": state.get("last_selected_count", 0),
            "last_selected_sources": state.get("last_selected_sources", []),
        },
    }
