from fastapi import APIRouter

from app.core.self_check import run_self_check

router = APIRouter(prefix="/system-guard", tags=["System Guard"])


@router.get("/status")
def system_guard_status():
    return run_self_check()
