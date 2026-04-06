from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Body

from app.core.supply_target_config import (
    SUPPLY_MIN_PROFIT_PER_WIN,
    SUPPLY_MONTHLY_PROFIT_TARGET,
    SUPPLY_WINS_TARGET_PER_MONTH,
)
from app.services.opportunity_scorer import score_opportunity
from app.services.pricing_engine import build_supply_quote
from app.services.submission_engine import (
    build_submission_pack,
    get_submission_summary,
    mark_submission_status,
)
from app.services.supplier_engine import get_all_suppliers
from app.services.supply_classifier import classify_supply_rfq
from app.services.target_control_engine import build_target_control
from app.services.live_supply_pipeline import (
    analyze_live_rfqs,
    append_live_rfqs,
    load_live_rfqs,
)

router = APIRouter(prefix="/revenue-dashboard", tags=["Revenue Dashboard"])


DEMO_RFQS: List[Dict[str, Any]] = [
    {
        "rfq_id": "RFQ-1001",
        "title": "Supply and delivery of HDPE pipes to Northern Cape district stores",
        "description": (
            "Appointment of a supplier for supply and delivery of HDPE pipes and valves. "
            "Quantity required: 1200 pipes. Submit via email. No compulsory briefing."
        ),
        "scope": "Supply and delivery only.",
        "requirements": "Tax compliant, CSD registered.",
        "submission_method": "email",
        "submission_email": "quotes@example-municipality.gov.za",
        "deadline": "2026-03-31 11:00",
        "portal_url": None,
    },
    {
        "rfq_id": "RFQ-1002",
        "title": "Supply of PPE for district facilities",
        "description": (
            "Supply of 20000 gloves, 8000 masks, 2500 face shields and reflective wear. "
            "Portal submission. Briefing not compulsory."
        ),
        "scope": "Supply and delivery to district stores.",
        "requirements": "Proof of capacity required.",
        "submission_method": "portal",
        "submission_email": None,
        "deadline": "2026-03-28 12:00",
        "portal_url": "https://portal.example.org/rfq/1002",
    },
    {
        "rfq_id": "RFQ-1003",
        "title": "Construction of boundary wall and associated works",
        "description": "Mandatory site meeting. Construction and civil works.",
        "scope": "Works contract.",
        "requirements": "CIDB required.",
        "submission_method": "portal",
        "submission_email": None,
        "deadline": "2026-04-02 10:00",
        "portal_url": "https://portal.example.org/rfq/1003",
    },
    {
        "rfq_id": "RFQ-1004",
        "title": "Supply and delivery of office stationery to provincial offices",
        "description": (
            "Supply of 5000 reams of A4 paper, files and pens. "
            "Submit via email. Non-compulsory briefing."
        ),
        "scope": "Supply only.",
        "requirements": "Supplier must have delivery capacity.",
        "submission_method": "email",
        "submission_email": "stationery@province.gov.za",
        "deadline": "2026-03-29 10:00",
        "portal_url": None,
    },
    {
        "rfq_id": "RFQ-1005",
        "title": "Supply of diesel for municipal fleet",
        "description": (
            "Supply and delivery of diesel to municipal depots. "
            "Email submissions invited."
        ),
        "scope": "Fuel supply.",
        "requirements": "Bulk supply capability required.",
        "submission_method": "email",
        "submission_email": "fleetfuel@municipality.gov.za",
        "deadline": "2026-03-27 11:00",
        "portal_url": None,
    },
    {
        "rfq_id": "RFQ-1006",
        "title": "Supply of laptops and printers for district offices",
        "description": (
            "Supply and delivery of 150 laptops and 60 printers to district offices. "
            "Portal submission."
        ),
        "scope": "Supply only.",
        "requirements": "Warranty and support required.",
        "submission_method": "portal",
        "submission_email": None,
        "deadline": "2026-03-30 09:00",
        "portal_url": "https://portal.example.org/rfq/1006",
    },
    {
        "rfq_id": "RFQ-1007",
        "title": "Supply of cleaning materials to regional offices",
        "description": (
            "Supply and delivery of disinfectant, toilet paper, mops and refuse bags. "
            "Submit via email. Briefing not compulsory."
        ),
        "scope": "Pure supply and delivery.",
        "requirements": "Delivery to multiple offices.",
        "submission_method": "email",
        "submission_email": "cleaning@province.gov.za",
        "deadline": "2026-03-26 10:30",
        "portal_url": None,
    },
]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _analyze_single_rfq(rfq: Dict[str, Any]) -> Dict[str, Any]:
    classification = classify_supply_rfq(rfq)
    quote = build_supply_quote(classification)
    scoring = score_opportunity(rfq, classification, quote)
    pack = build_submission_pack(rfq, classification, quote, scoring)

    return {
        "rfq": rfq,
        "classification": classification,
        "quote": quote,
        "scoring": scoring,
        "submission_pack": pack,
    }


def _summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_rfqs = len(results)
    eligible_rfqs = sum(1 for r in results if r["classification"].get("eligible"))
    excluded_rfqs = sum(1 for r in results if r["classification"].get("excluded"))
    construction_rfqs = sum(1 for r in results if r["classification"].get("is_construction"))
    can_quote = sum(1 for r in results if r["quote"].get("can_quote"))
    submit_count = sum(1 for r in results if r["scoring"].get("recommended_action") == "SUBMIT")
    review_count = sum(1 for r in results if r["scoring"].get("recommended_action") == "REVIEW")
    skip_count = sum(1 for r in results if r["scoring"].get("recommended_action") == "SKIP")
    ready_packs = sum(1 for r in results if r["submission_pack"].get("ready"))

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

    excluded_category_counts: Dict[str, int] = {}
    allowed_category_counts: Dict[str, int] = {}

    for r in results:
        excluded_category = r["classification"].get("excluded_category")
        category = r["classification"].get("category", "general_supply")

        if excluded_category:
            excluded_category_counts[excluded_category] = excluded_category_counts.get(excluded_category, 0) + 1
        else:
            allowed_category_counts[category] = allowed_category_counts.get(category, 0) + 1

    excluded_category_breakdown = [
        {"category": category, "count": count}
        for category, count in sorted(excluded_category_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    allowed_category_breakdown = [
        {"category": category, "count": count}
        for category, count in sorted(allowed_category_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    return {
        "total_rfqs": total_rfqs,
        "eligible_rfqs": eligible_rfqs,
        "excluded_rfqs": excluded_rfqs,
        "construction_rfqs": construction_rfqs,
        "can_quote": can_quote,
        "recommended_submit": submit_count,
        "recommended_review": review_count,
        "recommended_skip": skip_count,
        "ready_submission_packs": ready_packs,
        "estimated_pipeline_excl_vat": round(estimated_pipeline_excl_vat, 2),
        "estimated_profit_pipeline": round(estimated_profit_pipeline, 2),
        "excluded_category_breakdown": excluded_category_breakdown,
        "allowed_category_breakdown": allowed_category_breakdown,
    }


@router.get("/health")
def supply_command_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "LMCP Supply Command System",
        "timestamp": datetime.utcnow().isoformat(),
        "message": (
            "Supply classification, pricing, scoring, submission and target control "
            "services are available."
        ),
        "target_model": {
            "wins_target_per_month": SUPPLY_WINS_TARGET_PER_MONTH,
            "min_profit_per_win": SUPPLY_MIN_PROFIT_PER_WIN,
            "monthly_profit_target": SUPPLY_MONTHLY_PROFIT_TARGET,
        },
        "rules": {
            "target_supply_and_delivery_only": True,
            "exclude_medical_consumables": True,
            "exclude_it_equipment": True,
            "exclude_petrol_diesel_fuel": True,
            "exclude_construction_works_installation_maintenance": True,
        },
    }


@router.get("/suppliers")
def list_suppliers() -> Dict[str, Any]:
    suppliers = get_all_suppliers()
    return {
        "count": len(suppliers),
        "suppliers": suppliers,
    }


@router.get("/demo-run")
def supply_demo_run() -> Dict[str, Any]:
    results = [_analyze_single_rfq(rfq) for rfq in DEMO_RFQS]
    summary = _summarize_results(results)

    return {
        "summary": summary,
        "results": results,
    }


@router.get("/live-rfqs")
def get_live_rfqs() -> Dict[str, Any]:
    rfqs = load_live_rfqs()
    return {
        "count": len(rfqs),
        "rfqs": rfqs,
    }


@router.post("/live-rfqs/load")
def load_live_rfqs_from_payload(
    payload: List[Dict[str, Any]] = Body(..., description="List of harvested RFQs")
) -> Dict[str, Any]:
    return append_live_rfqs(payload)


@router.get("/live-run")
def live_supply_run() -> Dict[str, Any]:
    return analyze_live_rfqs()


@router.get("/live-dashboard")
def live_supply_dashboard() -> Dict[str, Any]:
    live = analyze_live_rfqs()
    submission_summary = get_submission_summary()

    actual_wins = _safe_int(submission_summary.get("won", 0))
    actual_profit = _safe_float(submission_summary.get("total_profit_from_wins", 0.0))
    target_control = build_target_control(
        actual_wins=actual_wins,
        actual_profit=actual_profit,
    )

    return {
        "target": {
            "wins_target_per_month": SUPPLY_WINS_TARGET_PER_MONTH,
            "min_profit_per_win": SUPPLY_MIN_PROFIT_PER_WIN,
            "monthly_profit_target": SUPPLY_MONTHLY_PROFIT_TARGET,
            "secured_pipeline_excl_vat": live["summary"]["estimated_pipeline_excl_vat"],
            "secured_profit_pipeline": live["summary"]["estimated_profit_pipeline"],
        },
        "rules": {
            "target_supply_and_delivery_only": True,
            "exclude_medical_consumables": True,
            "exclude_it_equipment": True,
            "exclude_petrol_diesel_fuel": True,
            "exclude_construction_works_installation_maintenance": True,
        },
        "live_summary": live["summary"],
        "submission_pipeline": submission_summary,
        "target_control": target_control,
        "today_money_list": live["today_money_list"],
        "rejected_list": live["rejected_list"],
    }


@router.post("/analyze-rfq")
def analyze_rfq(rfq: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return _analyze_single_rfq(rfq)


@router.post("/analyze-batch")
def analyze_batch(
    rfqs: List[Dict[str, Any]] = Body(..., description="List of RFQs to analyze")
) -> Dict[str, Any]:
    results = [_analyze_single_rfq(rfq) for rfq in rfqs]
    summary = _summarize_results(results)

    return {
        "summary": summary,
        "results": results,
    }


@router.get("/target-control")
def target_control_dashboard() -> Dict[str, Any]:
    submission_summary = get_submission_summary()
    actual_wins = _safe_int(submission_summary.get("won", 0))
    actual_profit = _safe_float(submission_summary.get("total_profit_from_wins", 0.0))

    return build_target_control(
        actual_wins=actual_wins,
        actual_profit=actual_profit,
    )


@router.get("/dashboard")
def revenue_dashboard() -> Dict[str, Any]:
    results = [_analyze_single_rfq(rfq) for rfq in DEMO_RFQS]
    summary = _summarize_results(results)
    submission_summary = get_submission_summary()

    actual_wins = _safe_int(submission_summary.get("won", 0))
    actual_profit = _safe_float(submission_summary.get("total_profit_from_wins", 0.0))
    target_control = build_target_control(
        actual_wins=actual_wins,
        actual_profit=actual_profit,
    )

    today_money_list: List[Dict[str, Any]] = []
    rejected_list: List[Dict[str, Any]] = []

    for r in results:
        classification = r["classification"]
        quote = r["quote"]
        scoring = r["scoring"]
        pack = r["submission_pack"]

        row = {
            "rfq_id": r["rfq"].get("rfq_id"),
            "title": r["rfq"].get("title"),
            "category": classification.get("category"),
            "excluded_category": classification.get("excluded_category"),
            "is_construction": classification.get("is_construction"),
            "score": scoring.get("score"),
            "priority": scoring.get("priority"),
            "action": scoring.get("recommended_action"),
            "profit_floor_passed": scoring.get("profit_floor_passed"),
            "value_excl_vat": quote.get("cost_breakdown", {}).get("quote_total_excl_vat", 0.0),
            "gross_profit": quote.get("cost_breakdown", {}).get("gross_profit", 0.0),
            "ready": pack.get("ready"),
        }

        if scoring.get("recommended_action") == "SUBMIT":
            today_money_list.append(row)
        else:
            rejected_list.append({
                **row,
                "reason": pack.get("reason") or "; ".join(scoring.get("reasons", [])),
            })

    today_money_list.sort(
        key=lambda x: (
            x["action"] != "SUBMIT",
            -_safe_float(x["score"]),
            -_safe_float(x["gross_profit"]),
        )
    )

    rejected_list.sort(
        key=lambda x: (
            x["excluded_category"] is None,
            x["is_construction"] is False,
            x["rfq_id"],
        )
    )

    return {
        "target": {
            "wins_target_per_month": SUPPLY_WINS_TARGET_PER_MONTH,
            "min_profit_per_win": SUPPLY_MIN_PROFIT_PER_WIN,
            "monthly_profit_target": SUPPLY_MONTHLY_PROFIT_TARGET,
            "secured_pipeline_excl_vat": summary["estimated_pipeline_excl_vat"],
            "secured_profit_pipeline": summary["estimated_profit_pipeline"],
        },
        "rules": {
            "target_supply_and_delivery_only": True,
            "exclude_medical_consumables": True,
            "exclude_it_equipment": True,
            "exclude_petrol_diesel_fuel": True,
            "exclude_construction_works_installation_maintenance": True,
        },
        "rfq_intake": {
            "total_demo_rfqs": summary["total_rfqs"],
            "eligible": summary["eligible_rfqs"],
            "excluded": summary["excluded_rfqs"],
            "construction": summary["construction_rfqs"],
            "recommended_submit": summary["recommended_submit"],
            "recommended_review": summary["recommended_review"],
            "recommended_skip": summary["recommended_skip"],
            "ready_submission_packs": summary["ready_submission_packs"],
        },
        "category_breakdown": {
            "allowed_categories": summary["allowed_category_breakdown"],
            "excluded_categories": summary["excluded_category_breakdown"],
        },
        "submission_pipeline": submission_summary,
        "target_control": target_control,
        "today_money_list": today_money_list,
        "rejected_list": rejected_list,
    }


@router.post("/submission/mark")
def mark_submission(
    payload: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    rfq_id = str(payload.get("rfq_id", "")).strip()
    status = str(payload.get("status", "")).strip().lower()
    submitted_by = str(payload.get("submitted_by", "system")).strip()
    notes = str(payload.get("notes", "")).strip()
    category = str(payload.get("category", "")).strip()
    gross_profit = _safe_float(payload.get("gross_profit", 0.0))
    award_value_excl_vat = _safe_float(payload.get("award_value_excl_vat", 0.0))

    if not rfq_id:
        return {"status": "error", "message": "rfq_id is required."}

    if status not in {"submitted", "failed", "pending", "reviewed", "won"}:
        return {
            "status": "error",
            "message": "status must be one of: submitted, failed, pending, reviewed, won.",
        }

    record = mark_submission_status(
        rfq_id=rfq_id,
        status=status,
        submitted_by=submitted_by,
        notes=notes,
        category=category,
        gross_profit=gross_profit,
        award_value_excl_vat=award_value_excl_vat,
    )

    return {
        "status": "ok",
        "record": record,
    }
