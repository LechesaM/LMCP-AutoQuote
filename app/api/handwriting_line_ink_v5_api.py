from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.handwriting_line_ink_v5 import (
    build_line_ink_assets_v5,
    example_payload,
    get_line_ink_status,
    normalize_line_ink_job_v7,
    resolve_line_asset_v5,
    resolve_line_asset_v7,
)

router = APIRouter(prefix="/handwriting-line-ink-v5", tags=["Handwriting Line Ink V5"])


def _coerce_int(value: Any) -> Any:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"status": "error", "message": f"Invalid integer: {value}"})


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_labels(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, list):
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "labels must be a list of strings when provided"},
        )
    return value


@router.get("/status")
def handwriting_line_ink_status() -> Dict[str, Any]:
    return get_line_ink_status()


@router.get("/example-payload")
def handwriting_line_ink_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": example_payload(),
    }


@router.post("/build-assets")
def handwriting_line_ink_build_assets(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return build_line_ink_assets_v5(
            job_id=str(payload.get("job_id") or "REAL-HANDWRITING"),
            labels=_coerce_labels(payload.get("labels")),
            normalize_v7=_coerce_bool(payload.get("normalize_v7"), True),
            target_density=float(payload.get("target_density", 0.075)),
            darken_factor=float(payload.get("darken_factor", 0.78)),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"status": "error", "message": str(exc)})


@router.post("/normalize-job")
def handwriting_line_ink_normalize_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return normalize_line_ink_job_v7(
            job_id=str(payload.get("job_id") or "REAL-HANDWRITING"),
            target_density=float(payload.get("target_density", 0.065)),
            darken_factor=float(payload.get("darken_factor", 0.82)),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"status": "error", "message": str(exc)})


@router.post("/resolve-asset")
def handwriting_line_ink_resolve_asset(payload: Dict[str, Any]) -> Dict[str, Any]:
    line_index = _coerce_int(payload.get("line_index"))
    prefer_normalized = _coerce_bool(payload.get("prefer_normalized"), True)
    job_id = str(payload.get("job_id") or "REAL-HANDWRITING")
    text = str(payload.get("text") or "")

    resolved = resolve_line_asset_v5(
        job_id=job_id,
        text=text,
        line_index=line_index,
        prefer_normalized=prefer_normalized,
    )

    if not resolved and line_index is not None:
        resolved = resolve_line_asset_v7(job_id=job_id, line_index=line_index)

    if not resolved:
        return {
            "status": "error",
            "message": "No matching line asset found.",
            "job_id": job_id,
            "text": text,
            "line_index": line_index,
        }

    return {
        "status": "ok",
        "job_id": job_id,
        "text": text,
        "line_index": line_index,
        "prefer_normalized": prefer_normalized,
        "path": str(resolved),
    }
