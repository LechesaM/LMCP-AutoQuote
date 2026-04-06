from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Opportunity
from app.relevance_scoring import score_opportunity


router = APIRouter(tags=["LMCP Relevance Scoring"])


def get_db() -> Session:
    db = SessionLocal()
    return db


@router.post("/score/{opportunity_id}")
def score_single_opportunity(opportunity_id: int):
    db = get_db()
    try:
        opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()

        if not opportunity:
            return {"status": "error", "message": "Opportunity not found"}

        result = score_opportunity(
            title=opportunity.title,
            description=opportunity.description,
            buyer=opportunity.buyer,
            category=opportunity.category,
        )

        opportunity.relevance_score = result["relevance_score"]
        opportunity.relevance_level = result["relevance_level"]
        opportunity.score_reason = result["score_reason"]
        opportunity.auto_bid_recommended = result["auto_bid_recommended"]

        db.commit()
        db.refresh(opportunity)

        return {
            "status": "success",
            "opportunity_id": opportunity.id,
            "title": opportunity.title,
            "relevance_score": opportunity.relevance_score,
            "relevance_level": opportunity.relevance_level,
            "score_reason": opportunity.score_reason,
            "auto_bid_recommended": opportunity.auto_bid_recommended,
        }
    finally:
        db.close()


@router.post("/score-all")
def score_all_opportunities():
    db = get_db()
    try:
        opportunities = db.query(Opportunity).all()
        updated = 0

        for opportunity in opportunities:
            result = score_opportunity(
                title=opportunity.title,
                description=opportunity.description,
                buyer=opportunity.buyer,
                category=opportunity.category,
            )

            opportunity.relevance_score = result["relevance_score"]
            opportunity.relevance_level = result["relevance_level"]
            opportunity.score_reason = result["score_reason"]
            opportunity.auto_bid_recommended = result["auto_bid_recommended"]
            updated += 1

        db.commit()

        return {
            "status": "success",
            "updated": updated,
        }
    finally:
        db.close()
