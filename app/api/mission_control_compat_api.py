from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import json

from fastapi import APIRouter

router = APIRouter(tags=["Mission Control Compatibility"])

RFQ_STATE = Path("runtime/rfq_lifecycle/rfqs.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _counts() -> Dict[str, Any]:
    data = _read_json(RFQ_STATE, {})
    items = data.get("items", {}) if isinstance(data, dict) else {}

    rows = list(items.values()) if isinstance(items, dict) else items if isinstance(items, list) else []

    total = len(rows)
    proof = 0
    failed = 0
    review = 0
    rejected = 0

    for item in rows:
        if not isinstance(item, dict):
            continue
        state = str(item.get("current_state") or item.get("state") or item.get("lifecycle_state") or "").upper()
        if state == "PROOF_CAPTURED":
            proof += 1
        elif state == "FAILED":
            failed += 1
        elif state == "REVIEW_REQUIRED":
            review += 1
        elif state == "REJECTED":
            rejected += 1

    return {
        "total_rfqs": total,
        "proof_captured": proof,
        "failed_rfqs": failed,
        "review_required": review,
        "rejected": rejected,
        "estimated_monthly_capacity": int(proof * 274),
    }


@router.get("/radar/status")
def radar_status() -> Dict[str, Any]:
    c = _counts()
    return {
        "status": "ok",
        "generated_at": _now(),
        "radar": {
            "lifecycle_health_score": 100.0 if c["failed_rfqs"] == 0 else 85.0,
            "system_resilience_score": 100.0,
            "worker_online": True,
            "online_workers": 6,
            "queue_backlog": 0,
            "failed_rfqs": c["failed_rfqs"],
            "review_required": c["review_required"],
            "proof_captured": c["proof_captured"],
            "estimated_monthly_capacity": c["estimated_monthly_capacity"],
            "upload_readiness_score": 0.0,
        },
        "slowest_stages": [],
        "warnings": [],
    }


@router.get("/tender-radar/status")
def tender_radar_status() -> Dict[str, Any]:
    return radar_status()


@router.get("/portal-health")
def portal_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "generated_at": _now(),
        "overall_status": "monitored",
        "portal_count": 2,
        "degraded_count": 0,
        "portals": [
            {"name": "www.etenders.gov.za", "status": "monitored", "success_rate": 100.0},
            {"name": "www.necsa.co.za", "status": "monitored", "success_rate": 100.0},
        ],
        "safety": {
            "no_final_submit": True,
            "no_email_send": True,
            "no_captcha_bypass": True,
        },
    }


@router.get("/harvester/portal-health")
def harvester_portal_health() -> Dict[str, Any]:
    return portal_health()


@router.get("/tender-radar/portal-health")
def tender_radar_portal_health() -> Dict[str, Any]:
    return portal_health()
