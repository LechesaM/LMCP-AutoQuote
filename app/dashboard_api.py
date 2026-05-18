from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Opportunity, QuoteDraft

router = APIRouter(prefix="/dashboard", tags=["Dashboard Mission Control"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _safe_attr(obj: Any, name: str, default=None):
    return getattr(obj, name, default)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    High-level dashboard counters for mission control cards.
    """
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    total_opportunities = db.query(func.count(Opportunity.id)).scalar() or 0
    total_quotes = db.query(func.count(QuoteDraft.id)).scalar() or 0

    harvested_today = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.created_at >= last_24h)
        .scalar()
        or 0
    )

    try:
        qualified_rfqs = (
            db.query(func.count(Opportunity.id))
            .filter(Opportunity.score >= 60)
            .scalar()
            or 0
        )
    except Exception:
        qualified_rfqs = 0

    try:
        quotes_today = (
            db.query(func.count(QuoteDraft.id))
            .filter(QuoteDraft.created_at >= last_24h)
            .scalar()
            or 0
        )
    except Exception:
        quotes_today = 0

    try:
        ready_to_submit = (
            db.query(func.count(QuoteDraft.id))
            .filter(QuoteDraft.status.in_(["pack_built", "ready_to_submit", "submission_ready"]))
            .scalar()
            or 0
        )
    except Exception:
        ready_to_submit = 0

    try:
        submitted_count = (
            db.query(func.count(QuoteDraft.id))
            .filter(QuoteDraft.status.in_(["submitted", "email_submitted"]))
            .scalar()
            or 0
        )
    except Exception:
        submitted_count = 0

    try:
        failed_count = (
            db.query(func.count(QuoteDraft.id))
            .filter(QuoteDraft.status.in_(["failed", "submission_failed", "email_failed"]))
            .scalar()
            or 0
        )
    except Exception:
        failed_count = 0

    return {
        "timestamp": _now_iso(),
        "cards": {
            "harvested_today": harvested_today,
            "qualified_rfqs": qualified_rfqs,
            "quotes_generated": total_quotes,
            "quotes_today": quotes_today,
            "submission_packs_ready": ready_to_submit,
            "emails_submitted": submitted_count,
            "failures": failed_count,
            "total_opportunities": total_opportunities,
        },
    }


@router.get("/opportunities")
def dashboard_opportunities(limit: int = 25, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Latest harvested opportunities.
    """
    items = db.query(Opportunity).order_by(desc(Opportunity.id)).limit(limit).all()

    data: List[Dict[str, Any]] = []
    for item in items:
        data.append(
            {
                "id": item.id,
                "title": _safe_attr(item, "title", ""),
                "buyer": _safe_attr(item, "buyer", ""),
                "source": _safe_attr(item, "source", ""),
                "province": _safe_attr(item, "province", ""),
                "submission_method": _safe_attr(item, "submission_method", ""),
                "closing_date": str(_safe_attr(item, "closing_date", "") or ""),
                "score": _safe_attr(item, "score", 0),
                "status": _safe_attr(item, "status", ""),
                "created_at": str(_safe_attr(item, "created_at", "") or ""),
            }
        )

    return {
        "timestamp": _now_iso(),
        "count": len(data),
        "items": data,
    }


@router.get("/quotes")
def dashboard_quotes(limit: int = 25, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Latest quote drafts / packs / submissions.
    """
    items = db.query(QuoteDraft).order_by(desc(QuoteDraft.id)).limit(limit).all()

    data: List[Dict[str, Any]] = []
    for item in items:
        data.append(
            {
                "id": item.id,
                "quote_number": _safe_attr(item, "quote_number", ""),
                "opportunity_id": _safe_attr(item, "opportunity_id", None),
                "status": _safe_attr(item, "status", ""),
                "total_amount": _safe_attr(item, "total_amount", 0),
                "document_path": _safe_attr(item, "document_path", ""),
                "pack_path": _safe_attr(item, "pack_path", ""),
                "email_to": _safe_attr(item, "email_to", ""),
                "submitted_at": str(_safe_attr(item, "submitted_at", "") or ""),
                "created_at": str(_safe_attr(item, "created_at", "") or ""),
            }
        )

    return {
        "timestamp": _now_iso(),
        "count": len(data),
        "items": data,
    }


@router.get("/submissions")
def dashboard_submissions(limit: int = 25, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Focused view of items that are submitted / ready / failed.
    """
    try:
        items = (
            db.query(QuoteDraft)
            .filter(
                QuoteDraft.status.in_(
                    [
                        "pack_built",
                        "ready_to_submit",
                        "submission_ready",
                        "submitted",
                        "email_submitted",
                        "failed",
                        "email_failed",
                        "submission_failed",
                    ]
                )
            )
            .order_by(desc(QuoteDraft.id))
            .limit(limit)
            .all()
        )
    except Exception:
        items = db.query(QuoteDraft).order_by(desc(QuoteDraft.id)).limit(limit).all()

    data: List[Dict[str, Any]] = []
    for item in items:
        data.append(
            {
                "id": item.id,
                "quote_number": _safe_attr(item, "quote_number", ""),
                "status": _safe_attr(item, "status", ""),
                "email_to": _safe_attr(item, "email_to", ""),
                "pack_path": _safe_attr(item, "pack_path", ""),
                "submitted_at": str(_safe_attr(item, "submitted_at", "") or ""),
                "created_at": str(_safe_attr(item, "created_at", "") or ""),
            }
        )

    return {
        "timestamp": _now_iso(),
        "count": len(data),
        "items": data,
    }


@router.get("/system-health")
def dashboard_system_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Basic health and heartbeat endpoint for dashboard.
    """
    try:
        db.query(func.count(Opportunity.id)).scalar()
        database_ok = True
    except Exception as exc:
        database_ok = False
        return {
            "timestamp": _now_iso(),
            "status": "degraded",
            "database_ok": False,
            "error": str(exc),
        }

    return {
        "timestamp": _now_iso(),
        "status": "ok",
        "database_ok": database_ok,
        "api_ok": True,
        "dashboard_ok": True,
    }
