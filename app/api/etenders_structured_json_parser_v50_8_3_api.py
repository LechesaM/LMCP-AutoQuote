"""
LMCP V50.8.3 API - eTenders Structured JSON Row Parser

Drop-in:
    app/api/etenders_structured_json_parser_v50_8_3_api.py
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_structured_json_parser_v50_8_3_service import (
    get_v50_8_3_status,
    parse_etenders_structured_json,
)

router = APIRouter(prefix="/v50-8-3-etenders-json", tags=["V50.8.3 eTenders Structured JSON Parser"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_8_3_status()


@router.post("/parse")
def parse(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return parse_etenders_structured_json(payload or {})
