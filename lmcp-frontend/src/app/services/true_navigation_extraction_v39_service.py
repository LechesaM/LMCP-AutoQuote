
from __future__ import annotations

"""
LMCP V39 True Navigation Extraction Engine

Drop-in:
    app/services/true_navigation_extraction_v39_service.py

Purpose:
    V36 finds accepted tender rows.
    V38 attempts click/deep extraction.
    V39 adds stronger true-navigation strategies:
      1. Re-open live eTenders listing.
      2. Match accepted RFQ row by title.
      3. Try row links, row click, title click, double click, Enter key.
      4. Detect URL change, modal opening, expanded row, or new page.
      5. Extract document links, emails, RFQ/reference numbers, closing date, and submission clues.
      6. Return pipeline-ready enriched RFQ objects.

This is a safe add-on. It does not replace V36/V38.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SERVICE_VERSION = "V39_TRUE_NAVIGATION_EXTRACTION_ENGINE"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOG_DIR = PROJECT_ROOT / "runtime" / "v39_true_navigation_extraction" / "logs"
PROOF_DIR = PROJECT_ROOT / "runtime" / "v39_true_navigation_extraction" / "proof"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROOF_DIR.mkdir(parents=True, exist_ok=True)

HEADLESS = str(os.getenv("V39_HEADLESS", "true")).strip().lower() == "true"
TIMEOUT_MS = int(str(os.getenv("V39_TIMEOUT_MS", "65000")).strip() or "65000")
WAIT_MS = int(str(os.getenv("V39_WAIT_MS", "2500")).strip() or "2500")
MAX_ROWS = int(str(os.getenv("V39_MAX_ROWS", "250")).strip() or "250")
MAX_LINKS = int(str(os.getenv("V39_MAX_LINKS", "140")).strip() or "140")

ETENDERS_URL = "https://www.etenders.gov.za/Home/opportunities"
ETENDERS_VARIANTS = [
    "https://www.etenders.gov.za/Home/opportunities?id=1",
    "https://www.etenders.gov.za/Home/opportunities?id=2",
]

DOC_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

NOISE_EMAIL_HINTS = ["noreply", "no-reply", "donotreply", "webmaster", "ethicshelpdesk"]
SUBMISSION_HINTS = ["submit", "submission", "quotation", "quotes", "quote", "tender", "tenders", "procurement", "scm", "supplychain", "bid"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _is_doc_url(url: str) -> bool:
    u = _lower(url).split("?")[0]
    return any(ext in u for ext in DOC_EXTENSIONS)


def _extract_reference(text: str) -> str:
    patterns = [
        r"\bRFQ[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bRFP[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bBID[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bTENDER[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\b[A-Z]{1,8}/[A-Z0-9]{1,10}\s*\d{1,6}/\d{2,4}\b",
        r"\b[A-Z]{2,10}\s*\d{2,6}/\d{2,4}\b",
        r"\b\d{2,6}/\d{2,4}\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            ref = _clean(m.group(0))
            if not re.fullmatch(r"\d{1,2}/\d{1,2}", ref):
                return ref
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


def _rank_emails(emails: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for email in emails:
        email = email.strip().strip(".,;:()[]<>")
        low = email.lower()
        if not email or low in seen:
            continue
        if any(x in low for x in NOISE_EMAIL_HINTS):
            continue
        seen.add(low)
        out.append(email)

    def score(email: str) -> int:
        low = email.lower()
        return sum(10 for hint in SUBMISSION_HINTS if hint in low)

    return sorted(out, key=score, reverse=True)


def _title_match(candidate_title: str, row_text: str) -> bool:
    title = _lower(candidate_title)
    row = _lower(row_text)
    if not title or not row:
        return False
    if title in row:
        return True

    title_words = [w for w in re.split(r"[^a-z0-9]+", title) if len(w) >= 4]
    if not title_words:
        return False

    hits = sum(1 for w in title_words if w in row)
    return hits >= max(3, int(len(title_words) * 0.55))


def _activate_listing(page) -> List[str]:
    actions: List[str] = []
    page.goto(ETENDERS_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    page.wait_for_timeout(WAIT_MS)

    for url in ETENDERS_VARIANTS:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            actions.append(f"goto_variant:{url}")
            page.wait_for_timeout(WAIT_MS)
            break
        except Exception as exc:
            actions.append(f"goto_variant_failed:{url}:{str(exc)[:140]}")

    for i in range(5):
        try:
            page.evaluate("(y) => window.scrollTo(0, y)", 800 * (i + 1))
            page.wait_for_timeout(700)
            actions.append(f"scroll:{i+1}")
        except Exception:
            pass

    try:
        page.wait_for_selector("table tbody tr, table tr", timeout=15000)
        actions.append("selector_ready:table_rows")
    except Exception as exc:
        actions.append(f"selector_failed:table_rows:{str(exc)[:140]}")

    return actions


def _collect_rows(page) -> List[Dict[str, Any]]:
    return page.evaluate(
        """(maxRows) => Array.from(document.querySelectorAll('table tr')).slice(0, maxRows).map((tr, index) => {
            const cells = Array.from(tr.querySelectorAll('td,th')).map(td => (td.innerText || '').trim()).filter(Boolean);
            const links = Array.from(tr.querySelectorAll('a[href]')).map(a => ({href: a.href || '', text: (a.innerText || a.getAttribute('title') || '').trim()}));
            const rect = tr.getBoundingClientRect();
            return {index, cells, links, text: (tr.innerText || '').trim(), x: rect.x, y: rect.y, width: rect.width, height: rect.height};
        }).filter(r => r.text && r.text.length > 10)""",
        MAX_ROWS,
    )


def _extract_current_page_intelligence(page) -> Dict[str, Any]:
    data = page.evaluate(
        """(maxLinks) => {
            const bodyText = (document.body ? document.body.innerText : '') || '';
            const links = Array.from(document.querySelectorAll('a[href]')).slice(0, maxLinks).map(a => ({
                href: a.href || '',
                text: (a.innerText || a.getAttribute('title') || a.getAttribute('aria-label') || '').trim()
            }));
            const buttons = Array.from(document.querySelectorAll('button,input[type=button],input[type=submit]')).slice(0, 80).map(b => ({
                text: (b.innerText || b.value || b.getAttribute('title') || b.getAttribute('aria-label') || '').trim()
            }));
            const tables = Array.from(document.querySelectorAll('table')).slice(0, 8).map(t => (t.innerText || '').trim());
            const modals = Array.from(document.querySelectorAll('.modal,[role=dialog],.swal2-popup')).slice(0, 8).map(m => (m.innerText || '').trim());
            return {url: location.href, text: bodyText, links, buttons, tables, modals, title: document.title || ''};
        }""",
        MAX_LINKS,
    )

    full_text = _clean(" ".join([
        data.get("title", ""),
        data.get("text", ""),
        " ".join(data.get("tables", []) or []),
        " ".join(data.get("modals", []) or []),
    ]))

    links = []
    docs = []
    for link in data.get("links", []) or []:
        href = _clean(link.get("href"))
        label = _clean(link.get("text"))
        if not href:
            continue
        obj = {"url": href, "label": label, "type": "document" if _is_doc_url(href) else "link"}
        links.append(obj)
        if _is_doc_url(href):
            docs.append(obj)

    emails = EMAIL_RE.findall(full_text)
    for link in links:
        url = link.get("url", "")
        if url.startswith("mailto:"):
            emails.append(url.replace("mailto:", "").split("?")[0])

    return {
        "url": data.get("url", page.url),
        "text": full_text[:35000],
        "links": links[:MAX_LINKS],
        "document_links": docs[:40],
        "emails": _rank_emails(emails)[:30],
        "reference": _extract_reference(full_text),
        "closing_date": _extract_closing_date(full_text),
        "buttons": data.get("buttons", []),
        "modal_text": " ".join(data.get("modals", []) or [])[:12000],
    }


def _wait_after_click(page, old_url: str, actions: List[str]) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
        actions.append("waited_networkidle")
    except Exception:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
            actions.append("waited_domcontentloaded")
        except Exception:
            actions.append("wait_load_state_timeout")

    page.wait_for_timeout(WAIT_MS)

    if page.url != old_url:
        actions.append(f"url_changed:{old_url}=>{page.url}")
    else:
        actions.append("url_not_changed")


def _try_click_strategies(page, row_index: int, candidate_title: str, actions: List[str]) -> Dict[str, Any]:
    old_url = page.url

    # 1. Click document/detail link inside row if available.
    try:
        row = page.locator("table tr").nth(row_index)
        links = row.locator("a[href]")
        count = links.count()
        actions.append(f"row_link_count:{count}")
        if count > 0:
            links.first.click(timeout=10000)
            actions.append(f"clicked_row_first_link:{row_index}")
            _wait_after_click(page, old_url, actions)
            return {"strategy": "row_first_link", "clicked": True}
    except Exception as exc:
        actions.append(f"row_link_strategy_failed:{str(exc)[:160]}")

    # 2. Click row.
    try:
        old_url = page.url
        page.locator("table tr").nth(row_index).click(timeout=10000)
        actions.append(f"clicked_row:{row_index}")
        _wait_after_click(page, old_url, actions)
        return {"strategy": "row_click", "clicked": True}
    except Exception as exc:
        actions.append(f"row_click_failed:{str(exc)[:160]}")

    # 3. Double click row.
    try:
        old_url = page.url
        page.locator("table tr").nth(row_index).dblclick(timeout=10000)
        actions.append(f"double_clicked_row:{row_index}")
        _wait_after_click(page, old_url, actions)
        return {"strategy": "row_double_click", "clicked": True}
    except Exception as exc:
        actions.append(f"row_double_click_failed:{str(exc)[:160]}")

    # 4. Click matching title text.
    try:
        old_url = page.url
        page.get_by_text(candidate_title[:90], exact=False).first.click(timeout=10000)
        actions.append("clicked_title_text")
        _wait_after_click(page, old_url, actions)
        return {"strategy": "title_text_click", "clicked": True}
    except Exception as exc:
        actions.append(f"title_text_click_failed:{str(exc)[:160]}")

    # 5. Focus row and press Enter.
    try:
        old_url = page.url
        row = page.locator("table tr").nth(row_index)
        row.focus(timeout=8000)
        page.keyboard.press("Enter")
        actions.append(f"pressed_enter_on_row:{row_index}")
        _wait_after_click(page, old_url, actions)
        return {"strategy": "row_enter", "clicked": True}
    except Exception as exc:
        actions.append(f"row_enter_failed:{str(exc)[:160]}")

    return {"strategy": "none", "clicked": False}


def _build_enriched_candidate(candidate: Dict[str, Any], intel: Dict[str, Any], actions: List[str], screenshot: str, row_match: Dict[str, Any] | None) -> Dict[str, Any]:
    item = dict(candidate or {})
    docs = intel.get("document_links", []) or []
    emails = intel.get("emails", []) or []

    if docs:
        item["document_url"] = item.get("document_url") or docs[0].get("url", "")
        item["discovered_documents"] = docs
    else:
        item["discovered_documents"] = []

    if emails:
        item["buyer_email"] = item.get("buyer_email") or emails[0]
        item["recipient_email"] = item.get("recipient_email") or emails[0]
        item["submission_email"] = item.get("submission_email") or emails[0]
        item["submission_method"] = "email"
    else:
        item["submission_method"] = item.get("submission_method") or "portal"

    if intel.get("reference"):
        item["buyer_rfq_number"] = intel["reference"]
        item["rfq_number"] = intel["reference"]
        item["reference_number"] = intel["reference"]

    if intel.get("closing_date") and not item.get("closing_date"):
        item["closing_date"] = intel["closing_date"]

    item["detail_url"] = item.get("detail_url") or intel.get("url", "")
    item["discovered_emails"] = emails
    item["deep_rfq_text"] = _clean(" ".join([item.get("raw_text", ""), item.get("description", ""), intel.get("text", "")]))[:35000]

    ok = bool(docs or emails or intel.get("reference"))
    status = "ok" if ok else "opened_but_no_documents_or_email"

    item["v39_true_navigation_extraction"] = {
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "status": status,
        "document_count": len(docs),
        "email_count": len(emails),
        "has_reference": bool(intel.get("reference")),
        "detail_url": intel.get("url", ""),
        "row_match_index": row_match.get("index") if isinstance(row_match, dict) else None,
        "row_match_text": (row_match.get("text", "")[:1000] if isinstance(row_match, dict) else ""),
        "proof_screenshot": screenshot,
        "actions": actions,
    }

    item["updated_at"] = _now()
    return item


def true_navigation_extract_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        item = dict(candidate or {})
        item["v39_true_navigation_extraction"] = {
            "service_version": SERVICE_VERSION,
            "checked_at": _now(),
            "status": "error",
            "message": f"Playwright unavailable: {exc}",
        }
        return item

    title = _clean(candidate.get("title"))
    actions: List[str] = []
    screenshot = str(PROOF_DIR / f"v39_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            actions.extend(_activate_listing(page))

            rows = _collect_rows(page)
            actions.append(f"collected_rows:{len(rows)}")

            match = None
            for row in rows:
                if _title_match(title, row.get("text", "")):
                    match = row
                    break

            if not match:
                actions.append("no_matching_row_found")
                intel = _extract_current_page_intelligence(page)
                try:
                    page.screenshot(path=screenshot, full_page=True)
                except Exception:
                    screenshot = ""
                browser.close()
                item = _build_enriched_candidate(candidate, intel, actions, screenshot, None)
                item["v39_true_navigation_extraction"]["status"] = "no_matching_row_found"
                return item

            actions.append(f"matched_row_index:{match.get('index')}")

            # If links in row already contain documents, enrich directly first.
            row_docs = []
            row_links = []
            for link in match.get("links", []) or []:
                href = _clean(link.get("href"))
                label = _clean(link.get("text"))
                if not href:
                    continue
                obj = {"url": href, "label": label, "type": "document" if _is_doc_url(href) else "link"}
                row_links.append(obj)
                if _is_doc_url(href):
                    row_docs.append(obj)

            if row_docs:
                intel = {
                    "url": page.url,
                    "text": match.get("text", ""),
                    "links": row_links,
                    "document_links": row_docs,
                    "emails": [],
                    "reference": _extract_reference(match.get("text", "")),
                    "closing_date": _extract_closing_date(match.get("text", "")),
                }
                try:
                    page.screenshot(path=screenshot, full_page=True)
                except Exception:
                    screenshot = ""
                browser.close()
                return _build_enriched_candidate(candidate, intel, actions + ["used_row_document_links"], screenshot, match)

            _try_click_strategies(page, int(match.get("index", 0)), title, actions)

            # Sometimes data appears after row click but same page. Extract anyway.
            intel = _extract_current_page_intelligence(page)

            # If still no docs, try clicking visible "View", "Details", "Download" buttons/links that appeared.
            if not intel.get("document_links"):
                for text in ["View", "Details", "Tender Details", "Download", "Documents", "Bid Documents"]:
                    try:
                        old_url = page.url
                        locator = page.get_by_text(text, exact=False).first
                        if locator.count() > 0:
                            locator.click(timeout=6000)
                            actions.append(f"clicked_secondary_text:{text}")
                            _wait_after_click(page, old_url, actions)
                            intel = _extract_current_page_intelligence(page)
                            if intel.get("document_links") or intel.get("emails"):
                                break
                    except Exception as exc:
                        actions.append(f"secondary_click_failed:{text}:{str(exc)[:120]}")

            try:
                page.screenshot(path=screenshot, full_page=True)
            except Exception:
                screenshot = ""

            browser.close()
            return _build_enriched_candidate(candidate, intel, actions, screenshot, match)

    except Exception as exc:
        item = dict(candidate or {})
        item["v39_true_navigation_extraction"] = {
            "service_version": SERVICE_VERSION,
            "checked_at": _now(),
            "status": "error",
            "message": str(exc),
            "actions": actions,
            "proof_screenshot": screenshot,
        }
        return item


def run_v39_from_v36(
    max_portals: int = 1,
    enable_auto_quote: bool = False,
    persist_to_live_store: bool = True,
    include_review: bool = False,
) -> Dict[str, Any]:
    from app.services.interactive_playwright_extractor_v36_service import run_v36_interactive_extraction

    v36 = run_v36_interactive_extraction(
        max_portals=max_portals,
        enable_auto_quote=False,
        persist_to_live_store=persist_to_live_store,
        include_review_in_pipeline=False,
    )

    candidates: List[Dict[str, Any]] = []
    candidates.extend(v36.get("accepted_items", []))
    if include_review:
        candidates.extend(v36.get("review_items", []))

    enriched_items = [true_navigation_extract_candidate(c) for c in candidates]
    ok_items = [
        x for x in enriched_items
        if x.get("v39_true_navigation_extraction", {}).get("status") == "ok"
    ]

    auto_quote_results = []
    if enable_auto_quote and enriched_items:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch
            auto_quote_results = run_tender_pipeline_batch(
                enriched_items,
                source="v39-true-navigation-extraction",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{"status": "error", "stage": "v39_pipeline_batch", "message": str(exc)}]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "v36_candidate_total": v36.get("candidate_total", 0),
        "v36_accepted_total": v36.get("accepted_total", 0),
        "v36_review_total": v36.get("review_total", 0),
        "v39_input_total": len(candidates),
        "v39_enriched_total": len(ok_items),
        "pipeline_candidate_total": len(enriched_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "v36_result": v36,
        "items": enriched_items,
        "enriched_items": ok_items,
    }
    result["log_path"] = _write_log("v39_from_v36", result)
    return result
