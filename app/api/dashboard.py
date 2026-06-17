from __future__ import annotations

import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.live_rfq_store import LiveRFQStore
from app.services.operator_auth_service import OperatorAuthError, resolve_request_operator
from app.services.portal_radar_service import get_portal_radar_summary
from app.services.procurement_heatmap import build_procurement_heatmap
from app.services.quote_review_service import list_pilot_runs, list_review_queue, validate_quote_pack
from app.services.tender_harvester import (
    get_productive_source_pack_report,
    get_runtime_stability_report,
    get_runtime_stability_source_report,
    recheck_source_health,
    recheck_suppressed_source_health,
    reset_source_health,
)
from app.services.weekly_operations_report_service import build_weekly_operations_report
from app.pilot import pilot_core

try:
    from app.services.submission_history_service import (
        get_submission_summary,
        list_submission_history,
    )
except Exception:
    get_submission_summary = None
    list_submission_history = None

try:
    from app.services.submission_analytics_service import (
        get_submission_profit_tracking,
        get_submission_success_tracking,
    )
except Exception:
    get_submission_profit_tracking = None
    get_submission_success_tracking = None

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_operator(request: Request, action: str):
    try:
        return resolve_request_operator(request, action)
    except OperatorAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_monthly_quote_artifacts() -> Dict[str, int]:
    """
    Lightweight filesystem summary for dashboard visibility.
    Safe even if monthly_quotes does not exist yet.
    """
    base = Path("monthly_quotes")

    summary = {
        "rfq_folders": 0,
        "quote_pdfs": 0,
        "supplier_quotes_found": 0,
        "comparison_json_count": 0,
        "award_json_count": 0,
        "purchase_order_json_count": 0,
    }

    if not base.exists():
        return summary

    try:
        for month_dir in base.iterdir():
            if not month_dir.is_dir():
                continue

            for rfq_dir in month_dir.iterdir():
                if not rfq_dir.is_dir():
                    continue

                summary["rfq_folders"] += 1

                if (rfq_dir / "quote_comparison.json").exists():
                    summary["comparison_json_count"] += 1

                if (rfq_dir / "supplier_award.json").exists():
                    summary["award_json_count"] += 1

                if (rfq_dir / "supplier_purchase_order.json").exists():
                    summary["purchase_order_json_count"] += 1

                for pdf in rfq_dir.glob("*.pdf"):
                    summary["quote_pdfs"] += 1
                    if pdf.name.lower().startswith("supplier_quote_"):
                        summary["supplier_quotes_found"] += 1

    except Exception:
        return summary

    return summary


def _empty_submission_history_summary() -> Dict[str, Any]:
    return {
        "total": 0,
        "submitted": 0,
        "failed": 0,
        "manual_action_required": 0,
        "queued": 0,
        "unknown": 0,
        "recent": [],
        "history_file": "",
        "available": False,
        "note": "Submission history service not available yet.",
    }


def _get_submission_history_summary_safe() -> Dict[str, Any]:
    if get_submission_summary is None:
        return _empty_submission_history_summary()

    try:
        summary = get_submission_summary() or {}
        if not isinstance(summary, dict):
            return _empty_submission_history_summary()

        return {
            "total": int(summary.get("total") or 0),
            "submitted": int(summary.get("submitted") or 0),
            "failed": int(summary.get("failed") or 0),
            "manual_action_required": int(summary.get("manual_action_required") or 0),
            "queued": int(summary.get("queued") or 0),
            "unknown": int(summary.get("unknown") or 0),
            "recent": summary.get("recent") if isinstance(summary.get("recent"), list) else [],
            "history_file": str(summary.get("history_file") or ""),
            "available": True,
        }
    except Exception as exc:
        return {
            **_empty_submission_history_summary(),
            "note": f"Submission history service error: {exc}",
        }


def _get_recent_submission_items_safe(limit: int = 10) -> List[Dict[str, Any]]:
    if list_submission_history is None:
        return []

    try:
        result = list_submission_history(limit=limit, offset=0)
        if not isinstance(result, dict):
            return []

        items = result.get("items")
        if isinstance(items, list):
            return items[:limit]
        return []
    except Exception:
        return []


def _safe_success_tracking() -> Dict[str, Any]:
    if get_submission_success_tracking is None:
        return {"available": False}

    try:
        result = get_submission_success_tracking()
        if isinstance(result, dict):
            result["available"] = True
            return result
    except Exception as exc:
        return {"available": False, "error": str(exc)}

    return {"available": False}


def _safe_profit_tracking() -> Dict[str, Any]:
    if get_submission_profit_tracking is None:
        return {"available": False}

    try:
        result = get_submission_profit_tracking(submitted_only=True)
        if isinstance(result, dict):
            result["available"] = True
            return result
    except Exception as exc:
        return {"available": False, "error": str(exc)}

    return {"available": False}


@router.get("/system-health")
def dashboard_system_health() -> Dict[str, Any]:
    portal_radar = get_portal_radar_summary()
    submission_history = _get_submission_history_summary_safe()
    success_tracking = _safe_success_tracking()

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "system_status": "ok",
        "handwriting_stack_url": "/handwriting-stack/status",
        "portal_radar": portal_radar,
        "submission_history": {
            "available": submission_history.get("available", False),
            "total": submission_history.get("total", 0),
            "submitted": submission_history.get("submitted", 0),
            "failed": submission_history.get("failed", 0),
            "manual_action_required": submission_history.get("manual_action_required", 0),
            "queued": submission_history.get("queued", 0),
            "unknown": submission_history.get("unknown", 0),
        },
        "submission_success_tracking": {
            "available": success_tracking.get("available", False),
            "success_rate": success_tracking.get("success_rate", 0.0),
            "failure_rate": success_tracking.get("failure_rate", 0.0),
        },
        "ui_flags": {
            "show_national_procurement_radar": True,
            "show_submission_history": True,
            "show_submission_analytics": True,
        },
    }


@router.get("/summary")
def dashboard_summary() -> Dict[str, Any]:
    artifact_summary = _count_monthly_quote_artifacts()
    submission_history = _get_submission_history_summary_safe()
    recent_submissions = _get_recent_submission_items_safe(limit=10)
    success_tracking = _safe_success_tracking()
    profit_tracking = _safe_profit_tracking()
    controlled_pilot_dashboard = pilot_core.build_controlled_pilot_dashboard(limit=50)

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "handwriting_stack_url": "/handwriting-stack/status",
        "summary": {
            "rfq_folders": artifact_summary["rfq_folders"],
            "quote_pdfs": artifact_summary["quote_pdfs"],
            "supplier_quotes_found": artifact_summary["supplier_quotes_found"],
            "comparison_json_count": artifact_summary["comparison_json_count"],
            "award_json_count": artifact_summary["award_json_count"],
            "purchase_order_json_count": artifact_summary["purchase_order_json_count"],
        },
        "submission_history": {
            "available": submission_history.get("available", False),
            "total": submission_history.get("total", 0),
            "submitted": submission_history.get("submitted", 0),
            "failed": submission_history.get("failed", 0),
            "manual_action_required": submission_history.get("manual_action_required", 0),
            "queued": submission_history.get("queued", 0),
            "unknown": submission_history.get("unknown", 0),
            "history_file": submission_history.get("history_file", ""),
        },
        "submission_success_tracking": {
            "available": success_tracking.get("available", False),
            "total": success_tracking.get("total", 0),
            "submitted": success_tracking.get("submitted", 0),
            "failed": success_tracking.get("failed", 0),
            "success_rate": success_tracking.get("success_rate", 0.0),
            "failure_rate": success_tracking.get("failure_rate", 0.0),
            "by_method": success_tracking.get("by_method", []),
        },
        "submission_profit_tracking": {
            "available": profit_tracking.get("available", False),
            "counted_records": profit_tracking.get("counted_records", 0),
            "uncosted_records": profit_tracking.get("uncosted_records", 0),
            "estimated_revenue": profit_tracking.get("estimated_revenue", 0.0),
            "estimated_cost": profit_tracking.get("estimated_cost", 0.0),
            "estimated_profit": profit_tracking.get("estimated_profit", 0.0),
            "estimated_margin": profit_tracking.get("estimated_margin", 0.0),
            "by_method": profit_tracking.get("by_method", []),
        },
        "controlled_pilot_dashboard": controlled_pilot_dashboard,
        "recent_submissions": recent_submissions,
        "note": (
            "Dashboard summary includes file-based quote metrics, submission history metrics, and "
            "submission analytics metrics. Profit tracking depends on estimated financial values "
            "being present in submission history metadata/raw_result."
        ),
    }


@router.get("/pilot")
def dashboard_pilot() -> Dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "controlled_pilot_dashboard": pilot_core.build_controlled_pilot_dashboard(limit=50),
    }


@router.get("/recent-submissions")
def dashboard_recent_submissions(limit: int = 10) -> Dict[str, Any]:
    safe_limit = max(1, min(int(limit or 10), 100))
    items = _get_recent_submission_items_safe(limit=safe_limit)

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "count": len(items),
        "items": items,
    }


@router.get("/procurement-heatmap")
def procurement_heatmap() -> Dict[str, Any]:
    return build_procurement_heatmap()


@router.get("/manual-review/summary")
def dashboard_manual_review_summary(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    queue = list_review_queue(db)
    status_counts: Dict[str, int] = {}
    blocked_quotes = 0
    ready_for_approval = 0
    ready_for_submission = 0

    for quote in queue:
        status_key = quote.status.value if getattr(quote.status, "value", None) else str(quote.status)
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        validation = validate_quote_pack(quote)
        if validation.get("errors"):
            blocked_quotes += 1
        if validation.get("ready_for_approval"):
            ready_for_approval += 1
        if validation.get("ready_for_submission"):
            ready_for_submission += 1

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "total_quotes": len(queue),
        "status_counts": status_counts,
        "blocked_quotes": blocked_quotes,
        "ready_for_approval": ready_for_approval,
        "ready_for_submission": ready_for_submission,
    }


@router.get("/manual-review/queue")
def dashboard_manual_review_queue(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_operator(request, "quote_review_view")
    queue = list_review_queue(db)
    items: List[Dict[str, Any]] = []
    for quote in queue:
        validation = validate_quote_pack(quote)
        items.append(
            {
                "id": quote.id,
                "quote_number": quote.quote_number,
                "project_title": quote.project_title,
                "buyer_name": quote.buyer_name,
                "rfq_reference": quote.rfq_reference,
                "status": quote.status.value if getattr(quote.status, "value", None) else str(quote.status),
                "province": quote.province,
                "closing_date_text": quote.closing_date_text,
                "briefing_required": bool(quote.briefing_required),
                "estimated_profit": float(quote.estimated_profit or 0.0),
                "estimated_margin_percent": float(quote.estimated_margin_percent or 0.0),
                "validation": validation,
            }
        )

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "count": len(items),
        "items": items,
    }


@router.get("/manual-review/pilot-summary")
def dashboard_manual_review_pilot_summary(request: Request) -> Dict[str, Any]:
    _require_operator(request, "quote_review_pilot_view")
    runs = list_pilot_runs()
    latest = runs[0] if runs else None
    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "total_runs": len(runs),
        "latest_run": latest or {},
        "runs": runs[:10],
    }


@router.get("/buyer-pack-acquisition")
def dashboard_buyer_pack_acquisition() -> Dict[str, Any]:
    return LiveRFQStore.get_buyer_pack_acquisition_report()


@router.get("/external-submission-candidate-queue")
def dashboard_external_submission_candidate_queue(limit: int = 3) -> Dict[str, Any]:
    return LiveRFQStore.get_external_submission_candidate_queue(limit=limit)


@router.get("/benchmark-candidate-search")
def dashboard_benchmark_candidate_search(limit: int = 5) -> Dict[str, Any]:
    return LiveRFQStore.get_benchmark_candidate_search(limit=limit)


@router.get("/procurement-shape-distribution")
def dashboard_procurement_shape_distribution() -> Dict[str, Any]:
    return LiveRFQStore.get_procurement_shape_distribution_report()


@router.get("/source-shape-performance")
def dashboard_source_shape_performance(limit: int = 10) -> Dict[str, Any]:
    return LiveRFQStore.get_source_shape_performance_report(limit=limit)


@router.get("/runtime-stability")
def dashboard_runtime_stability(limit: int = 15) -> Dict[str, Any]:
    return get_runtime_stability_report(limit=limit)


@router.get("/runtime-stability/sources")
def dashboard_runtime_stability_sources(limit: int = 1000) -> Dict[str, Any]:
    return get_runtime_stability_source_report(limit=limit)


@router.get("/source-pool/productive")
def dashboard_productive_source_pool(limit: int = 25) -> Dict[str, Any]:
    return get_productive_source_pack_report(limit=limit)


@router.post("/source-pool/health/reset")
def dashboard_reset_source_health(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    identifier = payload.get("source_name") or payload.get("source_url") or payload.get("identifier")
    return reset_source_health(identifier)


@router.post("/source-pool/health/recheck")
def dashboard_recheck_source_health(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    if payload.get("all_suppressed"):
        return recheck_suppressed_source_health()
    identifier = payload.get("source_name") or payload.get("source_url") or payload.get("identifier")
    return recheck_source_health(identifier)


@router.get("/weekly-operations")
def dashboard_weekly_operations(window_days: int = 7, limit: int = 25) -> Dict[str, Any]:
    return build_weekly_operations_report(window_days=window_days, limit=limit)


@router.get("/debug/network")
def dashboard_debug_network() -> Dict[str, Any]:
    def _resolve(host: str) -> str:
        try:
            return socket.gethostbyname(host)
        except Exception as exc:
            return str(exc)

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "google": _resolve("google.com"),
        "etenders": _resolve("www.etenders.gov.za"),
    }
