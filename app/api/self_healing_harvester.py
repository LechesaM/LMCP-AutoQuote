from fastapi import APIRouter, Query

from app.services.self_healing_harvester import self_healing_harvester

router = APIRouter(
    prefix="/self-healing-harvester",
    tags=["self-healing-harvester"],
)


@router.get("/status")
def self_healing_status():
    return {
        "ok": True,
        "data": self_healing_harvester.get_status(),
    }


@router.get("/history")
def self_healing_history(limit: int = Query(default=50, ge=1, le=500)):
    return {
        "ok": True,
        "data": self_healing_harvester.get_history(limit=limit),
    }
