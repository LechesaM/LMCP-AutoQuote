from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.mission_control_ai_scoring_service import build_mission_control_ai_scoring

router = APIRouter(prefix="/mission-control", tags=["Mission Control"])


@router.get("/ai-scoring", operation_id="mission_control_ai_scoring")
def mission_control_ai_scoring() -> Dict[str, Any]:
    return build_mission_control_ai_scoring()

