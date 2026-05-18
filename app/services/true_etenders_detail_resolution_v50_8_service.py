"""
LMCP V50.8 - True eTenders Detail Resolution Engine

Purpose:
- Use Playwright to inspect eTenders listing/table rows.
- Match a harvested RFQ title against visible rows.
- Extract row-local detail/download links only.
- Reject global/generic DownloadSpec links unless row/title evidence exists.
- Produce a safe detail/document resolution result for the autonomous harvester.

Drop-in:
    app/services/true_etenders_detail_resolution_v50_8_service.py
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse


SERVICE_VERSION = "V50.8_TRUE_ETENDERS_DETAIL_RESOLUTION"

ETENDERS_BASE = "https://www.etenders.gov.za"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"

SUPPORTED_DOCUMENT_HINTS = (
    "download",
    "downloadspec",
    "documentid",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
)

GENERIC_LABELS = {
    "home",
    "tenders",
    "tender opportunities",
    "currently advertised",
    "awarded",
    "cancelled",
    "closed",
    "quickfind",
    "about",
    "about e-tender",
    "vision and mission",
    "mandate",
    "procurement plans",
    "procurement data",
    "login",
    "get in touch",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _norm_url(url: str, base: str = ETENDERS_BASE) -> str:
    url = html.unescape(_clean(url))
    if not url:
        return ""
    return urljoin(base, url)


def _is_generic_url(url: str) -> bool:
    if not url:
        return True
    p = urlparse(url)
    path = (p.path or "").rstrip("/").lower()
    if path in {"", "/home", "/home/opportunities", "/home/about", "/home/visionmission", "/home/mandate"}:
        return True
    if "identity/account/login" in path:
        return True
    return False


def _is_document_like(url: str, label: str = "") -> bool:
    blob = _safe_lower(url + " " + label)
    return any(h in blob for h in SUPPORTED_DOCUMENT_HINTS)


def _tokenise(text: str) -> List[str]:
    text = _safe_lower(text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {
        "the", "and", "for", "with", "including", "copies", "copy", "supply", "delivery",
        "of", "a", "an", "to", "in", "on", "at", "rfq", "rfp", "bid", "tender",
        "days", "day", "service", "services",
    }
    return [t for t in text.split() if len(t) >= 4 and t not in stop]


def _row_match_score(target_title: str, row_text: str) -> Dict[str, Any]:
    target_tokens = _tokenise(target_title)
    row_low = _safe_lower(row_text)

    if not target_tokens:
        return {"score": 0.0, "hits": [], "target_token_count": 0}

    hits = [t for t in target_tokens if t in row_low]
    score = len(hits) / max(len(target_tokens), 1)

    # Date match matters on eTenders rows.
    target_dates = re.findall(r"\b\d{2}/\d{2}/20\d{2}\b", target_title)
    date_hits = [d for d in target_dates if d in row_text]
    if target_dates and date_hits:
        score += 0.15

    # Strong phrase overlap.
    phrase = _safe_lower(target_title)
    phrase = re.sub(r"\s+in\s+\d+\s+days?$", "", phrase).strip()
    if phrase and phrase[:50] in row_low:
        score += 0.25

    return {
        "score": round(min(score, 1.0), 4),
        "hits": hits,
        "target_token_count": len(target_tokens),
        "date_hits": date_hits,
    }


@dataclass
class ResolvedLink:
    url: str
    label: str
    score: float
    reasons: List[str]
    is_document: bool
    is_generic: bool


def _score_row_link(url: str, label: str, row_score: float) -> ResolvedLink:
    low_label = _safe_lower(label)
    is_doc = _is_document_like(url, label)
    is_generic = _is_generic_url(url) or low_label in GENERIC_LABELS

    score = 0.0
    reasons: List[str] = []

    if row_score >= 0.45:
        score += 0.45
        reasons.append("matched_row_context")
    elif row_score >= 0.3:
        score += 0.25
        reasons.append("weak_row_context")
    else:
        score -= 0.3
        reasons.append("poor_row_context")

    if is_doc:
        score += 0.35
        reasons.append("document_or_download_link")

    if "downloadspec" in _safe_lower(url):
        score += 0.15
        reasons.append("downloadspec")

    if "documentid=" in _safe_lower(url):
        score += 0.1
        reasons.append("document_id")

    if low_label in GENERIC_LABELS:
        score -= 0.4
        reasons.append("generic_label")

    if is_generic:
        score -= 0.35
        reasons.append("generic_url")

    if is_doc and row_score < 0.35:
        score -= 0.35
        reasons.append("document_without_sufficient_row_match")

    return ResolvedLink(
        url=url,
        label=label,
        score=round(score, 4),
        reasons=reasons,
        is_document=is_doc,
        is_generic=is_generic,
    )


def resolve_true_etenders_detail(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    target_title = _clean(
        payload.get("title")
        or payload.get("description")
        or payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or ""
    )

    source_url = _norm_url(
        payload.get("source_url")
        or payload.get("document_url")
        or payload.get("detail_url")
        or ETENDERS_OPPORTUNITIES
    )

    if "etenders.gov.za" not in _safe_lower(source_url):
        return {
            "status": "skipped",
            "service_version": SERVICE_VERSION,
            "reason": "not_etenders_source",
            "resolved_at": _now(),
        }

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:
        return {
            "status": "skipped",
            "service_version": SERVICE_VERSION,
            "reason": "playwright_unavailable",
            "error": str(exc),
            "resolved_at": _now(),
        }

    rows_out: List[Dict[str, Any]] = []
    candidates: List[ResolvedLink] = []
    screenshots: List[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
                )
            )
            page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            # Try to expand visible rows if eTenders uses detail-control cells/buttons.
            expand_selectors = [
                "td.details-control",
                "button.details-control",
                ".details-control",
                "td:first-child",
            ]
            for selector in expand_selectors:
                try:
                    controls = page.query_selector_all(selector)
                    for control in controls[:30]:
                        try:
                            control.click(timeout=800)
                            page.wait_for_timeout(150)
                        except Exception:
                            continue
                    if controls:
                        break
                except Exception:
                    continue

            row_selectors = [
                "table tbody tr",
                "table tr",
                ".dataTables_wrapper tr",
                ".tender-row",
                ".opportunity-row",
                ".card",
            ]

            row_handles = []
            for selector in row_selectors:
                try:
                    row_handles = page.query_selector_all(selector)
                    if row_handles:
                        break
                except Exception:
                    continue

            for idx, row in enumerate(row_handles[:150]):
                try:
                    row_text = _clean(row.inner_text(timeout=1200))
                except Exception:
                    continue

                if not row_text or len(row_text) < 20:
                    continue

                match = _row_match_score(target_title, row_text)
                row_score = float(match.get("score") or 0.0)

                if row_score < 0.25:
                    continue

                row_data = {
                    "index": idx,
                    "match_score": row_score,
                    "match_hits": match.get("hits") or [],
                    "date_hits": match.get("date_hits") or [],
                    "text_preview": row_text[:500],
                    "links": [],
                }

                try:
                    anchors = row.query_selector_all("a[href]")
                except Exception:
                    anchors = []

                for a in anchors:
                    try:
                        href = a.get_attribute("href") or ""
                        label = _clean(a.inner_text(timeout=500) or a.get_attribute("title") or "")
                    except Exception:
                        continue

                    url = _norm_url(href, source_url)
                    if not url:
                        continue

                    link = _score_row_link(url, label, row_score)
                    row_data["links"].append(asdict(link))
                    candidates.append(link)

                # Also capture onclick-style document ids if present.
                try:
                    html_blob = row.inner_html(timeout=1000)
                except Exception:
                    html_blob = ""

                for doc_id in re.findall(r"documentId\s*[=:]\s*['\"]?(\d+)", html_blob, flags=re.I):
                    url = f"{ETENDERS_BASE}/Home/DownloadSpec?documentId={doc_id}&source=sharepoint"
                    link = _score_row_link(url, "Download", row_score)
                    if "onclick_document_id" not in link.reasons:
                        link.reasons.append("onclick_document_id")
                    row_data["links"].append(asdict(link))
                    candidates.append(link)

                rows_out.append(row_data)

            browser.close()

    except Exception as exc:
        return {
            "status": "failed",
            "service_version": SERVICE_VERSION,
            "resolved_at": _now(),
            "source_url": source_url,
            "title": target_title,
            "error": str(exc),
        }

    # Dedupe candidate links.
    dedup: Dict[str, ResolvedLink] = {}
    for c in candidates:
        if c.url not in dedup or c.score > dedup[c.url].score:
            dedup[c.url] = c

    sorted_links = sorted(dedup.values(), key=lambda x: x.score, reverse=True)

    verified_documents = [
        c for c in sorted_links
        if c.is_document
        and not c.is_generic
        and c.score >= 0.55
        and "matched_row_context" in c.reasons
        and "document_without_sufficient_row_match" not in c.reasons
    ]

    verified_details = [
        c for c in sorted_links
        if not c.is_document
        and not c.is_generic
        and c.score >= 0.35
        and "matched_row_context" in c.reasons
    ]

    if verified_documents:
        action = "promote_verified_row_document"
    elif verified_details:
        action = "promote_verified_detail_page"
    elif rows_out:
        action = "matched_row_but_no_verified_document"
    else:
        action = "no_matching_row"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "resolved_at": _now(),
        "source_url": source_url,
        "title": target_title,
        "matched_row_count": len(rows_out),
        "candidate_link_count": len(sorted_links),
        "verified_document_count": len(verified_documents),
        "verified_detail_count": len(verified_details),
        "recommended_action": action,
        "safe_to_download": bool(verified_documents),
        "safe_to_follow_detail": bool(verified_details),
        "recommended_document_links": [asdict(c) for c in verified_documents[:10]],
        "recommended_detail_links": [asdict(c) for c in verified_details[:10]],
        "candidate_links": [asdict(c) for c in sorted_links[:30]],
        "matched_rows": rows_out[:12],
        "notes": [
            "V50.8 only promotes links found inside rows matching the harvested RFQ title.",
            "Generic eTenders/global links remain blocked.",
            "This engine is intended to run before document acquisition.",
        ],
    }


def get_v50_8_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "capabilities": [
            "playwright_row_inspection",
            "row_title_token_matching",
            "row_local_document_extraction",
            "onclick_document_id_capture",
            "generic_global_link_rejection",
            "safe_document_promotion",
        ],
    }
