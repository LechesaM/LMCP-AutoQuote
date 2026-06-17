from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin
import re
import requests


SERVICE_VERSION = "V49_REAL_RFQ_DETAIL_NAVIGATION_ENGINE"

DETAIL_KEYWORDS = [
    "view", "details", "more", "download", "documents", "specification",
    "rfq", "rfp", "bid", "tender", "quotation"
]

GENERIC_BLOCKERS = [
    "administrative and support activities",
    "manufacturing",
    "construction",
    "other service activities",
    "community social and personal services",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _extract_references(text: str) -> List[str]:
    patterns = [
        r"\bFIN-SCM-[A-Z0-9-]+\b",
        r"\bRFQ[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bRFP[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bSCM[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\bBID[\s:/#-]*(?:NO|NUMBER|REF)?[\s:/#-]*[A-Z0-9][A-Z0-9./-]{2,}\b",
        r"\b[TQ]\d{2,}[-/][A-Z0-9./-]+\b",
    ]

    bad = {
        "bid is", "bid for", "bid number", "bid description",
        "bid validity", "bid closing", "bid documents",
        "bid box", "bid response", "bid to",
    }

    found: List[str] = []
    for p in patterns:
        for m in re.findall(p, text, flags=re.I):
            ref = re.sub(r"\s+", " ", _clean(m)).strip(" .,:;")
            if not ref:
                continue
            if ref.lower() in bad:
                continue
            if len(ref) < 6:
                continue
            if ref not in found:
                found.append(ref)
    return found[:10]


def _extract_dates(text: str) -> List[str]:
    found = []
    for m in re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", text):
        if m not in found:
            found.append(m)
    return found[:10]


def _extract_links(html: str, base_url: str, target_refs: List[str] | None = None) -> List[Dict[str, Any]]:
    target_refs = target_refs or []
    links: List[Dict[str, Any]] = []
    for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
        label_clean = re.sub(r"<[^>]+>", " ", label)
        label_clean = re.sub(r"\s+", " ", label_clean).strip()
        full = urljoin(base_url, href)
        low = (full + " " + label_clean).lower()

        score = 0
        reasons = []

        if any(k in low for k in DETAIL_KEYWORDS):
            score += 30
            reasons.append("detail_keyword")

        if any(ext in low for ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"]):
            score += 40
            reasons.append("document_extension")

        if "download" in low:
            score += 20
            reasons.append("download_signal")

        if "details" in low or "view" in low:
            score += 15
            reasons.append("detail_signal")

        for ref in target_refs:
            ref_low = ref.lower()
            if ref_low and ref_low in low:
                score += 100
                reasons.append("matched_target_reference")
                break

        if score > 0:
            links.append({
                "url": full,
                "label": label_clean,
                "score": score,
                "reasons": reasons,
            })

    links.sort(key=lambda x: x.get("score", 0), reverse=True)
    return links[:50]


def analyse_rfq_detail_navigation(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = _clean(payload.get("url") or payload.get("source_url") or payload.get("document_url"))
    title = _clean(payload.get("title") or payload.get("buyer_rfq_number"))
    raw_text = _clean(payload.get("raw_text") or payload.get("description") or title)

    result: Dict[str, Any] = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "analysed_at": _now(),
        "input_url": url,
        "title": title,
        "generic_listing_detected": False,
        "strong_rfq_identity": False,
        "references": [],
        "closing_dates": [],
        "candidate_detail_links": [],
        "candidate_document_links": [],
        "recommended_action": "manual_review",
    }

    combined = f"{title} {raw_text}".lower()

    if any(term in combined for term in GENERIC_BLOCKERS):
        result["generic_listing_detected"] = True

    explicit_refs = []
    for key in ["buyer_rfq_number", "rfq_number", "reference_number"]:
        val = _clean(payload.get(key))
        if val and val.lower() not in {"unknown", "n/a", "none"}:
            explicit_refs.append(val)

    refs = []
    for r in explicit_refs + _extract_references(f"{title} {raw_text}"):
        if r not in refs:
            refs.append(r)
    dates = _extract_dates(f"{title} {raw_text}")

    result["references"] = refs
    result["closing_dates"] = dates
    result["strong_rfq_identity"] = bool(refs)

    if not url:
        result.update({
            "status": "no_url",
            "recommended_action": "skip_no_url",
        })
        return result

    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "LMCP-AutoQuote-V49/1.0"})
        result["http_status"] = resp.status_code
        result["content_type"] = resp.headers.get("content-type", "")

        if resp.status_code >= 400:
            result.update({
                "status": "http_error",
                "recommended_action": "skip_http_error",
            })
            return result

        html = resp.text or ""
        page_text = re.sub(r"<[^>]+>", " ", html)
        page_text = re.sub(r"\s+", " ", page_text).strip()

        page_refs = _extract_references(page_text)
        page_dates = _extract_dates(page_text)

        merged_refs = []
        for r in refs + page_refs:
            if r not in merged_refs:
                merged_refs.append(r)

        merged_dates = []
        for d in dates + page_dates:
            if d not in merged_dates:
                merged_dates.append(d)

        result["references"] = merged_refs[:10]
        result["closing_dates"] = merged_dates[:10]
        result["strong_rfq_identity"] = bool(result["references"])

        links = _extract_links(html, url, explicit_refs)
        result["candidate_detail_links"] = [
            x for x in links
            if not any(ext in x["url"].lower() for ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"])
        ][:20]
        result["candidate_document_links"] = [
            x for x in links
            if any(ext in x["url"].lower() for ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"])
        ][:20]

        explicit_ref_match = False
        for link in result["candidate_document_links"]:
            link_low = str(link.get("url") or "").lower() + " " + str(link.get("label") or "").lower()
            for ref in explicit_refs:
                if ref and ref.lower() in link_low:
                    explicit_ref_match = True
                    link["explicit_reference_match"] = True

        result["explicit_reference_document_match"] = explicit_ref_match

        if result["strong_rfq_identity"] and result["candidate_document_links"] and explicit_ref_match:
            result["recommended_action"] = "promote_to_document_acquisition"
        elif result["strong_rfq_identity"] and result["candidate_document_links"] and not explicit_ref_match:
            result["recommended_action"] = "navigate_detail_links_target_reference_missing"
        elif result["strong_rfq_identity"] and result["candidate_detail_links"]:
            result["recommended_action"] = "navigate_detail_links"
        elif result["generic_listing_detected"]:
            result["recommended_action"] = "block_generic_listing"
        else:
            result["recommended_action"] = "manual_review"

        return result

    except Exception as exc:
        result.update({
            "status": "error",
            "error": str(exc),
            "recommended_action": "manual_review",
        })
        return result


def get_v49_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "engine": "Real RFQ Detail Navigation Engine",
        "purpose": "Navigate from listing pages into true RFQ detail/document links before pricing or submission.",
        "ready": True,
        "updated_at": _now(),
    }
