from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _tokenize(value: str) -> List[str]:
    return [tok for tok in _normalize_text(value).split() if len(tok) > 2]


def _jaccard(a: str, b: str) -> float:
    sa = set(_tokenize(a))
    sb = set(_tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa | sb), 1)


def _parse_days_from_lead_time(lead_time: Optional[str]) -> Optional[int]:
    if not lead_time:
        return None

    text = lead_time.lower()

    # business days / working days / days
    match = re.search(r"(\d+)\s*(?:business|working)?\s*days?", text)
    if match:
        return int(match.group(1))

    # weeks
    match = re.search(r"(\d+)\s*weeks?", text)
    if match:
        return int(match.group(1)) * 7

    # in stock / immediate
    if any(word in text for word in ["in stock", "immediate", "available now", "ready stock"]):
        return 1

    return None


def _extract_buyer_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rfq = payload.get("rfq") or payload
    items = rfq.get("items") or payload.get("items") or []
    normalized: List[Dict[str, Any]] = []

    for item in items:
        if isinstance(item, dict):
            desc = (
                item.get("description")
                or item.get("item_description")
                or item.get("name")
                or item.get("title")
                or ""
            )
            qty = item.get("quantity") or item.get("qty")
            normalized.append({"description": str(desc), "quantity": qty})
        else:
            normalized.append({"description": str(item), "quantity": None})

    return normalized


def _coverage_score(buyer_items: List[Dict[str, Any]], supplier_items: List[Dict[str, Any]]) -> float:
    if not buyer_items:
        return 1.0
    if not supplier_items:
        return 0.0

    supplier_descs = [str(x.get("description") or "") for x in supplier_items]
    matched = 0

    for buyer_item in buyer_items:
        buyer_desc = buyer_item.get("description") or ""
        best = 0.0
        for supp_desc in supplier_descs:
            score = _jaccard(buyer_desc, supp_desc)
            if score > best:
                best = score
        if best >= 0.25:
            matched += 1

    return round(matched / max(len(buyer_items), 1), 2)


def _commercial_score(total: Optional[float], min_total: Optional[float], max_total: Optional[float]) -> float:
    if total is None or min_total is None or max_total is None:
        return 0.0
    if math.isclose(max_total, min_total):
        return 1.0
    # lower is better
    return round((max_total - total) / (max_total - min_total), 2)


def _lead_time_score(days: Optional[int]) -> float:
    if days is None:
        return 0.5
    if days <= 1:
        return 1.0
    if days <= 3:
        return 0.9
    if days <= 7:
        return 0.8
    if days <= 14:
        return 0.6
    if days <= 21:
        return 0.4
    return 0.2


def _confidence_score(extraction_confidence: Optional[float]) -> float:
    if extraction_confidence is None:
        return 0.0
    return max(0.0, min(float(extraction_confidence), 1.0))


def _compliance_flags(quote: Dict[str, Any], buyer_items: List[Dict[str, Any]]) -> Tuple[bool, List[str], float]:
    flags: List[str] = []
    compliant = True

    total = quote.get("total_incl_vat")
    if total is None or total <= 0:
        compliant = False
        flags.append("Missing total price")

    coverage = _coverage_score(buyer_items, quote.get("items") or [])
    if buyer_items and coverage < 0.5:
        compliant = False
        flags.append(f"Low item coverage ({coverage:.0%})")

    if (quote.get("extraction_confidence") or 0) < 0.35:
        compliant = False
        flags.append("Low extraction confidence")

    return compliant, flags, coverage


def compare_supplier_quotes(payload: Dict[str, Any]) -> Dict[str, Any]:
    folder = Path(
        payload.get("quote_folder")
        or payload.get("monthly_quote_folder")
        or payload.get("folder_path")
        or "monthly_quotes"
    )
    folder.mkdir(parents=True, exist_ok=True)

    quotes = payload.get("supplier_quotes") or (payload.get("supplier_quote_ingestion") or {}).get("supplier_quotes") or []
    buyer_items = _extract_buyer_items(payload)

    totals = [q.get("total_incl_vat") for q in quotes if q.get("total_incl_vat") is not None]
    min_total = min(totals) if totals else None
    max_total = max(totals) if totals else None

    comparison_rows: List[Dict[str, Any]] = []
    best_candidate: Optional[Dict[str, Any]] = None

    for quote in quotes:
        compliant, compliance_flags, coverage = _compliance_flags(quote, buyer_items)
        total = quote.get("total_incl_vat")
        lead_days = _parse_days_from_lead_time(quote.get("lead_time"))

        compliance_score = 1.0 if compliant else max(0.0, 1.0 - (0.35 * len(compliance_flags)))
        price_score = _commercial_score(total, min_total, max_total)
        delivery_score = _lead_time_score(lead_days)
        extraction_score = _confidence_score(quote.get("extraction_confidence"))

        total_score = round(
            (0.35 * compliance_score)
            + (0.35 * price_score)
            + (0.15 * delivery_score)
            + (0.10 * coverage)
            + (0.05 * extraction_score),
            3,
        )

        row = {
            "supplier_name": quote.get("supplier_name"),
            "pdf_filename": quote.get("pdf_filename"),
            "quote_number": quote.get("quote_number"),
            "quote_date": quote.get("quote_date"),
            "total_incl_vat": total,
            "lead_time": quote.get("lead_time"),
            "lead_time_days": lead_days,
            "coverage_score": coverage,
            "extraction_confidence": quote.get("extraction_confidence"),
            "compliant": compliant,
            "compliance_flags": compliance_flags,
            "compliance_score": round(compliance_score, 2),
            "price_score": price_score,
            "delivery_score": delivery_score,
            "total_score": total_score,
        }
        comparison_rows.append(row)

    # Winner logic:
    # 1. compliant only
    # 2. highest total_score
    # 3. lower price breaks ties
    compliant_rows = [r for r in comparison_rows if r["compliant"]]
    ranked_rows = sorted(
        compliant_rows if compliant_rows else comparison_rows,
        key=lambda r: (
            -(r.get("total_score") or 0),
            r.get("total_incl_vat") if r.get("total_incl_vat") is not None else float("inf"),
        ),
    )

    if ranked_rows:
        best_candidate = ranked_rows[0]

    second_candidate = ranked_rows[1] if len(ranked_rows) > 1 else None

    savings_vs_second = None
    if best_candidate and second_candidate:
        best_total = best_candidate.get("total_incl_vat")
        second_total = second_candidate.get("total_incl_vat")
        if best_total is not None and second_total is not None:
            savings_vs_second = round(second_total - best_total, 2)

    comparison = {
        "comparison_completed": True,
        "quote_folder": str(folder),
        "buyer_item_count": len(buyer_items),
        "supplier_quote_count": len(quotes),
        "comparison_rows": comparison_rows,
        "ranked_rows": ranked_rows,
        "recommended_supplier": best_candidate,
        "runner_up_supplier": second_candidate,
        "estimated_savings_vs_runner_up": savings_vs_second,
    }

    out_path = folder / "quote_comparison.json"
    out_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")

    payload["supplier_quote_comparison"] = comparison
    payload["comparison_completed"] = True
    payload["recommended_supplier"] = best_candidate
    payload["runner_up_supplier"] = second_candidate

    return payload
