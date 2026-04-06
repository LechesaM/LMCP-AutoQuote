from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from app.services.portal_radar_service import get_portal_radar_summary
from app.services.procurement_heatmap import build_procurement_heatmap

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


@router.get("/system-health")
def dashboard_system_health() -> Dict[str, Any]:
    portal_radar = get_portal_radar_summary()

    return {
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "system_status": "ok",
        "portal_radar": portal_radar,
        "ui_flags": {
            "show_national_procurement_radar": True,
        },
    }


@router.get("/summary")
def dashboard_summary() -> Dict[str, Any]:
    artifact_summary = _count_monthly_quote_artifacts()

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
        "note": "Dashboard summary is file-based for now and can be upgraded to live pipeline metrics next.",
    }


@router.get("/procurement-heatmap")
def procurement_heatmap() -> Dict[str, Any]:
    return build_procurement_heatmap()
