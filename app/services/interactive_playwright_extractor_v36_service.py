from __future__ import annotations

"""
LMCP V36 Interactive Playwright Extractor

Drop-in:
    app/services/interactive_playwright_extractor_v36_service.py

Purpose:
    V35 proved Playwright can open the live DOM, but eTenders still needs interaction.
    V36 clicks likely tabs/buttons, scrolls, waits for dynamic content, handles pagination
    where possible, and then extracts RFQ/tender rows/cards.

Safe design:
    - Add-on only, does not replace V31-V35.
    - Headless by default.
    - Uses bounded waits.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SERVICE_VERSION = "V36_INTERACTIVE_PLAYWRIGHT_EXTRACTOR"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOG_DIR = PROJECT_ROOT / "runtime" / "v36_interactive_playwright" / "logs"
PROOF_DIR = PROJECT_ROOT / "runtime" / "v36_interactive_playwright" / "proof"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROOF_DIR.mkdir(parents=True, exist_ok=True)

HEADLESS = str(os.getenv("V36_HEADLESS", "true")).strip().lower() == "true"
TIMEOUT_MS = int(str(os.getenv("V36_TIMEOUT_MS", "60000")).strip() or "60000")
WAIT_MS = int(str(os.getenv("V36_WAIT_MS", "3000")).strip() or "3000")
MAX_ROWS = int(str(os.getenv("V36_MAX_ROWS", "250")).strip() or "250")
MAX_CARDS = int(str(os.getenv("V36_MAX_CARDS", "200")).strip() or "200")

PORTALS = [
    {
        "name": "National Treasury eTenders",
        "url": "https://www.etenders.gov.za/Home/opportunities",
        "source": "v36-etenders",
        "click_texts": [
            "Currently Advertised",
            "Tender Opportunities",
            "Search",
            "Apply",
        ],
        "wait_selectors": [
            "table tbody tr",
            "table tr",
            ".dataTables_wrapper",
            "#tenderList",
            ".tender",
        ],
    },
]

NOISE_EXACT = {
    "tenders", "tender", "advertised tenders", "currently advertised",
    "currently advertised tenders", "tender description",
    "category tender description esubmission advertised closing",
    "sign in/register", "vision and mission", "procurement plans",
    "home", "download", "downloads", "click here",
    "save tender: easily save tenders to your profile.",
    "division name email address telephone no",
}

CONTACT_WORDS = [
    "email address", "telephone no", "toll free", "fax:", "callback:",
    "ethicshelpdesk", "reportit@", "mailto:",
]

EXCLUDED = [
    "medical", "biomedical", "pharmaceutical", "medicine", "surgical",
    "clinic", "hospital", "manikin", "manikins", "ict", "it equipment",
    "computer", "laptop", "server", "software", "printer", "fuel",
    "diesel", "petrol", "catering",
]

POSITIVE_PROCUREMENT = [
    "supply", "delivery", "supply and delivery", "goods", "materials",
    "equipment", "stationery", "furniture", "uniform", "ppe", "tools",
    "corporate gifts", "gift packs", "consumables", "provision",
    "appointment of service provider", "procurement", "request for quotation",
    "rfq", "bid", "tender",
]

SUPPLY_STRONG = [
    "supply", "delivery", "supply and delivery", "goods", "materials",
    "stationery", "furniture", "uniform", "ppe", "tools",
    "corporate gifts", "gift packs", "consumables",
]

RFQ_SIGNALS = [
    "rfq", "request for quotation", "quotation", "quote", "bid", "tender",
    "closing date", "closing time", "submission", "compulsory briefing",
    "non-compulsory briefing", "briefing", "advertised", "description",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\xa0", " ")).strip()


def _lower(v: Any) -> str:
    return _clean(v).lower()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _date(text: str) -> str:
    text = _clean(text)
    patterns = [
        r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]20\d{2}\b",
        r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(0)
    return ""


def _ref(text: str) -> str:
    patterns = [
        r"\bRFQ[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bRFP[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bBID[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bTENDER[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\b[A-Z]{1,6}/[A-Z0-9]{1,8}\s*\d{1,5}/\d{2,4}\b",
        r"\b[A-Z]{2,8}\s*\d{2,6}/\d{2,4}\b",
        r"\b\d{2,5}/\d{2,4}\b",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return _clean(m.group(0))
    return ""


def _doc_url(url: str) -> bool:
    u = _lower(url)
    return any(x in u for x in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"])


def _is_noise(text: Any) -> bool:
    low = _lower(text)
    if not low:
        return True
    if low in NOISE_EXACT:
        return True
    if any(w in low for w in CONTACT_WORDS):
        return True
    if "@" in low and not any(sig in low for sig in RFQ_SIGNALS):
        return True
    if len(low) < 18:
        return True
    return False


def _score(item: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(_clean(item.get(k)) for k in ["title", "description", "raw_text", "document_url", "detail_url"]).lower()
    score = 0
    reasons: List[str] = []

    if _is_noise(item.get("title")):
        score -= 45
        reasons.append("noise_title")

    excluded = [x for x in EXCLUDED if x in text]
    if excluded:
        score -= 80
        reasons.append("excluded:" + ",".join(excluded[:5]))

    procurement_hits = [x for x in POSITIVE_PROCUREMENT if x in text]
    supply_hits = [x for x in SUPPLY_STRONG if x in text]
    rfq_hits = [x for x in RFQ_SIGNALS if x in text]

    if procurement_hits:
        score += min(35, len(procurement_hits) * 8)
    else:
        reasons.append("no_procurement_signal")

    if supply_hits:
        score += min(35, len(supply_hits) * 12)
    else:
        reasons.append("no_strong_supply_signal")

    if rfq_hits:
        score += min(25, len(rfq_hits) * 7)
    else:
        reasons.append("no_rfq_signal")

    if item.get("closing_date"):
        score += 20
    else:
        reasons.append("no_closing_date")

    if item.get("document_url"):
        score += 20
    elif item.get("detail_url"):
        score += 8
    else:
        reasons.append("no_document_or_detail_url")

    if item.get("buyer_rfq_number") and item.get("buyer_rfq_number") != item.get("title"):
        score += 10

    score = max(0, min(100, int(score)))

    if excluded:
        decision = "reject"
    elif score >= 62:
        decision = "accept"
    elif score >= 42:
        decision = "review"
    else:
        decision = "reject"

    return {
        "service_version": SERVICE_VERSION,
        "decision": decision,
        "score": score,
        "reasons": reasons,
        "procurement_hits": procurement_hits[:10],
        "strong_supply_hits": supply_hits[:10],
        "rfq_hits": rfq_hits[:10],
        "excluded_hits": excluded[:10],
        "checked_at": _now(),
    }


def _apply_flags(item: Dict[str, Any]) -> Dict[str, Any]:
    cls = item.get("v36_interactive_extraction", {})
    decision = cls.get("decision")
    score = cls.get("score")
    reasons = cls.get("reasons", [])
    if decision == "accept":
        item["eligible"] = True
        item["quote_ready"] = True
        item["pipeline_status"] = "v36_interactive_accepted"
        item["submission_status"] = ""
        item["exclusion_reason"] = ""
        item["eligibility_reason"] = f"V36 accepted with score {score}"
    elif decision == "review":
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "v36_interactive_review"
        item["submission_status"] = "manual_review_required"
        item["exclusion_reason"] = ";".join(reasons)
        item["eligibility_reason"] = f"V36 review with score {score}"
    else:
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "v36_interactive_rejected"
        item["submission_status"] = "skipped"
        item["exclusion_reason"] = ";".join(reasons)
        item["eligibility_reason"] = f"V36 rejected with score {score}"
    return item


def _title_from_cells(cells: List[str]) -> str:
    useful = [c for c in cells if not _is_noise(c)]
    procurement = [c for c in useful if any(w in c.lower() for w in POSITIVE_PROCUREMENT)]
    if procurement:
        return max(procurement, key=len)[:240]
    if useful:
        return max(useful, key=len)[:240]
    return ""


def _row_to_item(row: Dict[str, Any], portal: Dict[str, Any]) -> Dict[str, Any] | None:
    cells = [_clean(c) for c in row.get("cells", []) if _clean(c)]
    raw = _clean(" ".join(cells))
    if len(cells) < 2 or _is_noise(raw):
        return None

    low = raw.lower()
    header_terms = ["tender no", "project type", "province", "description", "queries", "closing date"]
    if sum(1 for h in header_terms if h in low) >= 4 and len(cells) <= 8:
        return None

    links = row.get("links", []) or []
    doc = ""
    detail = ""
    for link in links:
        href = _clean(link.get("href"))
        if _doc_url(href):
            doc = href
            break
    if not doc:
        for link in links:
            href = _clean(link.get("href"))
            if href and not href.startswith("mailto:"):
                detail = href
                break

    title = _title_from_cells(cells)
    if not title:
        return None

    reference = _ref(raw) or _ref(title) or title[:120]
    item = {
        "title": title,
        "description": raw[:3000],
        "raw_text": raw[:6000],
        "buyer_name": portal.get("name", ""),
        "buyer_rfq_number": reference,
        "rfq_number": reference,
        "reference_number": reference,
        "source": portal.get("source", "v36-portal"),
        "source_name": portal.get("name", ""),
        "portal_name": portal.get("name", ""),
        "source_url": portal.get("url", ""),
        "document_url": doc,
        "detail_url": detail,
        "closing_date": _date(raw),
        "submission_method": "portal",
        "recipient_email": "",
        "buyer_email": "",
        "briefing_required": "compulsory briefing" in low,
        "items": [],
        "line_items": [],
        "auto_quote_enabled": False,
        "harvested_at": _now(),
    }
    item["v36_interactive_extraction"] = _score(item)
    return _apply_flags(item)


def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = (_lower(item.get("buyer_rfq_number")), _lower(item.get("title")), _lower(item.get("document_url") or item.get("detail_url")))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _interactive_steps(page, portal: Dict[str, Any]) -> List[str]:
    actions: List[str] = []

    # Click likely links/buttons/tabs.
    for text in portal.get("click_texts", []):
        try:
            locator = page.get_by_text(text, exact=False).first
            if locator.count() > 0:
                locator.click(timeout=5000)
                actions.append(f"clicked_text:{text}")
                page.wait_for_timeout(WAIT_MS)
        except Exception as exc:
            actions.append(f"click_failed:{text}:{str(exc)[:120]}")

    # Try common eTenders query strings if the visible click did not populate enough.
    for target in [
        "https://www.etenders.gov.za/Home/opportunities?id=1",
        "https://www.etenders.gov.za/Home/opportunities?id=2",
    ]:
        if "etenders.gov.za" in portal.get("url", ""):
            try:
                page.goto(target, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                actions.append(f"goto_variant:{target}")
                page.wait_for_timeout(WAIT_MS)
                break
            except Exception as exc:
                actions.append(f"variant_failed:{target}:{str(exc)[:120]}")

    # Scroll / trigger lazy loading.
    for i in range(4):
        try:
            page.evaluate("(y) => window.scrollTo(0, y)", 1000 * (i + 1))
            actions.append(f"scroll:{i+1}")
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # Try DataTables search with supply words where search input exists.
    for word in ["supply", "delivery", "stationery"]:
        try:
            search = page.locator("input[type='search']").first
            if search.count() > 0:
                search.fill(word)
                actions.append(f"datatable_search:{word}")
                page.wait_for_timeout(WAIT_MS)
                break
        except Exception as exc:
            actions.append(f"datatable_search_failed:{word}:{str(exc)[:120]}")

    # Wait for selectors.
    for selector in portal.get("wait_selectors", []):
        try:
            page.wait_for_selector(selector, timeout=8000)
            actions.append(f"selector_ready:{selector}")
            break
        except Exception:
            pass

    return actions


def extract_interactive_portal(portal: Dict[str, Any]) -> Dict[str, Any]:
    url = _clean(portal.get("url"))
    if not url:
        return {"status": "error", "service_version": SERVICE_VERSION, "message": "Missing URL", "items": []}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "service_version": SERVICE_VERSION, "message": f"Playwright unavailable: {exc}", "items": []}

    screenshot_path = str(PROOF_DIR / f"v36_{portal.get('source','portal')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
    actions: List[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            page.wait_for_timeout(WAIT_MS)

            actions.extend(_interactive_steps(page, portal))

            try:
                page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                screenshot_path = ""

            rows = page.evaluate(
                """(maxRows) => Array.from(document.querySelectorAll('table tr')).slice(0, maxRows).map((tr) => {
                    const cells = Array.from(tr.querySelectorAll('td,th')).map(td => (td.innerText || '').trim()).filter(Boolean);
                    const links = Array.from(tr.querySelectorAll('a[href]')).map(a => ({href: a.href, text: (a.innerText || '').trim()}));
                    return {cells, links, text: (tr.innerText || '').trim()};
                })""",
                MAX_ROWS,
            )

            # Pull all visible row-like blocks as fallback.
            blocks = page.evaluate(
                """(maxCards) => {
                    const selectors = ['.card','.panel','.views-row','.tender','.tender-item','.opportunity','.opportunity-item','article','li','div[class*=tender]','div[class*=rfq]','div[class*=bid]','tbody tr'];
                    const seen = new Set();
                    const out = [];
                    for (const sel of selectors) {
                        for (const el of Array.from(document.querySelectorAll(sel))) {
                            if (seen.has(el)) continue;
                            seen.add(el);
                            const text = (el.innerText || '').trim();
                            if (!text) continue;
                            const titleEl = el.querySelector('h1,h2,h3,h4,strong,b,a');
                            const title = titleEl ? (titleEl.innerText || '').trim() : '';
                            const links = Array.from(el.querySelectorAll('a[href]')).map(a => ({href: a.href, text: (a.innerText || '').trim()}));
                            out.push({text, title, links});
                            if (out.length >= maxCards) return out;
                        }
                    }
                    return out;
                }""",
                MAX_CARDS,
            )
            browser.close()
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "portal": portal,
            "url": url,
            "message": str(exc),
            "actions": actions,
            "proof_screenshot": screenshot_path,
            "items": [],
        }

    items: List[Dict[str, Any]] = []
    for row in rows or []:
        item = _row_to_item(row, portal)
        if item:
            items.append(item)

    # Convert block text into pseudo rows.
    for block in blocks or []:
        text = _clean(block.get("text"))
        if not text or _is_noise(text):
            continue
        links = block.get("links", []) or []
        cells = []
        title = _clean(block.get("title"))
        if title:
            cells.append(title)
        cells.append(text)
        item = _row_to_item({"cells": cells, "links": links}, portal)
        if item:
            items.append(item)

    items = _dedupe(items)

    accepted = [x for x in items if x.get("v36_interactive_extraction", {}).get("decision") == "accept"]
    review = [x for x in items if x.get("v36_interactive_extraction", {}).get("decision") == "review"]
    rejected = [x for x in items if x.get("v36_interactive_extraction", {}).get("decision") == "reject"]

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal": portal,
        "url": url,
        "actions": actions,
        "proof_screenshot": screenshot_path,
        "raw_row_count": len(rows or []),
        "raw_block_count": len(blocks or []),
        "candidate_total": len(items),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len(rejected),
        "items": items,
        "accepted_items": accepted,
        "review_items": review,
        "rejected_items": rejected,
    }


def run_v36_interactive_extraction(
    max_portals: int = 1,
    enable_auto_quote: bool = True,
    persist_to_live_store: bool = True,
    include_review_in_pipeline: bool = False,
) -> Dict[str, Any]:
    portals = PORTALS[:max(1, int(max_portals or 1))]
    portal_results: List[Dict[str, Any]] = []
    all_items: List[Dict[str, Any]] = []
    accepted: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []

    for portal in portals:
        result = extract_interactive_portal(portal)
        portal_results.append(result)
        all_items.extend(result.get("items", []))
        accepted.extend(result.get("accepted_items", []))
        review.extend(result.get("review_items", []))

    pipeline_items = list(accepted)
    if include_review_in_pipeline:
        pipeline_items.extend(review)

    auto_quote_results = []
    if enable_auto_quote and pipeline_items:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch
            auto_quote_results = run_tender_pipeline_batch(
                pipeline_items,
                source="v36-interactive-playwright",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{"status": "error", "stage": "v36_pipeline_batch", "message": str(exc)}]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal_count": len(portals),
        "candidate_total": len(all_items),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len([x for x in all_items if x.get("v36_interactive_extraction", {}).get("decision") == "reject"]),
        "pipeline_candidate_total": len(pipeline_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "portal_results": portal_results,
        "items": all_items,
        "accepted_items": accepted,
        "review_items": review,
    }
    result["log_path"] = _write_log("v36_interactive_extraction", result)
    return result
