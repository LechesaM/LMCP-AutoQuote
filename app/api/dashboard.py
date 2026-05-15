from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

from app.services.portal_radar_service import get_portal_radar_summary
from app.services.procurement_heatmap import build_procurement_heatmap

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

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
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
        "recent_submissions": recent_submissions,
        "note": (
            "Dashboard summary includes file-based quote metrics, submission history metrics, and "
            "submission analytics metrics. Profit tracking depends on estimated financial values "
            "being present in submission history metadata/raw_result."
        ),
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


