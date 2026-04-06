from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.database import SessionLocal
from app.models import QuoteDraft

router = APIRouter(prefix="/quotes", tags=["quotes"])


def _row_to_dict(row: QuoteDraft) -> Dict[str, Any]:
    return {
        "id": row.id,
        "opportunity_id": row.opportunity_id,
        "buyer_name": row.buyer_name,
        "reference_number": row.reference_number,
        "title": row.title,
        "description": row.description,
        "category": row.category,
        "closing_date": row.closing_date,
        "delivery_period": row.delivery_period,
        "validity_period": row.validity_period,
        "scope_summary": row.scope_summary,
        "cover_letter": row.cover_letter,
        "pricing_notes": row.pricing_notes,
        "internal_review_notes": row.internal_review_notes,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/", response_model=List[Dict[str, Any]])
def list_quotes() -> List[Dict[str, Any]]:
    session = SessionLocal()
    try:
        rows = session.query(QuoteDraft).order_by(QuoteDraft.created_at.desc()).all()
        return [_row_to_dict(row) for row in rows]
    finally:
        session.close()


@router.get("/{quote_id}", response_model=Dict[str, Any])
def get_quote(quote_id: int) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        row = session.query(QuoteDraft).filter(QuoteDraft.id == quote_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Quote draft not found")
        return _row_to_dict(row)
    finally:
        session.close()
