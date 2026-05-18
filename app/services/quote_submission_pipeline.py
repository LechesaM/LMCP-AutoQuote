from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.db import SessionLocal
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def trigger_quote_to_submission_pipeline(opportunity_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opportunity:
            return {
                "success": False,
                "error": f"Opportunity {opportunity_id} not found",
                "processed_at": _now_iso(),
            }

        if opportunity.status != "quote_ready":
            return {
                "success": False,
                "error": f"Opportunity {opportunity_id} is not quote_ready",
                "current_status": opportunity.status,
                "processed_at": _now_iso(),
            }

        from app.quote_pack_service import build_quote_for_opportunity
        from app.quote_pack_service import generate_quote_pack_pdf
        from app.email_api import send_quote_email_for_opportunity

        quote_result = build_quote_for_opportunity(db, opportunity)
        if not quote_result.get("success"):
            return quote_result

        opportunity.status = "quote_generated"
        db.commit()

        pdf_result = generate_quote_pack_pdf(db, opportunity, quote_result)
        if not pdf_result.get("success"):
            return pdf_result

        opportunity.status = "pack_generated"
        db.commit()

        email_result = send_quote_email_for_opportunity(
            db=db,
            opportunity=opportunity,
            pdf_path=pdf_result["pdf_path"],
            quote_result=quote_result,
        )

        if email_result.get("success"):
            opportunity.status = "submitted"
        else:
            opportunity.status = "submission_failed"

        db.commit()

        return {
            "success": email_result.get("success", False),
            "processed_at": _now_iso(),
            "opportunity_id": opportunity.id,
            "quote_result": quote_result,
            "pdf_result": pdf_result,
            "email_result": email_result,
            "final_status": opportunity.status,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("trigger_quote_to_submission_pipeline failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "processed_at": _now_iso(),
            "opportunity_id": opportunity_id,
        }
    finally:
        db.close()
