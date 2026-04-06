import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AuditLog

router = APIRouter(tags=["LMCP Audit Trail"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_detail_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


@router.get("/audit/logs")
def get_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "status": row.status,
            "message": row.message,
            "opportunity_id": row.opportunity_id,
            "quote_id": row.quote_id,
            "job_id": row.job_id,
            "source": row.source,
            "detail": parse_detail_json(row.detail_json),
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


@router.get("/audit/opportunity/{opportunity_id}")
def get_audit_logs_for_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.opportunity_id == opportunity_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "status": row.status,
            "message": row.message,
            "opportunity_id": row.opportunity_id,
            "quote_id": row.quote_id,
            "job_id": row.job_id,
            "source": row.source,
            "detail": parse_detail_json(row.detail_json),
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


@router.get("/audit/quote/{quote_id}")
def get_audit_logs_for_quote(quote_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.quote_id == quote_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "status": row.status,
            "message": row.message,
            "opportunity_id": row.opportunity_id,
            "quote_id": row.quote_id,
            "job_id": row.job_id,
            "source": row.source,
            "detail": parse_detail_json(row.detail_json),
            "created_at": str(row.created_at),
        }
        for row in rows
    ]
