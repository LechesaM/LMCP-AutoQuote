from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header

from app.services.security_guard_service import (
    require_operator_pin,
    security_status,
    verify_operator_pin,
)

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/status")
def get_security_status() -> Dict[str, Any]:
    return security_status()


@router.post("/verify-pin")
def verify_pin(x_operator_pin: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    return verify_operator_pin(x_operator_pin or "")


@router.post("/protected-test")
def protected_test(auth: Dict[str, Any] = require_operator_pin) -> Dict[str, Any]:
    return {
        "status": "ok",
        "message": "Protected endpoint access granted.",
        "auth": auth,
    }
