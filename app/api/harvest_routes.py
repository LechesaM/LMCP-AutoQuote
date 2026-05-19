from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.harvest.controlled_harvester import ControlledHarvester
from app.harvest.operator_capacity import capacity_status
from app.harvest.seed_sources import load_seed_sources
from app.harvest.source_health import get_source_health
from app.harvest.source_registry import SourceRegistry, load_source_registry
from app.harvest.source_tiers import HarvestTier


router = APIRouter(prefix="/harvest", tags=["Harvest"])


def _registry() -> SourceRegistry:
    return load_source_registry()


def _harvester() -> ControlledHarvester:
    return ControlledHarvester(registry=_registry())


def _serialize_sources(sources) -> List[Dict[str, Any]]:
    return [source.to_jsonable_dict() for source in sources]


@router.get("/sources")
def list_sources(tier: str | None = None) -> Dict[str, Any]:
    registry = _registry()
    if tier:
        sources = registry.list_sources_by_tier(HarvestTier.from_value(tier))
    else:
        sources = registry.list_sources()
    return {"status": "ok", "sources": _serialize_sources(sources)}


@router.post("/sources")
def add_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        record = _registry().add_source(payload)
        return {"status": "ok", "source": record.to_jsonable_dict()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sources/import")
def import_sources(payload: Dict[str, Any]) -> Dict[str, Any]:
    registry = _registry()
    sources = payload.get("sources") if isinstance(payload, dict) else []
    if not isinstance(sources, list):
        sources = []
    return {"status": "ok", **registry.bulk_import_sources(sources)}


@router.post("/run/source/{source_id}")
async def run_source(source_id: str) -> Dict[str, Any]:
    return await _harvester().harvest_source(source_id)


@router.post("/run/tier/{tier}")
async def run_tier(tier: str) -> Dict[str, Any]:
    resolved = HarvestTier.from_value(tier)
    return await _harvester().harvest_tier(resolved)


@router.get("/runs")
def list_runs(limit: int = 100) -> Dict[str, Any]:
    return {"status": "ok", "runs": _harvester().list_runs(limit=limit)}


@router.get("/opportunities")
def list_opportunities(limit: int = 100) -> Dict[str, Any]:
    return {"status": "ok", "opportunities": _harvester().list_opportunities(limit=limit)}


@router.get("/source-health")
def source_health(source_id: str | None = None) -> Dict[str, Any]:
    if source_id:
        return {"status": "ok", "health": get_source_health(source_id).to_jsonable_dict()}
    registry = _registry()
    return {"status": "ok", "health": [get_source_health(source.id).to_jsonable_dict() for source in registry.list_sources()]}


@router.get("/operator-capacity")
def operator_capacity(already_promoted_count: int = 0) -> Dict[str, Any]:
    snapshot = capacity_status(already_promoted_count=already_promoted_count)
    return {"status": "ok", "capacity": snapshot.__dict__}


@router.get("/promotion-summary")
def promotion_summary(limit: int = 100) -> Dict[str, Any]:
    opportunities = _harvester().list_opportunities(limit=limit)
    promoted = [item for item in opportunities if bool(item.get("promoted_for_review"))]
    suppressed = [item for item in opportunities if not bool(item.get("promoted_for_review"))]
    return {
        "status": "ok",
        "total": len(opportunities),
        "promoted": len(promoted),
        "suppressed": len(suppressed),
        "promoted_items": promoted,
        "suppressed_items": suppressed,
    }
