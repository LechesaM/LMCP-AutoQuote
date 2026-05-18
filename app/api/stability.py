from fastapi import APIRouter
from app.core.stability_guard import guard
from app.services.disk_safety_guard import disk_guard
from app.services.portal_isolation import portal_isolation_manager

router = APIRouter(prefix="/system", tags=["stability"])


@router.get("/status")
def stability_status():
    return {
        "ok": True,
        "data": guard.read_status(),
    }


@router.get("/heartbeat")
def heartbeat():
    return {
        "ok": True,
        "data": guard.heartbeat("api_manual_probe"),
    }


@router.get("/disk-safety")
def disk_safety_status():
    return disk_guard.snapshot()
   

@router.post("/disk-safety/check")
def run_disk_safety_check():
    return disk_guard.check_once()


@router.get("/portal-isolation")
def portal_isolation_status():
    return portal_isolation_manager.snapshot()


@router.post("/portal-isolation/{portal_slug}/unisolate")
def unisolate_portal(portal_slug: str):
    return portal_isolation_manager.unisolate(portal_slug)
