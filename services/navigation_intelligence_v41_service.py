"""
LMCP AutoQuote System
V41 Navigation Intelligence Engine

Purpose:
- Consume V40 Clickable Navigation Extractor output.
- Interpret raw PDF navigation signals into usable tender intelligence.
- Identify pricing/BOQ candidates, SBD/MBD pages, declaration pages,
  submission email, specifications, terms of reference, evaluation and closing-date sections.
- Optionally run V40 directly from an input PDF, then interpret the result.

This layer does NOT replace V40. It builds on top of it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import re
import traceback


SERVICE_VERSION = "V41_NAVIGATION_INTELLIGENCE_ENGINE"
DEFAULT_OUTPUT_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "navigation_intelligence_v41"


PRICING_TERMS = [
    "pricing schedule",
    "price schedule",
    "schedule of prices",
    "price list",
    "price quotation",
    "quotation",
    "bill of quantities",
    "boq",
    "financial offer",
    "financial proposal",
    "pricing",
    "total price",
    "amount",
    "vat",
    "unit price",
    "quantity",
]

SBD_TERMS = [
    "sbd",
    "mbd",
    "standard bidding document",
    "municipal bidding document",
]

DECLARATION_TERMS = [
    "declaration",
    "bidder's declaration",
    "preference points claim",
    "local content",
    "interest",
    "conflict",
    "collusive bidding",
    "tax compliance",
]

SUBMISSION_TERMS = [
    "submission",
    "submit",
    "bid submission",
    "quotation submission",
    "email",
    "closing date",
    "closing time",
    "deadline",
]

SPECIFICATION_TERMS = [
    "specification",
    "specifications",
    "scope of work",
    "terms of reference",
    "tor",
    "deliverables",
    "requirements",
]

EVALUATION_TERMS = [
    "evaluation",
    "functionality",
    "threshold",
    "preference points",
    "specific goals",
    "points",
]

FORM_FILLING_TERMS = [
    "must not be typed",
    "black ink",
    "completed in black",
    "handwritten",
    "sign",
    "signature",
]


@dataclass
class V41Candidate:
    page: int
    page_index: int
    text: str
    source: str
    confidence: float
    reason: str
    target_page: Optional[int] = None
    target_kind: str = "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def _contains_any(text: str, terms: List[str]) -> List[str]:
    t = _normalise_text(text).lower()
    return [term for term in terms if term in t]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _candidate_from_item(item: Dict[str, Any], reason: str, confidence: float, page_override: Optional[int] = None) -> V41Candidate:
    page = page_override if page_override is not None else _safe_int(item.get("target_page") or item.get("page") or 0)
    page_index = max(page - 1, 0) if page else _safe_int(item.get("page_index") or 0)

    return V41Candidate(
        page=page,
        page_index=page_index,
        text=_normalise_text(item.get("text")),
        source=_normalise_text(item.get("source")),
        confidence=round(min(max(confidence, 0.0), 1.0), 3),
        reason=reason,
        target_page=item.get("target_page"),
        target_kind=_normalise_text(item.get("target_kind") or "unknown"),
    )


def _dedupe_candidates(candidates: List[V41Candidate]) -> List[V41Candidate]:
    best: Dict[Tuple[int, str], V41Candidate] = {}
    for c in candidates:
        key = (c.page, c.text.lower())
        old = best.get(key)
        if old is None or c.confidence > old.confidence:
            best[key] = c
    return sorted(best.values(), key=lambda x: (-x.confidence, x.page, x.text.lower()))


def _page_scores(items: List[Dict[str, Any]], terms: List[str], base: float = 0.35) -> List[V41Candidate]:
    candidates: List[V41Candidate] = []
    for item in items:
        text = _normalise_text(item.get("text"))
        hits = _contains_any(text, terms)
        if not hits:
            continue

        item_conf = _safe_float(item.get("confidence"), 0.35)
        target_page = item.get("target_page")
        source = _normalise_text(item.get("source"))

        if isinstance(target_page, int) and target_page > 0:
            page = target_page
            confidence = max(item_conf, base + 0.25 + min(0.2, 0.04 * len(hits)))
            reason = f"matched {', '.join(hits[:5])}; target page available"
        else:
            page = _safe_int(item.get("page") or 0)
            confidence = max(item_conf, base + min(0.2, 0.04 * len(hits)))
            reason = f"matched {', '.join(hits[:5])}; using source page"

        if source == "pdf_link_annotation":
            confidence += 0.08

        candidates.append(_candidate_from_item(item, reason, confidence, page_override=page))

    return _dedupe_candidates(candidates)


def _extract_submission_emails(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}

    for item in items:
        text = _normalise_text(item.get("text"))
        uri = _normalise_text(item.get("target_uri"))
        email = _normalise_text(item.get("target_email"))
        source_blob = f"{text} {uri} {email}".replace("mailto:", " ")

        emails = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", source_blob, flags=re.I)
        for e in emails:
            clean = e.lower().strip(" .;,%")
            score = 0.72
            reason_bits = ["email detected"]
            if "bid" in clean or "tender" in clean or "quote" in clean:
                score += 0.15
                reason_bits.append("procurement-style address")
            if item.get("source") == "pdf_link_annotation":
                score += 0.08
                reason_bits.append("clickable mailto/link")
            if _contains_any(text, SUBMISSION_TERMS):
                score += 0.05
                reason_bits.append("submission context")

            existing = found.get(clean)
            row = {
                "email": clean,
                "page": _safe_int(item.get("page") or 0),
                "source": item.get("source"),
                "text": text,
                "confidence": round(min(score, 0.98), 3),
                "reason": "; ".join(reason_bits),
            }
            if existing is None or row["confidence"] > existing["confidence"]:
                found[clean] = row

    return sorted(found.values(), key=lambda x: (-x["confidence"], x["email"]))


def _detect_form_filling_instruction(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    hits: List[Dict[str, Any]] = []
    for item in items:
        text = _normalise_text(item.get("text"))
        matched = _contains_any(text, FORM_FILLING_TERMS)
        if not matched:
            continue
        hits.append({
            "page": _safe_int(item.get("page") or 0),
            "text": text,
            "matched": matched,
            "confidence": round(max(_safe_float(item.get("confidence"), 0.5), 0.7), 3),
        })

    must_handwrite = any(
        "must not be typed" in _normalise_text(h.get("text")).lower()
        or "black ink" in _normalise_text(h.get("text")).lower()
        or "completed in black" in _normalise_text(h.get("text")).lower()
        for h in hits
    )

    return {
        "must_handwrite_forms": must_handwrite,
        "instruction_hits": hits[:10],
        "recommended_engine": "sbd_intelligence_handwriting_flow" if must_handwrite else "standard_form_completion_flow",
    }


def _infer_page_windows(candidates: List[V41Candidate], page_count: int, spread: int = 1) -> List[int]:
    pages = set()
    for c in candidates:
        if c.page <= 0:
            continue
        for p in range(max(1, c.page - spread), min(page_count, c.page + spread) + 1):
            pages.add(p)
    return sorted(pages)


def _pricing_fallback_from_document_context(items: List[Dict[str, Any]], page_count: int) -> List[V41Candidate]:
    """
    Some RFQs have no explicit 'pricing schedule' heading. This fallback looks for
    quantity/unit/VAT/amount wording and RFQ/quotation context.
    """
    candidates: List[V41Candidate] = []
    weak_terms = ["quantity", "qty", "unit", "amount", "total", "vat", "quote", "quotation", "rfq"]

    for item in items:
        text = _normalise_text(item.get("text"))
        hits = _contains_any(text, weak_terms)
        if len(hits) < 2:
            continue

        page = _safe_int(item.get("target_page") or item.get("page") or 0)
        if not page:
            continue

        score = 0.46 + min(0.18, len(hits) * 0.03)
        if page <= 5:
            score -= 0.05
        candidates.append(_candidate_from_item(
            item,
            f"fallback pricing context matched {', '.join(hits[:5])}",
            score,
            page_override=page,
        ))

    return _dedupe_candidates(candidates)


def build_navigation_intelligence(v40_payload: Dict[str, Any]) -> Dict[str, Any]:
    started_at = _now_iso()
    items = v40_payload.get("items") or []
    page_count = _safe_int(v40_payload.get("page_count") or 0)

    pricing_candidates = _page_scores(items, PRICING_TERMS, base=0.42)
    if not pricing_candidates:
        pricing_candidates = _pricing_fallback_from_document_context(items, page_count)

    sbd_candidates = _page_scores(items, SBD_TERMS, base=0.48)
    declaration_candidates = _page_scores(items, DECLARATION_TERMS, base=0.44)
    submission_candidates = _page_scores(items, SUBMISSION_TERMS, base=0.40)
    specification_candidates = _page_scores(items, SPECIFICATION_TERMS, base=0.44)
    evaluation_candidates = _page_scores(items, EVALUATION_TERMS, base=0.44)

    submission_emails = _extract_submission_emails(items)
    form_filling = _detect_form_filling_instruction(items)

    sbd_pages = _infer_page_windows(sbd_candidates, page_count, spread=0)
    declaration_pages = _infer_page_windows(declaration_candidates, page_count, spread=0)
    pricing_pages = _infer_page_windows(pricing_candidates, page_count, spread=1)
    specification_pages = _infer_page_windows(specification_candidates, page_count, spread=1)
    evaluation_pages = _infer_page_windows(evaluation_candidates, page_count, spread=1)
    submission_pages = _infer_page_windows(submission_candidates, page_count, spread=1)

    primary_submission_email = submission_emails[0]["email"] if submission_emails else None

    confidence = {
        "pricing": round(pricing_candidates[0].confidence if pricing_candidates else 0.0, 3),
        "sbd": round(sbd_candidates[0].confidence if sbd_candidates else 0.0, 3),
        "declaration": round(declaration_candidates[0].confidence if declaration_candidates else 0.0, 3),
        "submission_email": round(submission_emails[0]["confidence"] if submission_emails else 0.0, 3),
        "specification": round(specification_candidates[0].confidence if specification_candidates else 0.0, 3),
        "evaluation": round(evaluation_candidates[0].confidence if evaluation_candidates else 0.0, 3),
    }

    recommended_next_actions: List[str] = []
    if pricing_pages:
        recommended_next_actions.append("Run pricing/table extractor against pricing_pages.")
    else:
        recommended_next_actions.append("Run page-level table scan because no clear pricing page was detected.")
    if sbd_pages or declaration_pages:
        recommended_next_actions.append("Run SBD/form intelligence against sbd_pages and declaration_pages.")
    if primary_submission_email:
        recommended_next_actions.append("Use detected submission email for email submission routing.")
    if form_filling["must_handwrite_forms"]:
        recommended_next_actions.append("Use handwriting/SBD intelligence flow because buyer says forms must not be typed.")

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "message": "Navigation intelligence completed.",
        "input_pdf": v40_payload.get("input_pdf"),
        "buyer_rfq_number": v40_payload.get("buyer_rfq_number"),
        "page_count": page_count,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "v40_summary": v40_payload.get("summary", {}),
        "intelligence": {
            "primary_submission_email": primary_submission_email,
            "submission_emails": submission_emails,
            "pricing_pages": pricing_pages,
            "sbd_pages": sbd_pages,
            "declaration_pages": declaration_pages,
            "submission_pages": submission_pages,
            "specification_pages": specification_pages,
            "evaluation_pages": evaluation_pages,
            "form_filling": form_filling,
            "confidence": confidence,
            "recommended_next_actions": recommended_next_actions,
        },
        "candidates": {
            "pricing": [asdict(c) for c in pricing_candidates[:20]],
            "sbd": [asdict(c) for c in sbd_candidates[:30]],
            "declaration": [asdict(c) for c in declaration_candidates[:30]],
            "submission": [asdict(c) for c in submission_candidates[:30]],
            "specification": [asdict(c) for c in specification_candidates[:30]],
            "evaluation": [asdict(c) for c in evaluation_candidates[:30]],
        },
    }
    return result


def analyse_v40_json(
    v40_json_path: str,
    buyer_rfq_number: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = _now_iso()
    try:
        path = Path(v40_json_path)
        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V40 JSON file not found.",
                "v40_json_path": str(path),
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        v40_payload = json.loads(path.read_text(encoding="utf-8"))
        if buyer_rfq_number and not v40_payload.get("buyer_rfq_number"):
            v40_payload["buyer_rfq_number"] = buyer_rfq_number

        result = build_navigation_intelligence(v40_payload)

        out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if not out_root.is_absolute():
            out_root = Path.cwd() / out_root
        out_root.mkdir(parents=True, exist_ok=True)

        safe_rfq = re.sub(r"[^A-Za-z0-9_.-]+", "-", result.get("buyer_rfq_number") or path.stem).strip("-") or "RFQ"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = out_root / f"{safe_rfq}__{SERVICE_VERSION}__{timestamp}.json"
        result["output_json"] = str(out_path)
        result["v40_json_path"] = str(path)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V41 analysis failed.",
            "v40_json_path": v40_json_path,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def analyse_pdf_with_v40_then_v41(
    input_pdf: str,
    buyer_rfq_number: Optional[str] = None,
    max_pages_scan: int = 12,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function: run V40 extractor, then V41 interpretation.
    """
    started_at = _now_iso()
    try:
        from app.services.clickable_navigation_v40_service import extract_clickable_navigation

        v40_result = extract_clickable_navigation(
            input_pdf=input_pdf,
            buyer_rfq_number=buyer_rfq_number,
            output_dir=None,
            max_pages_scan=max_pages_scan,
            include_low_confidence=True,
        )

        if v40_result.get("status") != "ok":
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "V40 extraction failed, so V41 could not continue.",
                "v40_result": v40_result,
                "started_at": started_at,
                "completed_at": _now_iso(),
            }

        result = build_navigation_intelligence(v40_result)

        out_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        if not out_root.is_absolute():
            out_root = Path.cwd() / out_root
        out_root.mkdir(parents=True, exist_ok=True)

        safe_rfq = re.sub(r"[^A-Za-z0-9_.-]+", "-", result.get("buyer_rfq_number") or "RFQ").strip("-") or "RFQ"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = out_root / f"{safe_rfq}__{SERVICE_VERSION}__{timestamp}.json"
        result["output_json"] = str(out_path)
        result["v40_output_json"] = v40_result.get("output_json")
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        return result

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "V41 PDF analysis failed.",
            "input_pdf": input_pdf,
            "buyer_rfq_number": buyer_rfq_number,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "completed_at": _now_iso(),
        }


def get_navigation_intelligence_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "service": "V41 Navigation Intelligence Engine",
        "description": "Interprets V40 navigation extraction into pricing pages, SBD pages, submission intelligence, section pages and recommended next actions.",
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "endpoints": {
            "status": "/v41-navigation-intelligence/status",
            "analyse_v40_json": "/v41-navigation-intelligence/analyse-v40-json",
            "analyse_pdf": "/v41-navigation-intelligence/analyse-pdf",
        },
        "ready": True,
    }
