# app/autonomous_engine.py

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.services.opportunity_persistence import persist_harvested_opportunities

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Safe feature flags
# -----------------------------------------------------------------------------

ENABLE_AUTONOMOUS_HARVEST = os.getenv("ENABLE_AUTONOMOUS_HARVEST", "true").strip().lower() in {
    "1", "true", "yes", "y", "on"
}

ENABLE_AUTONOMOUS_SCORING = os.getenv("ENABLE_AUTONOMOUS_SCORING", "true").strip().lower() in {
    "1", "true", "yes", "y", "on"
}

ENABLE_AUTONOMOUS_QUOTE_PIPELINE = os.getenv(
    "ENABLE_AUTONOMOUS_QUOTE_PIPELINE", "true"
).strip().lower() in {
    "1", "true", "yes", "y", "on"
}

MIN_SCORE_FOR_QUOTE = float(os.getenv("MIN_SCORE_FOR_QUOTE", "70"))


# -----------------------------------------------------------------------------
# Safe imports
# -----------------------------------------------------------------------------

def _import_harvester():
    try:
        from app.services.tender_harvester import run_national_tender_radar
        return run_national_tender_radar
    except Exception as exc:
        logger.exception("Unable to import run_national_tender_radar: %s", exc)
        return None


def _import_scoring_function():
    """
    Tries a few known scoring entry points without crashing the engine.
    """
    candidates = [
        ("app.scoring", "score_opportunities"),
        ("app.services.scoring", "score_opportunities"),
        ("app.services.opportunity_scoring", "score_opportunities"),
        ("app.services.scoring_engine", "score_opportunities"),
    ]

    for module_name, function_name in candidates:
        try:
            module = __import__(module_name, fromlist=[function_name])
            fn = getattr(module, function_name, None)
            if callable(fn):
                logger.info("Using scoring function: %s.%s", module_name, function_name)
                return fn
        except Exception:
            continue

    logger.warning("No dedicated score_opportunities() function found. Using safe fallback scoring.")
    return None


def _import_quote_pipeline():
    try:
        from app.services.intelligence_quote_pipeline import process_high_score_opportunities
        return process_high_score_opportunities
    except Exception as exc:
        logger.warning("Quote pipeline not available yet, safe fallback will be used: %s", exc)
        return None


# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _truncate(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    text = str(text)
    return text[:limit]


def _extract_score(item: Dict[str, Any]) -> float:
    """
    Supports several possible score field names.
    """
    for key in (
        "score",
        "opportunity_score",
        "relevance_score",
        "weighted_score",
        "final_score",
    ):
        if key in item:
            return _safe_float(item.get(key), 0.0)
    return 0.0


def _safe_reference(item: Dict[str, Any]) -> Optional[str]:
    for key in ("reference_number", "reference", "bid_number", "tender_number"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def _safe_title(item: Dict[str, Any]) -> str:
    return str(item.get("title") or item.get("name") or "Untitled Opportunity")


def _safe_url(item: Dict[str, Any]) -> str:
    return str(item.get("external_url") or item.get("url") or "")


def _safe_source(item: Dict[str, Any]) -> str:
    return str(item.get("source_name") or item.get("source") or "Unknown Source")


# -----------------------------------------------------------------------------
# Fallback scoring
# -----------------------------------------------------------------------------

def _fallback_score_single(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Very safe scoring heuristic so the engine still works even if the formal
    scoring module is missing.
    """
    title = (_safe_title(item) or "").lower()
    description = str(item.get("description") or "").lower()
    text = f"{title} {description}"

    score = 0.0
    reasons: List[str] = []

    positive_keywords = [
        "supply",
        "delivery",
        "goods",
        "procurement",
        "equipment",
        "materials",
        "consumables",
        "furniture",
        "stationery",
        "it equipment",
        "laptops",
        "printers",
        "uniform",
        "ppe",
    ]

    negative_keywords = [
        "construction",
        "civil works",
        "consultancy",
        "professional services",
        "maintenance",
        "repair",
        "renovation",
        "infrastructure",
    ]

    for kw in positive_keywords:
        if kw in text:
            score += 12
            reasons.append(f"Matched keyword: {kw}")

    for kw in negative_keywords:
        if kw in text:
            score -= 18
            reasons.append(f"Negative keyword: {kw}")

    if item.get("closing_date"):
        score += 8
        reasons.append("Has closing date")

    if item.get("reference_number"):
        score += 6
        reasons.append("Has reference number")

    if item.get("buyer_name"):
        score += 5
        reasons.append("Has buyer name")

    if item.get("category"):
        score += 4
        reasons.append("Has category")

    score = max(0.0, min(score, 100.0))

    enriched = dict(item)
    enriched["score"] = round(score, 2)
    enriched["score_reasons"] = reasons[:12]
    enriched["quote_candidate"] = score >= MIN_SCORE_FOR_QUOTE
    return enriched


def _fallback_score_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_fallback_score_single(item) for item in opportunities]


# -----------------------------------------------------------------------------
# Fallback quote preparation
# -----------------------------------------------------------------------------

def _build_quote_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    title = _safe_title(item)
    reference_number = _safe_reference(item)
    score = _extract_score(item)

    pricing_summary = {
        "pricing_model": "request_for_supplier_pricing",
        "basis": "commercial pricing to be generated from supplier catalogue mapping",
        "confidence": "medium" if score >= 80 else "preliminary",
    }

    compliance_flags = {
        "requires_csd": True,
        "requires_tax_clearance": True,
        "requires_bbee": True,
        "requires_sbd_forms": True,
    }

    return {
        "title": title,
        "reference_number": reference_number,
        "source_name": _safe_source(item),
        "external_url": _safe_url(item),
        "buyer_name": item.get("buyer_name"),
        "category": item.get("category"),
        "closing_date": item.get("closing_date"),
        "score": score,
        "pricing_summary": pricing_summary,
        "compliance_flags": compliance_flags,
    }


def _fallback_process_high_score_opportunities(
    db: Any,
    scored_opportunities: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for item in scored_opportunities:
        score = _extract_score(item)
        if score < MIN_SCORE_FOR_QUOTE:
            continue

        results.append(
            {
                "status": "quote_ready",
                "opportunity": item,
                "quote_payload": _build_quote_payload(item),
            }
        )

    return results


# -----------------------------------------------------------------------------
# Public status helper
# -----------------------------------------------------------------------------

def get_autonomous_status() -> Dict[str, Any]:
    return {
        "success": True,
        "service": "autonomous_engine",
        "timestamp": _utc_now_iso(),
        "features": {
            "harvest": ENABLE_AUTONOMOUS_HARVEST,
            "scoring": ENABLE_AUTONOMOUS_SCORING,
            "quote_pipeline": ENABLE_AUTONOMOUS_QUOTE_PIPELINE,
        },
        "thresholds": {
            "min_score_for_quote": MIN_SCORE_FOR_QUOTE,
        },
    }


# -----------------------------------------------------------------------------
# Main orchestration
# -----------------------------------------------------------------------------

def run_autonomous_cycle(db: Any = None) -> Dict[str, Any]:
    """
    Safe end-to-end autonomous run:
    1. Harvest
    2. Score
    3. Push high-score results into quote pipeline

    Returns one stable response structure for the API, dashboard, and logs.
    """
    started_at = _utc_now_iso()

    run_summary: Dict[str, Any] = {
        "success": True,
        "mode": "safe_autonomous_cycle",
        "started_at": started_at,
        "finished_at": None,
        "counts": {
            "harvested": 0,
            "scored": 0,
            "quote_ready": 0,
            "errors": 0,
        },
        "stages": {
            "harvest": {"success": False, "message": "", "count": 0},
            "scoring": {"success": False, "message": "", "count": 0},
            "quote_pipeline": {"success": False, "message": "", "count": 0},
        },
        "results": {
            "harvested_opportunities": [],
            "scored_opportunities": [],
            "quote_ready_results": [],
        },
    }

    harvested_opportunities: List[Dict[str, Any]] = []
    scored_opportunities: List[Dict[str, Any]] = []
    quote_ready_results: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Stage 1: Harvest
    # -------------------------------------------------------------------------
    if ENABLE_AUTONOMOUS_HARVEST:
        try:
            harvester = _import_harvester()
            if harvester is None:
                raise RuntimeError("Harvester entry point is unavailable.")

            harvest_result = harvester(db)
            if isinstance(harvest_result, dict):
                harvested_opportunities = list(harvest_result.get("results", []) or [])
            elif isinstance(harvest_result, list):
                harvested_opportunities = harvest_result
            else:
                harvested_opportunities = []

            run_summary["stages"]["harvest"] = {
                "success": True,
                "message": "Harvest completed successfully.",
                "count": len(harvested_opportunities),
            }
            run_summary["counts"]["harvested"] = len(harvested_opportunities)
            run_summary["results"]["harvested_opportunities"] = harvested_opportunities

        except Exception as exc:
            logger.exception("Autonomous harvest stage failed: %s", exc)
            run_summary["success"] = False
            run_summary["counts"]["errors"] += 1
            run_summary["stages"]["harvest"] = {
                "success": False,
                "message": f"Harvest failed: {exc}",
                "count": 0,
            }
    else:
        run_summary["stages"]["harvest"] = {
            "success": True,
            "message": "Harvest stage disabled by feature flag.",
            "count": 0,
        }

    # -------------------------------------------------------------------------
    # Stage 2: Scoring
    # -------------------------------------------------------------------------
    if ENABLE_AUTONOMOUS_SCORING:
        try:
            scoring_fn = _import_scoring_function()

            if scoring_fn and harvested_opportunities:
                try:
                    # common expected signature
                    scored_result = scoring_fn(harvested_opportunities)
                except TypeError:
                    # possible alternate signature
                    scored_result = scoring_fn(db, harvested_opportunities)

                if isinstance(scored_result, list):
                    scored_opportunities = scored_result
                elif isinstance(scored_result, dict):
                    scored_opportunities = list(
                        scored_result.get("results")
                        or scored_result.get("scored_opportunities")
                        or []
                    )
                else:
                    scored_opportunities = _fallback_score_opportunities(harvested_opportunities)
            else:
                scored_opportunities = _fallback_score_opportunities(harvested_opportunities)

            run_summary["stages"]["scoring"] = {
                "success": True,
                "message": "Scoring completed successfully.",
                "count": len(scored_opportunities),
            }
            run_summary["counts"]["scored"] = len(scored_opportunities)
            run_summary["results"]["scored_opportunities"] = scored_opportunities

        except Exception as exc:
            logger.exception("Autonomous scoring stage failed: %s", exc)
            run_summary["counts"]["errors"] += 1
            run_summary["stages"]["scoring"] = {
                "success": False,
                "message": f"Scoring failed: {exc}",
                "count": 0,
            }
            scored_opportunities = _fallback_score_opportunities(harvested_opportunities)
            run_summary["results"]["scored_opportunities"] = scored_opportunities
            run_summary["counts"]["scored"] = len(scored_opportunities)
    else:
        run_summary["stages"]["scoring"] = {
            "success": True,
            "message": "Scoring stage disabled by feature flag.",
            "count": 0,
        }

    # -------------------------------------------------------------------------
    # Stage 3: Quote pipeline
    # -------------------------------------------------------------------------
    if ENABLE_AUTONOMOUS_QUOTE_PIPELINE:
        try:
            quote_pipeline_fn = _import_quote_pipeline()

            if quote_pipeline_fn:
                try:
                    quote_ready_results = quote_pipeline_fn(db, scored_opportunities)
                except TypeError:
                    quote_ready_results = quote_pipeline_fn(scored_opportunities)

                if not isinstance(quote_ready_results, list):
                    quote_ready_results = _fallback_process_high_score_opportunities(
                        db, scored_opportunities
                    )
            else:
                quote_ready_results = _fallback_process_high_score_opportunities(
                    db, scored_opportunities
                )

            run_summary["stages"]["quote_pipeline"] = {
                "success": True,
                "message": "Quote pipeline completed successfully.",
                "count": len(quote_ready_results),
            }
            run_summary["counts"]["quote_ready"] = len(quote_ready_results)
            run_summary["results"]["quote_ready_results"] = quote_ready_results

        except Exception as exc:
            logger.exception("Autonomous quote pipeline failed: %s", exc)
            run_summary["counts"]["errors"] += 1
            run_summary["stages"]["quote_pipeline"] = {
                "success": False,
                "message": f"Quote pipeline failed: {exc}",
                "count": 0,
            }
            quote_ready_results = _fallback_process_high_score_opportunities(
                db, scored_opportunities
            )
            run_summary["results"]["quote_ready_results"] = quote_ready_results
            run_summary["counts"]["quote_ready"] = len(quote_ready_results)
    else:
        run_summary["stages"]["quote_pipeline"] = {
            "success": True,
            "message": "Quote pipeline disabled by feature flag.",
            "count": 0,
        }

    # -------------------------------------------------------------------------
    # Finish
    # -------------------------------------------------------------------------
    run_summary["finished_at"] = _utc_now_iso()

    # Compact preview for dashboard/API
    top_quote_candidates: List[Dict[str, Any]] = []
    for item in quote_ready_results[:20]:
        opportunity = item.get("opportunity", {}) if isinstance(item, dict) else {}
        quote_payload = item.get("quote_payload", {}) if isinstance(item, dict) else {}

        top_quote_candidates.append(
            {
                "title": _truncate(
                    quote_payload.get("title") or opportunity.get("title"), 300
                ),
                "reference_number": quote_payload.get("reference_number")
                or opportunity.get("reference_number"),
                "source_name": quote_payload.get("source_name")
                or opportunity.get("source_name"),
                "closing_date": quote_payload.get("closing_date")
                or opportunity.get("closing_date"),
                "score": quote_payload.get("score") or _extract_score(opportunity),
                "external_url": quote_payload.get("external_url")
                or opportunity.get("external_url"),
                "status": item.get("status", "quote_ready") if isinstance(item, dict) else "quote_ready",
            }
        )

    run_summary["preview"] = {
        "top_quote_candidates": top_quote_candidates,
    }

    return run_summary


# -----------------------------------------------------------------------------
# Backwards-compatible aliases
# -----------------------------------------------------------------------------

def run_once(db: Any = None) -> Dict[str, Any]:
    return run_autonomous_cycle(db=db)


def execute_autonomous_flow(db: Any = None) -> Dict[str, Any]:
    return run_autonomous_cycle(db=db)


def autonomous_status() -> Dict[str, Any]:
    return get_autonomous_status()
