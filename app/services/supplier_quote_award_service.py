from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.supplier_quote_ingestion_service import ingest_supplier_quotes
from app.services.supplier_quote_comparison_service import compare_supplier_quotes

def _folder(payload: Dict[str, Any]) -> Path:
    folder = Path(
        payload.get("quote_folder")
        or payload.get("monthly_quote_folder")
        or payload.get("folder_path")
        or "monthly_quotes"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _award_confidence(payload: Dict[str, Any]) -> float:
    recommended = payload.get("recommended_supplier") or {}
    comparison = payload.get("supplier_quote_comparison") or {}
    ranked_rows = comparison.get("ranked_rows") or []

    if not recommended:
        return 0.0

    score = float(recommended.get("total_score") or 0.0)
    extraction_conf = float(recommended.get("extraction_confidence") or 0.0)
    supplier_quotes = int(payload.get("supplier_quote_count") or 0)

    confidence = 0.0
    confidence += min(score, 1.0) * 0.55
    confidence += min(extraction_conf, 1.0) * 0.15

    if recommended.get("compliant") is True:
        confidence += 0.15

    if supplier_quotes >= 3:
        confidence += 0.10
    elif supplier_quotes == 2:
        confidence += 0.06

    if len(ranked_rows) >= 2:
        top = ranked_rows[0]
        second = ranked_rows[1]
        top_total = top.get("total_incl_vat")
        second_total = second.get("total_incl_vat")
        if top_total is not None and second_total is not None and second_total > 0:
            delta = abs(second_total - top_total) / second_total
            confidence += min(delta, 0.10)

    return round(min(confidence, 1.0), 2)


def decide_supplier_award(payload: Dict[str, Any]) -> Dict[str, Any]:
    folder = _folder(payload)
    comparison = payload.get("supplier_quote_comparison") or {}
    recommended = payload.get("recommended_supplier") or {}
    runner_up = payload.get("runner_up_supplier") or {}
    ranked_rows = comparison.get("ranked_rows") or []

    if not recommended:
        award = {
            "award_completed": True,
            "auto_award": False,
            "award_status": "no_recommendation",
            "award_reason": "No supplier recommendation could be determined",
            "awarded_supplier": None,
            "runner_up_supplier": None,
            "award_confidence": 0.0,
            "award_datetime": datetime.utcnow().isoformat() + "Z",
        }
    else:
        award_confidence = _award_confidence(payload)
        compliant = bool(recommended.get("compliant"))
        supplier_quote_count = int(payload.get("supplier_quote_count") or 0)
        score = float(recommended.get("total_score") or 0.0)

        auto_award = (
            compliant
            and supplier_quote_count >= 2
            and score >= 0.65
            and award_confidence >= 0.70
        )

        award_status = "auto_awarded" if auto_award else "manual_review_required"

        reasons = []
        if compliant:
            reasons.append("Recommended supplier is compliant")
        else:
            reasons.append("Recommended supplier is not fully compliant")

        reasons.append(f"Supplier quote count: {supplier_quote_count}")
        reasons.append(f"Comparison score: {score:.3f}")
        reasons.append(f"Award confidence: {award_confidence:.2f}")

        if runner_up:
            rec_total = recommended.get("total_incl_vat")
            runner_total = runner_up.get("total_incl_vat")
            if rec_total is not None and runner_total is not None:
                reasons.append(f"Estimated savings vs runner-up: {runner_total - rec_total:.2f}")

        award = {
            "award_completed": True,
            "auto_award": auto_award,
            "award_status": award_status,
            "award_reason": "; ".join(reasons),
            "awarded_supplier": recommended,
            "runner_up_supplier": runner_up if runner_up else None,
            "award_confidence": award_confidence,
            "award_datetime": datetime.utcnow().isoformat() + "Z",
            "ranked_suppliers": ranked_rows,
        }

    out_path = folder / "supplier_award.json"
    out_path.write_text(json.dumps(award, indent=2, ensure_ascii=False), encoding="utf-8")

    payload["supplier_award"] = award
    payload["supplier_award_status"] = award.get("award_status")
    payload["auto_award"] = award.get("auto_award", False)
    payload["awarded_supplier"] = award.get("awarded_supplier")

    return payload


def run_full_supplier_quote_cycle(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = ingest_supplier_quotes(payload)
    payload = compare_supplier_quotes(payload)
    payload = decide_supplier_award(payload)
    return payload
