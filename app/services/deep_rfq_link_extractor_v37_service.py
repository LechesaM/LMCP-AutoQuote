
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SERVICE_VERSION = "V37_DEEP_RFQ_LINK_EXTRACTOR"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOG_DIR = PROJECT_ROOT / "runtime" / "v37_deep_rfq_link_extractor" / "logs"
DOWNLOAD_DIR = PROJECT_ROOT / "runtime" / "v37_deep_rfq_link_extractor" / "downloads"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = int(str(os.getenv("V37_TIMEOUT", "35")).strip() or "35")
MAX_DOC_LINKS = int(str(os.getenv("V37_MAX_DOC_LINKS", "20")).strip() or "20")
DOWNLOAD_DOCS = str(os.getenv("V37_DOWNLOAD_DOCS", "false")).strip().lower() == "true"

DOC_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

EXCLUDED_EMAIL_HINTS = ["ethicshelpdesk", "donotreply", "no-reply", "noreply", "webmaster"]
SUBMISSION_EMAIL_HINTS = ["submit", "submission", "quotations", "quotes", "tender", "tenders", "procurement", "scm", "supplychain", "supply.chain"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _is_doc_url(url: str) -> bool:
    u = _clean(url).lower().split("?")[0]
    return any(u.endswith(ext) or ext in u for ext in DOC_EXTENSIONS)


def _extract_reference(text: str) -> str:
    patterns = [
        r"\bRFQ[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bRFP[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bBID[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bTENDER[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\b[A-Z]{1,8}/[A-Z0-9]{1,10}\s*\d{1,6}/\d{2,4}\b",
        r"\b[A-Z]{2,10}\s*\d{2,6}/\d{2,4}\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return _clean(m.group(0))
    return ""


def _extract_closing_date(text: str) -> str:
    patterns = [
        r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]20\d{2}\b",
        r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return _clean(m.group(0))
    return ""


def _good_email(email: str) -> bool:
    low = email.lower()
    return not any(h in low for h in EXCLUDED_EMAIL_HINTS)


def _rank_emails(emails: List[str]) -> List[str]:
    unique = []
    seen = set()
    for e in emails:
        e = e.strip().strip(".,;:()[]<>")
        if not _good_email(e):
            continue
        low = e.lower()
        if low in seen:
            continue
        seen.add(low)
        unique.append(e)

    def score(email: str) -> int:
        low = email.lower()
        return sum(10 for h in SUBMISSION_EMAIL_HINTS if h in low)

    return sorted(unique, key=score, reverse=True)


def _fetch(url: str) -> Dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0"}
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    return {"url": url, "content_type": ctype, "text": r.text if "html" in ctype.lower() or "<html" in r.text[:500].lower() else "", "bytes": r.content}


def _download_doc(url: str, rfq_ref: str = "") -> str:
    if not DOWNLOAD_DOCS:
        return ""
    try:
        data = _fetch(url)["bytes"]
        suffix = ".bin"
        low = url.lower().split("?")[0]
        for ext in DOC_EXTENSIONS:
            if low.endswith(ext) or ext in low:
                suffix = ext
                break
        safe_ref = re.sub(r"[^A-Za-z0-9_.-]+", "_", rfq_ref or "rfq")[:80]
        path = DOWNLOAD_DIR / f"{safe_ref}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
        path.write_bytes(data)
        return str(path)
    except Exception:
        return ""


def _discover_from_html(html: str, base_url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    full_text = _clean(soup.get_text(" ", strip=True))
    links = []
    doc_links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a.get("href"))
        label = _clean(a.get_text(" ", strip=True))
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0]
            links.append({"url": href, "label": label, "type": "email", "email": email})
            continue
        link = {"url": href, "label": label, "type": "document" if _is_doc_url(href) else "link"}
        links.append(link)
        if _is_doc_url(href):
            doc_links.append(link)

    emails = EMAIL_RE.findall(full_text)
    for link in links:
        if link.get("type") == "email" and link.get("email"):
            emails.append(link["email"])

    return {
        "text": full_text[:12000],
        "links": links[:100],
        "document_links": doc_links[:MAX_DOC_LINKS],
        "emails": _rank_emails(emails)[:20],
        "reference": _extract_reference(full_text),
        "closing_date": _extract_closing_date(full_text),
    }


def enrich_rfq_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(candidate or {})
    diagnostics = {"service_version": SERVICE_VERSION, "checked_at": _now(), "status": "started", "steps": []}

    detail_url = _clean(item.get("detail_url"))
    document_url = _clean(item.get("document_url"))
    source_url = _clean(item.get("source_url"))

    urls_to_try = []
    for url in [detail_url, document_url]:
        if url.startswith("http") and url != source_url:
            urls_to_try.append(url)

    discovered_docs = []
    discovered_emails = []
    discovered_texts = []
    downloaded_files = []
    best_ref = ""
    best_closing = ""

    if not urls_to_try:
        diagnostics["status"] = "no_detail_or_document_url"
        diagnostics["message"] = "Candidate has no detail/document URL yet. V38 must click each tender row/details to expose document links."
    else:
        for url in urls_to_try[:3]:
            try:
                diagnostics["steps"].append(f"fetch:{url}")
                fetched = _fetch(url)
                if _is_doc_url(url) or "pdf" in fetched.get("content_type", "").lower() or "application/" in fetched.get("content_type", "").lower():
                    downloaded = _download_doc(url, _clean(item.get("buyer_rfq_number") or item.get("title")))
                    discovered_docs.append({"url": url, "label": item.get("title", ""), "type": "direct_document", "downloaded_path": downloaded})
                    if downloaded:
                        downloaded_files.append(downloaded)
                    continue

                html = fetched.get("text", "")
                if html:
                    discovery = _discover_from_html(html, url)
                    discovered_docs.extend(discovery.get("document_links", []))
                    discovered_emails.extend(discovery.get("emails", []))
                    discovered_texts.append(discovery.get("text", ""))
                    best_ref = best_ref or discovery.get("reference", "")
                    best_closing = best_closing or discovery.get("closing_date", "")
            except Exception as exc:
                diagnostics["steps"].append(f"fetch_failed:{url}:{str(exc)[:180]}")

    doc_out = []
    seen_docs = set()
    for doc in discovered_docs:
        u = _clean(doc.get("url"))
        if not u or u in seen_docs:
            continue
        seen_docs.add(u)
        doc_out.append(doc)

    email_out = _rank_emails(discovered_emails)

    if doc_out and not item.get("document_url"):
        item["document_url"] = doc_out[0].get("url", "")

    if email_out:
        item["buyer_email"] = item.get("buyer_email") or email_out[0]
        item["recipient_email"] = item.get("recipient_email") or email_out[0]
        item["submission_email"] = item.get("submission_email") or email_out[0]
        item["submission_method"] = "email"

    if best_ref:
        item["buyer_rfq_number"] = best_ref
        item["rfq_number"] = best_ref
        item["reference_number"] = best_ref

    if best_closing and not item.get("closing_date"):
        item["closing_date"] = best_closing

    merged_text = _clean(" ".join([item.get("raw_text", ""), item.get("description", "")] + discovered_texts))
    if merged_text:
        item["deep_rfq_text"] = merged_text[:20000]

    item["discovered_documents"] = doc_out[:MAX_DOC_LINKS]
    item["discovered_emails"] = email_out[:20]
    item["downloaded_documents"] = downloaded_files

    diagnostics["status"] = "ok" if (doc_out or email_out or best_ref or best_closing) else diagnostics.get("status", "no_enrichment_found")
    diagnostics["document_count"] = len(doc_out)
    diagnostics["email_count"] = len(email_out)
    diagnostics["has_reference"] = bool(best_ref)
    diagnostics["has_closing_date"] = bool(best_closing)
    diagnostics["download_count"] = len(downloaded_files)

    item["v37_deep_rfq_link_extraction"] = diagnostics
    item["updated_at"] = _now()
    return item


def enrich_rfq_candidates(candidates: Any) -> Dict[str, Any]:
    if not isinstance(candidates, list):
        candidates = []
    items = [enrich_rfq_candidate(c) for c in candidates if isinstance(c, dict)]
    enriched = [x for x in items if x.get("v37_deep_rfq_link_extraction", {}).get("status") == "ok"]
    return {"status": "ok", "service_version": SERVICE_VERSION, "checked_at": _now(), "total": len(items), "enriched_total": len(enriched), "items": items, "enriched_items": enriched}


def run_v37_from_v36(max_portals: int = 1, enable_auto_quote: bool = False, persist_to_live_store: bool = True, include_review: bool = True) -> Dict[str, Any]:
    from app.services.interactive_playwright_extractor_v36_service import run_v36_interactive_extraction

    v36 = run_v36_interactive_extraction(max_portals=max_portals, enable_auto_quote=False, persist_to_live_store=persist_to_live_store, include_review_in_pipeline=False)
    candidates = []
    candidates.extend(v36.get("accepted_items", []))
    if include_review:
        candidates.extend(v36.get("review_items", []))

    enriched_result = enrich_rfq_candidates(candidates)
    pipeline_items = enriched_result.get("items", [])

    auto_quote_results = []
    if enable_auto_quote and pipeline_items:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch
            auto_quote_results = run_tender_pipeline_batch(pipeline_items, source="v37-deep-rfq-link-extractor", persist_to_live_store=persist_to_live_store)
        except Exception as exc:
            auto_quote_results = [{"status": "error", "stage": "v37_pipeline_batch", "message": str(exc)}]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "v36_candidate_total": v36.get("candidate_total", 0),
        "v36_accepted_total": v36.get("accepted_total", 0),
        "v36_review_total": v36.get("review_total", 0),
        "v37_input_total": len(candidates),
        "v37_enriched_total": enriched_result.get("enriched_total", 0),
        "pipeline_candidate_total": len(pipeline_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "v36_result": v36,
        "v37_result": enriched_result,
        "items": pipeline_items,
    }
    result["log_path"] = _write_log("v37_from_v36", result)
    return result
