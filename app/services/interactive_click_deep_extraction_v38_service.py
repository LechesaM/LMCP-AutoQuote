
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin

from app.core.runtime_paths import PROJECT_ROOT, ensure_directories

SERVICE_VERSION = "V38_INTERACTIVE_CLICK_DEEP_EXTRACTION"

LOG_DIR = PROJECT_ROOT / "runtime" / "v38_interactive_click_deep_extraction" / "logs"
PROOF_DIR = PROJECT_ROOT / "runtime" / "v38_interactive_click_deep_extraction" / "proof"


def ensure_v38_runtime_dirs() -> None:
    ensure_directories([LOG_DIR, PROOF_DIR])

HEADLESS = str(os.getenv("V38_HEADLESS", "true")).strip().lower() == "true"
TIMEOUT_MS = int(str(os.getenv("V38_TIMEOUT_MS", "60000")).strip() or "60000")
WAIT_MS = int(str(os.getenv("V38_WAIT_MS", "3000")).strip() or "3000")
MAX_DETAIL_LINKS = int(str(os.getenv("V38_MAX_DETAIL_LINKS", "80")).strip() or "80")

DOC_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

PORTAL = {
    "name": "National Treasury eTenders",
    "url": "https://www.etenders.gov.za/Home/opportunities",
    "source": "v38-etenders",
}

NOISE_EMAIL_HINTS = ["noreply", "no-reply", "donotreply", "webmaster", "ethicshelpdesk"]
SUBMISSION_HINTS = ["submit", "submission", "quotation", "quote", "tender", "procurement", "scm", "supplychain", "bid"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\xa0", " ")).strip()


def _lower(v: Any) -> str:
    return _clean(v).lower()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        ensure_v38_runtime_dirs()
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _doc_url(url: str) -> bool:
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
    for p in patterns:
        m = re.search(p, text, flags=re.I)
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
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return _clean(m.group(0))
    return ""


def _rank_emails(emails: List[str]) -> List[str]:
    unique = []
    seen = set()
    for email in emails:
        email = email.strip().strip(".,;:()[]<>")
        low = email.lower()
        if not email or low in seen:
            continue
        if any(x in low for x in NOISE_EMAIL_HINTS):
            continue
        seen.add(low)
        unique.append(email)

    def score(email: str) -> int:
        low = email.lower()
        return sum(10 for hint in SUBMISSION_HINTS if hint in low)

    return sorted(unique, key=score, reverse=True)


def _similar_title_match(candidate_title: str, row_text: str) -> bool:
    title = _lower(candidate_title)
    row = _lower(row_text)
    if not title or not row:
        return False
    if title in row:
        return True

    words = [w for w in re.split(r"[^a-z0-9]+", title) if len(w) > 3]
    if not words:
        return False

    hits = sum(1 for w in words if w in row)
    return hits >= max(3, int(len(words) * 0.55))


def _extract_page_intelligence(page, base_url: str) -> Dict[str, Any]:
    data = page.evaluate(
        """(maxLinks) => {
            const text = (document.body ? document.body.innerText : '') || '';
            const links = Array.from(document.querySelectorAll('a[href]')).slice(0, maxLinks).map(a => ({
                href: a.href || '',
                text: (a.innerText || a.getAttribute('title') || '').trim()
            }));
            const buttons = Array.from(document.querySelectorAll('button,input[type=button],input[type=submit]')).slice(0, 50).map(b => ({
                text: (b.innerText || b.value || b.getAttribute('title') || '').trim()
            }));
            return {text, links, buttons, url: location.href};
        }""",
        MAX_DETAIL_LINKS,
    )
    text = _clean(data.get("text", ""))

    links = []
    docs = []
    for link in data.get("links", []):
        href = _clean(link.get("href"))
        label = _clean(link.get("text"))
        if not href:
            continue
        obj = {"url": urljoin(base_url, href), "label": label, "type": "document" if _doc_url(href) else "link"}
        links.append(obj)
        if _doc_url(href):
            docs.append(obj)

    emails = EMAIL_RE.findall(text)
    for link in links:
        if link["url"].startswith("mailto:"):
            emails.append(link["url"].replace("mailto:", "").split("?")[0])

    submission_method = "portal"
    if emails:
        submission_method = "email"

    return {
        "url": data.get("url") or page.url,
        "text": text[:20000],
        "links": links[:MAX_DETAIL_LINKS],
        "document_links": docs[:30],
        "emails": _rank_emails(emails)[:20],
        "reference": _extract_reference(text),
        "closing_date": _extract_closing_date(text),
        "submission_method": submission_method,
        "buttons": data.get("buttons", []),
    }


def _activate_etenders_table(page) -> List[str]:
    actions = []
    page.goto(PORTAL["url"], wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    page.wait_for_timeout(WAIT_MS)

    for target in [
        "https://www.etenders.gov.za/Home/opportunities?id=1",
        "https://www.etenders.gov.za/Home/opportunities?id=2",
    ]:
        try:
            page.goto(target, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            actions.append(f"goto_variant:{target}")
            page.wait_for_timeout(WAIT_MS)
            break
        except Exception as exc:
            actions.append(f"variant_failed:{target}:{str(exc)[:120]}")

    for i in range(4):
        try:
            page.evaluate("(y) => window.scrollTo(0, y)", 900 * (i + 1))
            page.wait_for_timeout(700)
            actions.append(f"scroll:{i+1}")
        except Exception:
            pass

    try:
        page.wait_for_selector("table tbody tr, table tr", timeout=12000)
        actions.append("selector_ready:table_rows")
    except Exception as exc:
        actions.append(f"selector_failed:table_rows:{str(exc)[:120]}")

    return actions


def _collect_rows(page) -> List[Dict[str, Any]]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('table tr')).map((tr, index) => {
            const cells = Array.from(tr.querySelectorAll('td,th')).map(td => (td.innerText || '').trim()).filter(Boolean);
            const links = Array.from(tr.querySelectorAll('a[href]')).map(a => ({href: a.href, text: (a.innerText || '').trim()}));
            const rect = tr.getBoundingClientRect();
            return {index, cells, links, text: (tr.innerText || '').trim(), x: rect.x, y: rect.y, width: rect.width, height: rect.height};
        }).filter(r => r.text && r.text.length > 10)"""
    )


def _click_row_by_index(page, index: int, actions: List[str]) -> None:
    # Try link inside row first.
    try:
        locator = page.locator("table tr").nth(index)
        links = locator.locator("a[href]")
        if links.count() > 0:
            links.first.click(timeout=8000)
            actions.append(f"clicked_row_link:{index}")
            page.wait_for_timeout(WAIT_MS)
            return
    except Exception as exc:
        actions.append(f"row_link_click_failed:{index}:{str(exc)[:120]}")

    # Try row click.
    try:
        page.locator("table tr").nth(index).click(timeout=8000)
        actions.append(f"clicked_row:{index}")
        page.wait_for_timeout(WAIT_MS)
        return
    except Exception as exc:
        actions.append(f"row_click_failed:{index}:{str(exc)[:120]}")


def _apply_enrichment(candidate: Dict[str, Any], intel: Dict[str, Any], actions: List[str], screenshot: str) -> Dict[str, Any]:
    item = dict(candidate or {})
    docs = intel.get("document_links", []) or []
    emails = intel.get("emails", []) or []

    if docs:
        item["document_url"] = item.get("document_url") or docs[0].get("url", "")
        item["discovered_documents"] = docs

    if emails:
        item["buyer_email"] = item.get("buyer_email") or emails[0]
        item["recipient_email"] = item.get("recipient_email") or emails[0]
        item["submission_email"] = item.get("submission_email") or emails[0]
        item["submission_method"] = "email"
    else:
        item["submission_method"] = item.get("submission_method") or intel.get("submission_method") or "portal"

    if intel.get("reference"):
        item["buyer_rfq_number"] = intel["reference"]
        item["rfq_number"] = intel["reference"]
        item["reference_number"] = intel["reference"]

    if intel.get("closing_date") and not item.get("closing_date"):
        item["closing_date"] = intel["closing_date"]

    deep_text = _clean(" ".join([item.get("raw_text", ""), item.get("description", ""), intel.get("text", "")]))
    item["deep_rfq_text"] = deep_text[:25000]
    item["discovered_emails"] = emails
    item["detail_url"] = item.get("detail_url") or intel.get("url", "")

    status = "ok" if (docs or emails or intel.get("reference")) else "opened_but_no_docs_or_email"
    item["v38_interactive_click_deep_extraction"] = {
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "status": status,
        "document_count": len(docs),
        "email_count": len(emails),
        "has_reference": bool(intel.get("reference")),
        "detail_url": intel.get("url", ""),
        "proof_screenshot": screenshot,
        "actions": actions,
    }
    item["updated_at"] = _now()
    return item


def deep_click_extract_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    ensure_v38_runtime_dirs()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        item = dict(candidate or {})
        item["v38_interactive_click_deep_extraction"] = {"service_version": SERVICE_VERSION, "status": "error", "message": f"Playwright unavailable: {exc}", "checked_at": _now()}
        return item

    title = _clean(candidate.get("title"))
    actions: List[str] = []
    screenshot = str(PROOF_DIR / f"v38_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            actions.extend(_activate_etenders_table(page))

            rows = _collect_rows(page)
            match = None
            for row in rows:
                if _similar_title_match(title, row.get("text", "")):
                    match = row
                    break

            if not match:
                # Try direct text click as fallback.
                try:
                    page.get_by_text(title[:80], exact=False).first.click(timeout=8000)
                    actions.append("clicked_by_text")
                    page.wait_for_timeout(WAIT_MS)
                except Exception as exc:
                    actions.append(f"text_click_failed:{str(exc)[:180]}")
            else:
                actions.append(f"matched_row_index:{match.get('index')}")
                # First use row links if already present.
                link_docs = []
                link_details = []
                for link in match.get("links", []):
                    href = _clean(link.get("href"))
                    if _doc_url(href):
                        link_docs.append({"url": href, "label": link.get("text", ""), "type": "document"})
                    elif href:
                        link_details.append(href)

                if link_docs:
                    intel = {
                        "url": page.url,
                        "text": match.get("text", ""),
                        "document_links": link_docs,
                        "emails": [],
                        "reference": _extract_reference(match.get("text", "")),
                        "closing_date": _extract_closing_date(match.get("text", "")),
                        "submission_method": "portal",
                    }
                    try:
                        page.screenshot(path=screenshot, full_page=True)
                    except Exception:
                        screenshot = ""
                    browser.close()
                    return _apply_enrichment(candidate, intel, actions + ["used_row_document_links"], screenshot)

                _click_row_by_index(page, int(match.get("index", 0)), actions)

            try:
                page.screenshot(path=screenshot, full_page=True)
            except Exception:
                screenshot = ""

            intel = _extract_page_intelligence(page, PORTAL["url"])
            browser.close()
            return _apply_enrichment(candidate, intel, actions, screenshot)

    except Exception as exc:
        item = dict(candidate or {})
        item["v38_interactive_click_deep_extraction"] = {
            "service_version": SERVICE_VERSION,
            "checked_at": _now(),
            "status": "error",
            "message": str(exc),
            "actions": actions,
            "proof_screenshot": screenshot,
        }
        return item


def run_v38_from_v36(
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

    enriched = [deep_click_extract_candidate(c) for c in candidates]
    enriched_ok = [x for x in enriched if x.get("v38_interactive_click_deep_extraction", {}).get("status") == "ok"]

    auto_quote_results = []
    if enable_auto_quote and enriched:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch
            auto_quote_results = run_tender_pipeline_batch(
                enriched,
                source="v38-interactive-click-deep-extraction",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{"status": "error", "stage": "v38_pipeline_batch", "message": str(exc)}]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "v36_candidate_total": v36.get("candidate_total", 0),
        "v36_accepted_total": v36.get("accepted_total", 0),
        "v36_review_total": v36.get("review_total", 0),
        "v38_input_total": len(candidates),
        "v38_enriched_total": len(enriched_ok),
        "pipeline_candidate_total": len(enriched),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "v36_result": v36,
        "items": enriched,
        "enriched_items": enriched_ok,
    }
    result["log_path"] = _write_log("v38_from_v36", result)
    return result
