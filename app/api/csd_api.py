from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.csd_refresh_service import CSDRefreshError, CSDRefreshService

router = APIRouter(prefix="/csd", tags=["CSD"])


@router.get("/refresh")
def refresh_csd_report(
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None, ge=2020, le=2100),
) -> Dict[str, Any]:
    try:
        return CSDRefreshService.refresh_csd_with_fallback(month=month, year=year)
    except CSDRefreshError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CSD refresh failed: {exc}")


@router.get("/refresh/current")
def refresh_current_csd_report() -> Dict[str, Any]:
    now = datetime.now()
    try:
        return CSDRefreshService.refresh_csd_with_fallback(month=now.month, year=now.year)
    except CSDRefreshError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CSD refresh failed: {exc}")
