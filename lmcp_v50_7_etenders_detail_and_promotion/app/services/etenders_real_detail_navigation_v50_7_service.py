"""
LMCP V50.7 - eTenders Real Detail Navigation Engine

Purpose:
- Avoid generic eTenders listing downloads.
- Find real tender-specific detail/document URLs.
- Reject weak / generic document candidates.
- Produce a clean navigation result that can be consumed by the harvester,
  document acquisition engine, or autonomous radar.

Drop-in file:
    app/services/etenders_real_detail_navigation_v50_7_service.py
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup


SERVICE_VERSION = "V50.7_ETENDERS_REAL_DETAIL_NAVIGATION"


GENERIC_ETENDERS_URLS = {
    "https://www.etenders.gov.za",
    "https://www.etenders.gov.za/",
    "https://www.etenders.gov.za/Home/opportunities",
    "https://www.etenders.gov.za/Home/opportunities?id=1",
}

SUPPORTED_DOC_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z"
)

REFERENCE_PATTERNS = [
    r"\b[A-Z]{2,10}[-/][A-Z]{2,10}[-/][A-Z0-9]{2,10}[-/]\d{2,5}\b",
    r"\b[A-Z]{2,10}[-/]\d{2,5}[-/]\d{2,4}\b",
    r"\bRFQ\s*[-:/]?\s*\d{2,6}[/.-]?\d{0,4}\b",
    r"\bRFP\s*[-:/]?\s*\d{2,6}[/.-]?\d{0,4}\b",
    r"\bBID\s*[-:/]?\s*\d{2,6}[/.-]?\d{0,4}\b",
    r"\bTENDER\s*[-:/]?\s*\d{2,6}[/.-]?\d{0,4}\b",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_lower(value: Any) -> str:
    return _clean_text(value).lower()


def _normalise_url(url: str, base_url: str = "https://www.etenders.gov.za") -> str:
    url = html.unescape(_clean_text(url))
    if not url:
        return ""
    return urljoin(base_url, url)


def _is_generic_etenders_url(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if clean in GENERIC_ETENDERS_URLS:
        return True
    if parsed.path.lower() in {"", "/", "/home", "/home/opportunities"}:
        return True
    return False


def _looks_like_document_url(url: str) -> bool:
    low = _safe_lower(url)
    path = urlparse(low).path
    if any(path.endswith(ext) for ext in SUPPORTED_DOC_EXTENSIONS):
        return True
    if "downloadspec" in low or "download" in low or "documentid=" in low:
        return True
    return False


def _extract_references(*values: Any) -> List[str]:
    blob = " ".join(_clean_text(v) for v in values if v is not None)
    refs: List[str] = []
    for pat in REFERENCE_PATTERNS:
        for match in re.findall(pat, blob, flags=re.I):
            ref = _clean_text(match).upper()
            ref = re.sub(r"\s+", "", ref)
            if ref and ref not in refs:
                refs.append(ref)
    return refs


def _tokenise_reference(value: str) -> List[str]:
    value = _clean_text(value).upper()
    parts = re.split(r"[^A-Z0-9]+", value)
    return [p for p in parts if len(p) >= 2]


def _reference_overlap_score(candidate_text: str, references: List[str]) -> float:
    if not references:
        return 0.0

    candidate = _clean_text(unquote(candidate_text)).upper()
    if not candidate:
        return 0.0

    best = 0.0
    for ref in references:
        ref_clean = _clean_text(ref).upper()
        if ref_clean and ref_clean in candidate:
            best = max(best, 1.0)
            continue

        tokens = _tokenise_reference(ref_clean)
        if not tokens:
            continue

        hits = sum(1 for t in tokens if t in candidate)
        score = hits / max(len(tokens), 1)
        best = max(best, score)

    return round(best, 4)


def _get_html(url: str, timeout: int = 25) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    started = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return {
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get("content-type", ""),
            "text": response.text or "",
            "elapsed_seconds": round(time.time() - started, 3),
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 0,
            "final_url": url,
            "content_type": "",
            "text": "",
            "elapsed_seconds": round(time.time() - started, 3),
            "error": str(exc),
        }


@dataclass
class CandidateLink:
    url: str
    label: str
    score: float
    reasons: List[str]
    reference_overlap: float
    is_document: bool
    is_generic: bool


def _score_link(
    url: str,
    label: str,
    page_text: str,
    references: List[str],
    title: str,
    source_page: str,
) -> CandidateLink:
    low_url = _safe_lower(url)
    low_label = _safe_lower(label)
    is_doc = _looks_like_document_url(url)
    is_generic = _is_generic_etenders_url(url)

    score = 0.0
    reasons: List[str] = []

    if is_generic:
        score -= 0.65
        reasons.append("generic_etenders_url")

    if is_doc:
        score += 0.35
        reasons.append("document_or_download_url")

    if "downloadspec" in low_url:
        score += 0.15
        reasons.append("downloadspec_url")

    if "documentid=" in low_url:
        score += 0.05
        reasons.append("document_id_present")

    if any(k in low_label for k in ("download", "document", "spec", "bid", "tender", "rfq", "rfp", "sbd")):
        score += 0.2
        reasons.append("procurement_link_label")

    combined = " ".join([url, label, page_text[:2000], title])
    overlap = _reference_overlap_score(combined, references)

    if overlap >= 1.0:
        score += 0.5
        reasons.append("exact_reference_overlap")
    elif overlap >= 0.5:
        score += 0.25
        reasons.append("partial_reference_overlap")
    elif references and is_doc:
        score -= 0.25
        reasons.append("document_without_reference_overlap")

    # eTenders home page sometimes exposes many documentId links unrelated to a row.
    # Keep them visible, but make them weak unless reference evidence exists.
    if "downloadspec" in low_url and overlap < 0.5 and _is_generic_etenders_url(source_page):
        score -= 0.35
        reasons.append("weak_generic_downloadspec_rejected")

    return CandidateLink(
        url=url,
        label=label,
        score=round(score, 4),
        reasons=reasons,
        reference_overlap=overlap,
        is_document=is_doc,
        is_generic=is_generic,
    )


def analyse_etenders_detail_navigation(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    title = _clean_text(payload.get("title") or payload.get("description") or "")
    buyer_rfq_number = _clean_text(
        payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or payload.get("reference_number")
        or ""
    )

    seed_urls = []
    for key in ("detail_url", "document_url", "source_url", "portal_url", "url"):
        url = _normalise_url(payload.get(key) or "")
        if url and url not in seed_urls:
            seed_urls.append(url)

    if not seed_urls:
        seed_urls = ["https://www.etenders.gov.za/Home/opportunities?id=1"]

    references = _extract_references(title, buyer_rfq_number, payload.get("raw_text"), payload.get("description"))

    pages: List[Dict[str, Any]] = []
    all_candidates: List[CandidateLink] = []

    for seed in seed_urls[:4]:
        page = _get_html(seed)
        pages.append({
            "url": seed,
            "ok": page["ok"],
            "status_code": page["status_code"],
            "final_url": page["final_url"],
            "content_type": page["content_type"],
            "elapsed_seconds": page["elapsed_seconds"],
            "error": page["error"],
        })

        if not page["ok"] or "html" not in _safe_lower(page["content_type"]):
            continue

        soup = BeautifulSoup(page["text"], "html.parser")
        page_text = _clean_text(soup.get_text(" "))

        # Search row/card containers first.
        row_nodes = soup.select("tr, .card, .tender, .opportunity, .row, li")
        matched_rows = []
        title_tokens = [t for t in re.split(r"\W+", title.lower()) if len(t) >= 4][:12]

        for node in row_nodes:
            node_text = _clean_text(node.get_text(" "))
            node_low = node_text.lower()
            token_hits = sum(1 for t in title_tokens if t in node_low)
            ref_overlap = _reference_overlap_score(node_text, references)

            if ref_overlap >= 0.5 or token_hits >= 3:
                matched_rows.append((node, node_text, token_hits, ref_overlap))

        search_nodes = matched_rows if matched_rows else [(soup, page_text, 0, 0.0)]

        for node, node_text, token_hits, ref_overlap in search_nodes[:8]:
            for a in node.find_all("a", href=True):
                url = _normalise_url(a.get("href"), page["final_url"])
                label = _clean_text(a.get_text(" ") or a.get("title") or a.get("aria-label") or "")
                candidate = _score_link(
                    url=url,
                    label=label,
                    page_text=node_text,
                    references=references,
                    title=title,
                    source_page=seed,
                )

                if token_hits >= 3:
                    candidate.score = round(candidate.score + 0.15, 4)
                    candidate.reasons.append("row_title_token_match")

                if ref_overlap >= 0.5:
                    candidate.score = round(candidate.score + 0.2, 4)
                    candidate.reasons.append("row_reference_match")

                all_candidates.append(candidate)

    # De-duplicate by URL, keeping best scoring instance.
    dedup: Dict[str, CandidateLink] = {}
    for c in all_candidates:
        if c.url not in dedup or c.score > dedup[c.url].score:
            dedup[c.url] = c

    candidates = sorted(dedup.values(), key=lambda x: x.score, reverse=True)

    strong_document_links = [
        c for c in candidates
        if c.is_document and c.score >= 0.35 and not ("weak_generic_downloadspec_rejected" in c.reasons)
    ]

    strong_detail_links = [
        c for c in candidates
        if not c.is_document and c.score >= 0.25 and not c.is_generic
    ]

    recommended_action = "manual_review"
    if strong_document_links:
        recommended_action = "download_matched_documents"
    elif strong_detail_links:
        recommended_action = "navigate_detail_links"
    elif candidates:
        recommended_action = "reject_generic_or_weak_links"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "analysed_at": _now(),
        "title": title,
        "buyer_rfq_number": buyer_rfq_number,
        "references": references,
        "seed_urls": seed_urls,
        "pages": pages,
        "candidate_count": len(candidates),
        "strong_document_count": len(strong_document_links),
        "strong_detail_count": len(strong_detail_links),
        "candidate_links": [asdict(c) for c in candidates[:30]],
        "recommended_document_links": [asdict(c) for c in strong_document_links[:10]],
        "recommended_detail_links": [asdict(c) for c in strong_detail_links[:10]],
        "recommended_action": recommended_action,
        "safe_to_download": bool(strong_document_links),
        "safe_to_auto_quote": False,
        "notes": [
            "Generic eTenders listing links are intentionally down-scored.",
            "DownloadSpec documentId links require row/reference evidence before promotion.",
            "This service should run before document acquisition for eTenders items.",
        ],
    }


def get_v50_7_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "capabilities": [
            "generic_etenders_listing_rejection",
            "row_or_card_title_matching",
            "reference_overlap_scoring",
            "weak_downloadspec_rejection",
            "matched_document_link_recommendation",
        ],
    }
