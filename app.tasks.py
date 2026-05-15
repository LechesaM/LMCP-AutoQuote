from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.celery_app import celery
from app.database import SessionLocal
from app.models import Opportunity

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_db() -> Session:
    db = SessionLocal()
    return db


def safe_import(module_name: str, func_name: str):
    try:
        module = __import__(module_name, fromlist=[func_name])
        return getattr(module, func_name)
    except Exception as exc:
        logger.warning("Could not import %s.%s: %s", module_name, func_name, exc)
        return None


def serialize_result(name: str, status: str, detail: Any = None) -> Dict[str, Any]:
    return {
        "job": name,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "detail": detail,
    }


@celery.task(name="app.tasks.run_harvest_cycle")
def run_harvest_cycle() -> Dict[str, Any]:
    logger.info("Starting harvest cycle")
    harvest_fn = safe_import("app.harvest_engine", "run_harvest")

    if not harvest_fn:
        return serialize_result(
            "harvest_cycle",
            "warning",
            "app.harvest_engine.run_harvest not found",
        )

    try:
        result = harvest_fn()
        logger.info("Harvest cycle completed: %s", result)
        return serialize_result("harvest_cycle", "success", result)
    except Exception as exc:
        logger.exception("Harvest cycle failed")
        return serialize_result("harvest_cycle", "error", str(exc))


@celery.task(name="app.tasks.run_scoring_cycle")
def run_scoring_cycle() -> Dict[str, Any]:
    logger.info("Starting scoring cycle")
    score_fn = safe_import("app.relevance_engine", "score_unscored_opportunities")

    if not score_fn:
        return serialize_result(
            "scoring_cycle",
            "warning",
            "app.relevance_engine.score_unscored_opportunities not found",
        )

    try:
        result = score_fn()
        logger.info("Scoring cycle completed: %s", result)
        return serialize_result("scoring_cycle", "success", result)
    except Exception as exc:
        logger.exception("Scoring cycle failed")
        return serialize_result("scoring_cycle", "error", str(exc))


@celery.task(name="app.tasks.run_quote_cycle")
def run_quote_cycle() -> Dict[str, Any]:
    logger.info("Starting quote generation cycle")
    auto_quote_fn = safe_import("app.quote_generator", "auto_generate_quotes")

    if auto_quote_fn:
        try:
            result = auto_quote_fn()
            logger.info("Quote cycle completed: %s", result)
            return serialize_result("quote_cycle", "success", result)
        except Exception as exc:
            logger.exception("Quote cycle failed")
            return serialize_result("quote_cycle", "error", str(exc))

    db = get_db()
    try:
        opportunities: List[Opportunity] = (
            db.query(Opportunity)
            .filter(Opportunity.status == "new")
            .order_by(Opportunity.id.desc())
            .all()
        )

        processed = []
        for opp in opportunities:
            if hasattr(opp, "relevance_score") and opp.relevance_score is not None:
                if float(opp.relevance_score) < 60:
                    continue

            opp.status = "quote_pending"
            processed.append(
                {
                    "opportunity_id": opp.id,
                    "title": getattr(opp, "title", ""),
                    "new_status": opp.status,
                }
            )

        db.commit()
        logger.info("Quote cycle fallback processed %s opportunities", len(processed))
        return serialize_result("quote_cycle", "success", {"processed": processed})
    except Exception as exc:
        db.rollback()
        logger.exception("Quote cycle fallback failed")
        return serialize_result("quote_cycle", "error", str(exc))
    finally:
        db.close()


@celery.task(name="app.tasks.run_submission_pack_cycle")
def run_submission_pack_cycle() -> Dict[str, Any]:
    logger.info("Starting submission pack cycle")
    build_fn = safe_import("app.submission_pack", "auto_build_submission_packs")

    if not build_fn:
        return serialize_result(
            "submission_pack_cycle",
            "warning",
            "app.submission_pack.auto_build_submission_packs not found",
        )

    try:
        result = build_fn()
        logger.info("Submission pack cycle completed: %s", result)
        return serialize_result("submission_pack_cycle", "success", result)
    except Exception as exc:
        logger.exception("Submission pack cycle failed")
        return serialize_result("submission_pack_cycle", "error", str(exc))


@celery.task(name="app.tasks.run_email_submission_cycle")
def run_email_submission_cycle() -> Dict[str, Any]:
    logger.info("Starting email submission cycle")
    send_fn = safe_import("app.email_dispatcher", "auto_send_submissions")

    if not send_fn:
        return serialize_result(
            "email_submission_cycle",
            "warning",
            "app.email_dispatcher.auto_send_submissions not found",
        )

    try:
        result = send_fn()
        logger.info("Email submission cycle completed: %s", result)
        return serialize_result("email_submission_cycle", "success", result)
    except Exception as exc:
        logger.exception("Email submission cycle failed")
        return serialize_result("email_submission_cycle", "error", str(exc))


@celery.task(name="app.tasks.run_full_autonomous_cycle")
def run_full_autonomous_cycle() -> Dict[str, Any]:
    logger.info("Starting full autonomous cycle")

    results = {
        "harvest": run_harvest_cycle(),
        "scoring": run_scoring_cycle(),
        "quotes": run_quote_cycle(),
        "submission_packs": run_submission_pack_cycle(),
        "email_submissions": run_email_submission_cycle(),
    }

    logger.info("Full autonomous cycle completed")
    return serialize_result("full_autonomous_cycle", "success", results)
