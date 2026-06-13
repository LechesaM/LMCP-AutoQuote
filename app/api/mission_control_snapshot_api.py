from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter

from app.api.mission_control_compat_api import portal_health as get_portal_health_snapshot
from app.api.mission_control_compat_api import radar_status as get_radar_status_snapshot
from app.services import submission_analytics_service
from app.services.live_rfq_store import LiveRFQStore
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.portal_radar_service import get_portal_radar_summary
from app.services.province_enrichment import count_province_distribution, infer_province_code, infer_province_name
from app.services.submission_package_service import evaluate_submission_gate
from app.services.system_control_service import SystemControlService
from app.monitoring.health_service import get_system_health

router = APIRouter(prefix="/mission-control", tags=["Mission Control"])

PROVINCES = ("GP", "FS", "KZN", "WC", "EC", "NC", "NW", "MP", "LP")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text or default
    except Exception:
        return default


def _extract_live_rfq_items() -> List[Dict[str, Any]]:
    try:
        payload = LiveRFQStore.get_all()
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _enrich_live_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        province_name = infer_province_name(row)
        row["province"] = province_name or "Unknown"
        row["province_code"] = infer_province_code(row) or ""
        enriched.append(row)
    return enriched


def _pipeline_stages(lifecycle: Dict[str, Any]) -> Dict[str, int]:
    queue = _safe_dict(lifecycle.get("queue_by_lifecycle_state"))
    return {
        "Harvested": sum(_safe_int(queue.get(state)) for state in ("DISCOVERED", "QUALIFIED", "DOCUMENTS_ACQUIRED", "DOCUMENTS_PARSED", "PRICED")),
        "Ready": _safe_int(queue.get("SUBMISSION_READY")),
        "Quote Pack": _safe_int(queue.get("QUOTE_PACK_READY")),
        "Submitted": _safe_int(lifecycle.get("proof_captured_rfqs") or lifecycle.get("proof_archive_count")),
        "Blocked": sum(_safe_int(queue.get(state)) for state in ("FAILED", "REVIEW_REQUIRED", "READY_FOR_RETRY", "REJECTED")),
    }


def _quote_ready_count(lifecycle: Dict[str, Any]) -> int:
    queue = _safe_dict(lifecycle.get("queue_by_lifecycle_state"))
    return sum(
        _safe_int(queue.get(state))
        for state in ("QUOTE_PACK_READY", "SUBMISSION_READY", "SUBMISSION_READY_MANUAL")
    )


def _submitted_count(lifecycle: Dict[str, Any], profit_tracking: Dict[str, Any]) -> int:
    submitted = _safe_int(lifecycle.get("proof_captured_rfqs") or lifecycle.get("submitted_rfqs") or lifecycle.get("proof_archive_count"))
    if submitted:
        return submitted
    success_tracking = _safe_dict(profit_tracking.get("success_tracking"))
    return _safe_int(success_tracking.get("submitted") or success_tracking.get("total_submitted") or success_tracking.get("submitted_count"))


def _backend_status(system_health: Dict[str, Any], lifecycle: Dict[str, Any], radar_snapshot: Dict[str, Any]) -> str:
    if system_health.get("status") == "healthy" and lifecycle.get("status") == "ok" and radar_snapshot.get("status") != "error":
        return "healthy"
    return "degraded"


def _mode(system_control: Dict[str, Any]) -> str:
    return _safe_str(system_control.get("effective_system_status") or system_control.get("control_mode") or "controlled")


def _radar_snapshot(
    *,
    backend_status: str,
    harvested_count: int,
    quote_ready_count: int,
    lifecycle: Dict[str, Any],
    portal_radar: Dict[str, Any],
    portal_health: Dict[str, Any],
    radar_status: Dict[str, Any],
    system_health: Dict[str, Any],
) -> Dict[str, Any]:
    radar_payload = _safe_dict(radar_status.get("radar"))
    health_score = _safe_float(portal_radar.get("health_score_percent"))
    queue = _safe_dict(lifecycle.get("queue_by_lifecycle_state"))
    return {
        "status": _safe_str(portal_radar.get("status") or radar_status.get("status") or radar_payload.get("status") or "ok"),
        "serviceVersion": "mission-control-snapshot-v1",
        "sources": harvested_count,
        "eligible": quote_ready_count,
        "lifecycleHealthScore": _safe_float(lifecycle.get("lifecycle_health_score")),
        "systemResilienceScore": health_score or _safe_float(radar_payload.get("system_resilience_score")),
        "workerOnline": system_health.get("status") == "healthy",
        "onlineWorkers": _safe_int(radar_payload.get("online_workers")),
        "queueBacklog": sum(_safe_int(queue.get(state)) for state in ("FAILED", "REVIEW_REQUIRED", "READY_FOR_RETRY", "REJECTED")),
        "failedRfqs": _safe_int(lifecycle.get("failed_rfqs")),
        "reviewRequired": _safe_int(lifecycle.get("review_required_count") or lifecycle.get("review_required_rfqs")),
        "proofCaptured": _safe_int(lifecycle.get("proof_captured_rfqs") or lifecycle.get("proof_archive_count")),
        "estimatedMonthlyCapacity": _safe_int(lifecycle.get("estimated_monthly_capacity")),
        "uploadReadinessScore": _safe_float(radar_payload.get("upload_readiness_score")),
        "statusLabel": backend_status,
        "backendStatus": backend_status,
        "generatedAt": _safe_str(portal_radar.get("generated_at") or portal_health.get("generated_at") or _now_iso()),
    }


def _submission_readiness(lifecycle: Dict[str, Any], quote_ready_count: int, mode: str, backend_status: str) -> Dict[str, Any]:
    review_ready = quote_ready_count > 0
    submission_ready = review_ready and backend_status == "healthy" and mode != "off"
    detail = {
        "tender_id": "mission-control",
        "submission_package": {
            "approval_ready": review_ready,
            "submission_ready": submission_ready,
        },
        "review_ready_bundle": {"review_ready": review_ready},
        "governed_submission": {"submissionLocked": True},
        "submission_execution": {"execution_status": "ready" if submission_ready else "blocked"},
    }
    readiness = evaluate_submission_gate(detail)
    readiness.update(
        {
            "readiness_state": "READY" if readiness.get("allowed") else "MANUAL_ONLY",
            "approvalReady": bool(readiness.get("approval_ready")),
            "submissionReady": bool(readiness.get("submission_ready")),
            "blocking_issues": list(readiness.get("blocking_issues") or []),
            "proof_capture_status": _safe_dict(lifecycle.get("proof_capture_status")),
        }
    )
    return readiness


def _default_snapshot() -> Dict[str, Any]:
    return {
        "harvestedCount": 0,
        "quoteReadyCount": 0,
        "submittedCount": 0,
        "estimatedProfit": 0.0,
        "backendStatus": "degraded",
        "mode": "controlled",
        "portals": [],
        "provinceDistribution": dict.fromkeys(PROVINCES, 0),
        "radar": {},
        "pipelineStages": {"Harvested": 0, "Ready": 0, "Quote Pack": 0, "Submitted": 0, "Blocked": 0},
        "lifecycle": {},
        "submissionReadiness": {},
        "aiScoring": {"status": "not_configured", "items": []},
    }


@router.get("/snapshot")
def mission_control_snapshot() -> Dict[str, Any]:
    try:
        lifecycle_service = RfqLifecycleService()
        lifecycle = lifecycle_service.mission_control_summary()
        profit_tracking = submission_analytics_service.get_submission_profit_tracking(submitted_only=True)
        system_health = get_system_health()
        system_control = _safe_dict(lifecycle.get("safety", {}).get("system_control")) or SystemControlService().get_status()
        portal_health = get_portal_health_snapshot()
        portal_radar = get_portal_radar_summary()
        radar_status = get_radar_status_snapshot()
        live_items = _enrich_live_items(_extract_live_rfq_items())

        harvested_count = _safe_int(lifecycle.get("total_rfqs"))
        quote_ready_count = _quote_ready_count(lifecycle)
        submitted_count = _submitted_count(lifecycle, profit_tracking)
        estimated_profit = _safe_float(profit_tracking.get("estimated_profit"))
        backend_status = _backend_status(system_health, lifecycle, portal_radar)
        mode = _mode(system_control)

        return {
            "harvestedCount": harvested_count,
            "quoteReadyCount": quote_ready_count,
            "submittedCount": submitted_count,
            "estimatedProfit": estimated_profit,
            "backendStatus": backend_status,
            "mode": mode,
            "portals": _safe_list(portal_health.get("portals")),
            "provinceDistribution": count_province_distribution(live_items),
            "radar": _radar_snapshot(
                backend_status=backend_status,
                harvested_count=harvested_count,
                quote_ready_count=quote_ready_count,
                lifecycle=lifecycle,
                portal_radar=portal_radar,
                portal_health=portal_health,
                radar_status=radar_status,
                system_health=system_health,
            ),
            "pipelineStages": _pipeline_stages(lifecycle),
            "lifecycle": lifecycle,
            "submissionReadiness": _submission_readiness(lifecycle, quote_ready_count, mode, backend_status),
            "aiScoring": {"status": "not_configured", "items": []},
        }
    except Exception:
        return _default_snapshot()
