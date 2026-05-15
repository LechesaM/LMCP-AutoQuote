"""
LMCP V50.8.1 - eTenders Ajax/DataTables Resolver

Purpose:
- eTenders often loads rows through JavaScript/XHR instead of plain DOM.
- This resolver uses Playwright to capture network responses and DataTables JSON.
- It then matches tender rows against the harvested title and extracts row-local document/detail links.

Drop-in:
    app/services/etenders_ajax_datatables_resolver_v50_8_1_service.py
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse


SERVICE_VERSION = "V50.8.1_ETENDERS_AJAX_DATATABLES_RESOLVER"

ETENDERS_BASE = "https://www.etenders.gov.za"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"

DOCUMENT_HINTS = (
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
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _norm_url(url: str, base: str = ETENDERS_BASE) -> str:
    url = html.unescape(str(url or "")).strip()
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


def _is_doc_like(url: str, label: str = "") -> bool:
    blob = _safe_lower(f"{url} {label}")
    return any(h in blob for h in DOCUMENT_HINTS)


def _tokenise(text: str) -> List[str]:
    text = _safe_lower(text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {
        "the", "and", "for", "with", "including", "copies", "copy",
        "supply", "delivery", "deliver", "of", "a", "an", "to",
        "in", "on", "at", "rfq", "rfp", "bid", "tender", "days",
        "day", "service", "services", "printed",
    }
    return [t for t in text.split() if len(t) >= 4 and t not in stop]


def _match_score(target_title: str, row_text: str) -> Dict[str, Any]:
    tokens = _tokenise(target_title)
    row_low = _safe_lower(row_text)
    hits = [t for t in tokens if t in row_low]

    score = len(hits) / max(len(tokens), 1) if tokens else 0.0

    target_dates = re.findall(r"\b\d{2}/\d{2}/20\d{2}\b", target_title)
    date_hits = [d for d in target_dates if d in row_text]
    if target_dates and date_hits:
        score += 0.15

    phrase = _safe_lower(target_title)
    phrase = re.sub(r"\s+in\s+\d+\s+days?$", "", phrase).strip()
    if phrase and len(phrase) >= 35 and phrase[:55] in row_low:
        score += 0.25

    return {
        "score": round(min(score, 1.0), 4),
        "hits": hits,
        "target_token_count": len(tokens),
        "date_hits": date_hits,
    }


def _flatten_json_rows(value: Any) -> List[Any]:
    rows: List[Any] = []

    if isinstance(value, list):
        rows.extend(value)
        for item in value:
            rows.extend(_flatten_json_rows(item))
        return rows

    if isinstance(value, dict):
        for key in ("data", "aaData", "results", "items", "rows", "records", "releases"):
            sub = value.get(key)
            if isinstance(sub, list):
                rows.extend(sub)

        # Also inspect nested dict/list values.
        for sub in value.values():
            if isinstance(sub, (list, dict)):
                rows.extend(_flatten_json_rows(sub))

    return rows


def _row_to_text(row: Any) -> str:
    if isinstance(row, dict):
        parts: List[str] = []
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                parts.append(_row_to_text(value))
            else:
                parts.append(_clean(value))
        return _clean(" ".join(parts))

    if isinstance(row, list):
        return _clean(" ".join(_row_to_text(x) for x in row))

    return _clean(row)


def _extract_links_from_value(value: Any, base_url: str) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []

    blob = ""
    if isinstance(value, (dict, list)):
        try:
            blob = json.dumps(value, ensure_ascii=False)
        except Exception:
            blob = str(value)
    else:
        blob = str(value or "")

    blob = html.unescape(blob)

    for href in re.findall(r'href=["\']([^"\']+)["\']', blob, flags=re.I):
        links.append({"url": _norm_url(href, base_url), "label": ""})

    for url in re.findall(r'https?://[^\s"\'<>]+', blob, flags=re.I):
        links.append({"url": _norm_url(url, base_url), "label": ""})

    for doc_id in re.findall(r"documentId\s*[=:]\s*['\"]?(\d+)", blob, flags=re.I):
        links.append({
            "url": f"{ETENDERS_BASE}/Home/DownloadSpec?documentId={doc_id}&source=sharepoint",
            "label": "Download",
        })

    for doc_id in re.findall(r"DownloadSpec\?documentId=(\d+)", blob, flags=re.I):
        links.append({
            "url": f"{ETENDERS_BASE}/Home/DownloadSpec?documentId={doc_id}&source=sharepoint",
            "label": "Download",
        })

    # de-dupe
    out: List[Dict[str, str]] = []
    seen = set()
    for link in links:
        url = link.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(link)

    return out


@dataclass
class CandidateLink:
    url: str
    label: str
    score: float
    reasons: List[str]
    is_document: bool
    is_generic: bool
    source: str


def _score_link(url: str, label: str, row_score: float, source: str) -> CandidateLink:
    low_label = _safe_lower(label)
    is_document = _is_doc_like(url, label)
    is_generic = _is_generic_url(url) or low_label in GENERIC_LABELS

    score = 0.0
    reasons: List[str] = []

    if row_score >= 0.45:
        score += 0.5
        reasons.append("strong_row_match")
    elif row_score >= 0.3:
        score += 0.25
        reasons.append("weak_row_match")
    else:
        score -= 0.35
        reasons.append("poor_row_match")

    if is_document:
        score += 0.35
        reasons.append("document_or_download_link")

    low_url = _safe_lower(url)
    if "downloadspec" in low_url:
        score += 0.15
        reasons.append("downloadspec")

    if "documentid=" in low_url:
        score += 0.1
        reasons.append("document_id")

    if is_generic:
        score -= 0.45
        reasons.append("generic_link")

    if is_document and row_score < 0.35:
        score -= 0.45
        reasons.append("document_without_sufficient_row_match")

    return CandidateLink(
        url=url,
        label=label or "",
        score=round(score, 4),
        reasons=reasons,
        is_document=is_document,
        is_generic=is_generic,
        source=source,
    )


def resolve_etenders_ajax_datatables(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    title = _clean(
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

    captured_json: List[Dict[str, Any]] = []
    captured_text: List[Dict[str, Any]] = []
    matched_rows: List[Dict[str, Any]] = []
    links: List[CandidateLink] = []

    def handle_response(response: Any) -> None:
        try:
            url = response.url
            ctype = (response.headers or {}).get("content-type", "")
            low_url = _safe_lower(url)
            low_ctype = _safe_lower(ctype)

            interesting = any(k in low_url for k in [
                "opportun", "tender", "datatable", "ajax", "home", "get",
                "search", "downloadspec", "ocds"
            ])

            if not interesting:
                return

            if "json" in low_ctype:
                try:
                    data = response.json()
                    captured_json.append({
                        "url": url,
                        "content_type": ctype,
                        "data": data,
                    })
                except Exception:
                    pass
            elif "text" in low_ctype or "html" in low_ctype:
                try:
                    txt = response.text()
                    if any(k in _safe_lower(txt[:5000]) for k in ["downloadspec", "tender", "rfq", "supply"]):
                        captured_text.append({
                            "url": url,
                            "content_type": ctype,
                            "text": txt[:200000],
                        })
                except Exception:
                    pass
        except Exception:
            return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
                )
            )
            page.on("response", handle_response)

            page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Trigger common DataTables/search events.
            for selector in [
                "input[type='search']",
                "input[aria-controls]",
                "#dt_basic_filter input",
                ".dataTables_filter input",
                "input.form-control",
            ]:
                try:
                    box = page.query_selector(selector)
                    if box:
                        box.fill(title[:80])
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    continue

            # Try clicking search/filter buttons.
            for selector in [
                "button:has-text('Search')",
                "input[type='submit']",
                "button[type='submit']",
                ".btn-primary",
            ]:
                try:
                    btn = page.query_selector(selector)
                    if btn:
                        btn.click(timeout=1500)
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # Expand detail controls after Ajax loads.
            for selector in ["td.details-control", ".details-control", "td:first-child"]:
                try:
                    controls = page.query_selector_all(selector)
                    for control in controls[:30]:
                        try:
                            control.click(timeout=600)
                            page.wait_for_timeout(150)
                        except Exception:
                            continue
                    if controls:
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    continue

            # DOM fallback after Ajax/search.
            for selector in ["table tbody tr", "table tr", ".dataTables_wrapper tr", ".card", ".row"]:
                try:
                    rows = page.query_selector_all(selector)
                except Exception:
                    rows = []
                for idx, row in enumerate(rows[:200]):
                    try:
                        row_text = _clean(row.inner_text(timeout=1000))
                    except Exception:
                        continue
                    if len(row_text) < 20:
                        continue
                    match = _match_score(title, row_text)
                    score = float(match.get("score") or 0.0)
                    if score < 0.25:
                        continue
                    row_record = {
                        "source": "dom_after_ajax",
                        "index": idx,
                        "match_score": score,
                        "match_hits": match.get("hits") or [],
                        "date_hits": match.get("date_hits") or [],
                        "text_preview": row_text[:700],
                        "links": [],
                    }
                    try:
                        anchors = row.query_selector_all("a[href]")
                    except Exception:
                        anchors = []
                    for a in anchors:
                        try:
                            href = a.get_attribute("href") or ""
                            label = _clean(a.inner_text(timeout=500) or "")
                        except Exception:
                            continue
                        url = _norm_url(href, source_url)
                        scored = _score_link(url, label, score, "dom_after_ajax")
                        row_record["links"].append(asdict(scored))
                        links.append(scored)
                    matched_rows.append(row_record)

            browser.close()

    except Exception as exc:
        return {
            "status": "failed",
            "service_version": SERVICE_VERSION,
            "resolved_at": _now(),
            "source_url": source_url,
            "title": title,
            "error": str(exc),
        }

    # Analyse captured JSON rows.
    for resp in captured_json:
        rows = _flatten_json_rows(resp.get("data"))
        for idx, row in enumerate(rows[:2000]):
            row_text = _row_to_text(row)
            if len(row_text) < 20:
                continue
            match = _match_score(title, row_text)
            score = float(match.get("score") or 0.0)
            if score < 0.25:
                continue

            row_links = _extract_links_from_value(row, resp.get("url") or source_url)
            row_record = {
                "source": "xhr_json",
                "response_url": resp.get("url"),
                "index": idx,
                "match_score": score,
                "match_hits": match.get("hits") or [],
                "date_hits": match.get("date_hits") or [],
                "text_preview": row_text[:700],
                "links": [],
            }
            for link in row_links:
                scored = _score_link(link["url"], link.get("label") or "", score, "xhr_json")
                row_record["links"].append(asdict(scored))
                links.append(scored)
            matched_rows.append(row_record)

    # Analyse captured HTML/text chunks as row-like segments.
    for resp in captured_text:
        text = resp.get("text") or ""
        chunks = re.split(r"</tr>|<tr|</li>|</div>", text, flags=re.I)
        for idx, chunk in enumerate(chunks[:3000]):
            row_text = _clean(chunk)
            if len(row_text) < 20:
                continue
            match = _match_score(title, row_text)
            score = float(match.get("score") or 0.0)
            if score < 0.25:
                continue
            row_links = _extract_links_from_value(chunk, resp.get("url") or source_url)
            row_record = {
                "source": "xhr_text",
                "response_url": resp.get("url"),
                "index": idx,
                "match_score": score,
                "match_hits": match.get("hits") or [],
                "date_hits": match.get("date_hits") or [],
                "text_preview": row_text[:700],
                "links": [],
            }
            for link in row_links:
                scored = _score_link(link["url"], link.get("label") or "", score, "xhr_text")
                row_record["links"].append(asdict(scored))
                links.append(scored)
            matched_rows.append(row_record)

    # De-dupe links.
    dedup: Dict[str, CandidateLink] = {}
    for link in links:
        if link.url not in dedup or link.score > dedup[link.url].score:
            dedup[link.url] = link

    sorted_links = sorted(dedup.values(), key=lambda x: x.score, reverse=True)

    verified_docs = [
        link for link in sorted_links
        if link.is_document
        and not link.is_generic
        and link.score >= 0.55
        and (
            "strong_row_match" in link.reasons
            or "weak_row_match" in link.reasons
        )
        and "document_without_sufficient_row_match" not in link.reasons
    ]

    verified_details = [
        link for link in sorted_links
        if not link.is_document
        and not link.is_generic
        and link.score >= 0.35
        and ("strong_row_match" in link.reasons or "weak_row_match" in link.reasons)
    ]

    if verified_docs:
        action = "promote_verified_ajax_document"
    elif verified_details:
        action = "promote_verified_ajax_detail"
    elif matched_rows:
        action = "matched_ajax_row_but_no_verified_document"
    else:
        action = "no_matching_ajax_or_datatable_row"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "resolved_at": _now(),
        "source_url": source_url,
        "title": title,
        "captured_json_response_count": len(captured_json),
        "captured_text_response_count": len(captured_text),
        "matched_row_count": len(matched_rows),
        "candidate_link_count": len(sorted_links),
        "verified_document_count": len(verified_docs),
        "verified_detail_count": len(verified_details),
        "recommended_action": action,
        "safe_to_download": bool(verified_docs),
        "safe_to_follow_detail": bool(verified_details),
        "recommended_document_links": [asdict(x) for x in verified_docs[:10]],
        "recommended_detail_links": [asdict(x) for x in verified_details[:10]],
        "candidate_links": [asdict(x) for x in sorted_links[:30]],
        "matched_rows": matched_rows[:20],
        "captured_response_urls": [x.get("url") for x in captured_json[:20]] + [x.get("url") for x in captured_text[:20]],
        "notes": [
            "V50.8.1 captures network/XHR responses and DataTables JSON.",
            "Only row-matched document/detail links are promoted.",
            "If no matching Ajax row appears, use an authenticated/session-primed eTenders browser in the next phase.",
        ],
    }


def get_v50_8_1_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "capabilities": [
            "network_response_capture",
            "datatable_json_extraction",
            "ajax_text_row_extraction",
            "search_box_triggering",
            "row_local_document_promotion",
            "generic_link_rejection",
        ],
    }
