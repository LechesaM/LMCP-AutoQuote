from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.quote_draft_store import QuoteDraftStore
from app.services.quote_engine import QuoteEngine


router = APIRouter(
    prefix="/quote-engine",
    tags=["Quote Engine"],
)


@router.get("/health", operation_id="quote_engine_health")
def quote_engine_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "quote_engine",
        "features": {
            "auto_quote_generation": True,
            "source": "recommended_live_rfqs",
            "draft_storage": "runtime/quote_drafts.json",
            "vat_rate": 0.15,
            "default_margin_percent": 25.0,
        },
    }


@router.post("/run", operation_id="quote_engine_run")
def run_quote_engine() -> Dict[str, Any]:
    result = QuoteEngine.generate_quotes_from_recommended_rfqs()
    saved = QuoteDraftStore.replace_all(result.get("items", []))

    return {
        "status": "ok",
        "message": "Quote engine executed successfully",
        "generated_count": result.get("count", 0),
        "saved_count": saved.get("count", 0),
        "items": saved.get("items", []),
        "skipped": result.get("skipped", []),
    }


@router.get("/drafts", operation_id="quote_engine_drafts")
def get_quote_drafts() -> Dict[str, Any]:
    return QuoteDraftStore.get_all()
