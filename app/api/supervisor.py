from fastapi import APIRouter
from app.core.autonomous_supervisor import supervisor

router = APIRouter(
    prefix="/supervisor",
    tags=["supervisor"],
)


@router.get("/status")
def supervisor_status():
    return {
        "ok": True,
        "data": supervisor.read_status(),
    }
