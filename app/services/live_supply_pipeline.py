from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from app.services.supply_classifier import classify_supply_rfq
from app.services.pricing_engine import build_supply_quote
from app.services.opportunity_scorer import score_opportunity
from app.services.submission_engine import build_submission_pack


LIVE_RFQ_FILE = os.getenv(
    "LMCP_LIVE_RFQ_FILE",
    "runtime/live_harvested_rfqs.json",
)


def _ensure_runtime_dir() -> None:
    os.makedirs(os.path.dirname(LIVE_RFQ_FILE), exist_ok=True)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def load_live_rfqs() -> List[Dict[str, Any]]:
    _ensure_runtime_dir()

    if not os.path.exists(LIVE_RFQ_FILE):
        with open(LIVE_RFQ_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return []

    with open(LIVE_RFQ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue

        rfq = {
            "rfq_id": item.get("rfq_id") or f"LIVE-RFQ-{idx}",
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "scope": item.get("scope", ""),
            "requirements": item.get("requirements", ""),
            "category": item.get("category", ""),
            "quantities": item.get("quantities", []),
            "submission_method": item.get("submission_method", ""),
            "submission_email": item.get("submission_email"),
            "deadline": item.get("deadline"),
            "portal_url": item.get("portal_url"),
            "notes": item.get("notes", ""),
            "source": item.get("source", "live_harvester"),
        }
        cleaned.append(rfq)

    return cleaned


def save_live_rfqs(rfqs: List[Dict[str, Any]]) -> None:
    _ensure_runtime_dir()
    with open(LIVE_RFQ_FILE, "w", encoding="utf-8") as f:
        json.dump(rfqs, f, indent=2)


def append_live_rfqs(rfqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    existing = load_live_rfqs()
    existing_ids = {str(item.get("rfq_id", "")).strip() for item in existing}

    added = 0
    skipped_duplicates = 0

    for rfq in rfqs:
        rfq_id = str(rfq.get("rfq_id", "")).strip()
        if rfq_id and rfq_id in existing_ids:
            skipped_duplicates += 1
            continue

        existing.append(rfq)
        if rfq_id:
            existing_ids.add(rfq_id)
        added += 1

    save_live_rfqs(existing)

    return {
        "status": "ok",
        "added": added,
        "skipped_duplicates": skipped_duplicates,
        "total_live_rfqs": len(existing),
        "file": LIVE_RFQ_FILE,
    }


def analyze_live_rfqs() -> Dict[str, Any]:
    rfqs = load_live_rfqs()
    results: List[Dict[str, Any]] = []

    for rfq in rfqs:
        classification = classify_supply_rfq(rfq)
        quote = build_supply_quote(classification)
        scoring = score_opportunity(rfq, classification, quote)
        pack = build_submission_pack(rfq, classification, quote, scoring)

        results.append({
            "rfq": rfq,
            "classification": classification,
            "quote": quote,
            "scoring": scoring,
            "submission_pack": pack,
            "quote": quote,
        })

    total_rfqs = len(results)
    eligible_rfqs = sum(1 for r in results if r["classification"].get("eligible"))
    excluded_rfqs = sum(1 for r in results if r["classification"].get("excluded"))
    construction_rfqs = sum(1 for r in results if r["classification"].get("is_construction"))
    can_quote = sum(1 for r in results if r["quote"].get("can_quote"))
    recommended_submit = sum(1 for r in results if r["scoring"].get("recommended_action") == "SUBMIT")
    recommended_review = sum(1 for r in results if r["scoring"].get("recommended_action") == "REVIEW")
    recommended_skip = sum(1 for r in results if r["scoring"].get("recommended_action") == "SKIP")
    ready_submission_packs = sum(1 for r in results if r["submission_pack"].get("ready"))

    estimated_pipeline_excl_vat = sum(
        _safe_float(r["quote"].get("cost_breakdown", {}).get("quote_total_excl_vat", 0.0))
        for r in results
        if r["scoring"].get("recommended_action") == "SUBMIT"
    )

    estimated_profit_pipeline = sum(
        _safe_float(r["quote"].get("cost_breakdown", {}).get("gross_profit", 0.0))
        for r in results
        if r["scoring"].get("recommended_action") == "SUBMIT"
    )

    today_money_list: List[Dict[str, Any]] = []
    rejected_list: List[Dict[str, Any]] = []

    for r in results:
        row = {
            "rfq_id": r["rfq"].get("rfq_id"),
            "title": r["rfq"].get("title"),
            "category": r["classification"].get("category"),
            "excluded_category": r["classification"].get("excluded_category"),
            "is_construction": r["classification"].get("is_construction"),
            "submission_mode": r["classification"].get("submission_mode"),
            "score": r["scoring"].get("score"),
            "priority": r["scoring"].get("priority"),
            "action": r["scoring"].get("recommended_action"),
            "profit_floor_passed": r["scoring"].get("profit_floor_passed"),
            "value_excl_vat": r["quote"].get("cost_breakdown", {}).get("quote_total_excl_vat", 0.0),
            "gross_profit": r["quote"].get("cost_breakdown", {}).get("gross_profit", 0.0),
            "ready": r["submission_pack"].get("ready"),
            "source": r["rfq"].get("source", "live_harvester"),
        }

        if r["scoring"].get("recommended_action") == "SUBMIT":
            today_money_list.append(row)
        else:
            rejected_list.append({
                **row,
                "reason": r["submission_pack"].get("reason") or "; ".join(r["scoring"].get("reasons", [])),
            })

    today_money_list.sort(
        key=lambda x: (
            x["action"] != "SUBMIT",
            -_safe_float(x["score"]),
            -_safe_float(x["gross_profit"]),
        )
    )

    return {
        "source_file": LIVE_RFQ_FILE,
        "summary": {
            "total_rfqs": total_rfqs,
            "eligible_rfqs": eligible_rfqs,
            "excluded_rfqs": excluded_rfqs,
            "construction_rfqs": construction_rfqs,
            "can_quote": can_quote,
            "recommended_submit": recommended_submit,
            "recommended_review": recommended_review,
            "recommended_skip": recommended_skip,
            "ready_submission_packs": ready_submission_packs,
            "estimated_pipeline_excl_vat": round(estimated_pipeline_excl_vat, 2),
            "estimated_profit_pipeline": round(estimated_profit_pipeline, 2),
        },
        "today_money_list": today_money_list,
        "rejected_list": rejected_list,
        "results": results,
    }
