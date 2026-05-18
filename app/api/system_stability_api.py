from fastapi import APIRouter
from app.services.self_healing_service import watchdog_status
from app.services.retry_engine_service import get_retry_queue

router = APIRouter(prefix="/system-stability", tags=["system-stability"])

@router.get("/watchdog")
def watchdog():
    return watchdog_status()

@router.get("/retry-queue")
def retry_queue():
    return {"status": "ok", "queue": get_retry_queue()}
