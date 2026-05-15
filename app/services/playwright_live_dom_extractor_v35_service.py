from __future__ import annotations

"""
LMCP V35 Playwright Live DOM Extractor

Drop-in:
    app/services/playwright_live_dom_extractor_v35_service.py

Purpose:
    Extract tender/RFQ rows from JavaScript-rendered procurement portals.
    V34 proved requests+BeautifulSoup is too shallow for eTenders and similar sites.
    V35 opens the real browser DOM, waits for dynamic content, and extracts visible rows/cards.

Safe design:
    - Does not replace current harvesters.
    - Runs headless inside Docker by default.
    - Uses short bounded waits.
    - Scores candidates before sending to pipeline.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

SERVICE_VERSION = "V35_PLAYWRIGHT_LIVE_DOM_EXTRACTOR"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOG_DIR = PROJECT_ROOT / "runtime" / "v35_playwright_live_dom" / "logs"
PROOF_DIR = PROJECT_ROOT / "runtime" / "v35_playwright_live_dom" / "proof"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROOF_DIR.mkdir(parents=True, exist_ok=True)

HEADLESS = str(os.getenv("V35_HEADLESS", "true")).strip().lower() == "true"
TIMEOUT_MS = int(str(os.getenv("V35_TIMEOUT_MS", "45000")).strip() or "45000")
WAIT_MS = int(str(os.getenv("V35_WAIT_MS", "5000")).strip() or "5000")
MAX_ROWS = int(str(os.getenv("V35_MAX_ROWS", "120")).strip() or "120")
MAX_CARDS = int(str(os.getenv("V35_MAX_CARDS", "120")).strip() or "120")

PORTALS = [
    {
        "name": "National Treasury eTenders",
        "url": "https://www.etenders.gov.za/Home/opportunities",
        "source": "v35-etenders",
        "wait_selectors": ["table", "tr", ".dataTables_wrapper", "#tenderList", ".tender"],
    },
    {
        "name": "Transnet Tenders",
        "url": "https://transnetetenders.azurewebsites.net/",
        "source": "v35-transnet",
        "wait_selectors": ["table", "tr", ".card", "a"],
    },
    {
        "name": "SANRAL Tenders",
        "url": "https://www.nra.co.za/service-provider-zone/tenders/",
        "source": "v35-sanral",
        "wait_selectors": ["table", "tr", ".views-row", ".tender"],
    },
]

NOISE_EXACT = {
    "tenders",
    "tender",
    "advertised tenders",
    "currently advertised",
    "currently advertised tenders",
    "tender description",
    "category tender description esubmission advertised closing",
    "sign in/register",
    "vision and mission",
    "procurement plans",
    "home",
    "download",
    "downloads",
    "click here",
    "save tender: easily save tenders to your profile.",
    "division name email address telephone no",
}

CONTACT_WORDS = [
    "email address",
    "telephone no",
    "toll free",
    "fax:",
    "callback:",
    "ethicshelpdesk",
    "reportit@",
    "mailto:",
]

EXCLUDED = [
    "medical",
    "biomedical",
    "pharmaceutical",
    "medicine",
    "surgical",
    "clinic",
    "hospital",
    "manikin",
    "manikins",
    "ict",
    "it equipment",
    "computer",
    "laptop",
    "server",
    "software",
    "printer",
    "fuel",
    "diesel",
    "petrol",
    "catering",
]

POSITIVE_PROCUREMENT = [
    "supply",
    "delivery",
    "supply and delivery",
    "goods",
    "materials",
    "equipment",
    "stationery",
    "furniture",
    "uniform",
    "ppe",
    "tools",
    "corporate gifts",
    "gift packs",
    "consumables",
    "provision",
    "appointment of service provider",
    "procurement",
    "request for quotation",
    "rfq",
    "bid",
    "tender",
]

SUPPLY_STRONG = [
    "supply",
    "delivery",
    "supply and delivery",
    "goods",
    "materials",
    "stationery",
    "furniture",
    "uniform",
    "ppe",
    "tools",
    "corporate gifts",
    "gift packs",
    "consumables",
]

RFQ_SIGNALS = [
    "rfq",
    "request for quotation",
    "quotation",
    "quote",
    "bid",
    "tender",
    "closing date",
    "closing time",
    "submission",
    "compulsory briefing",
    "non-compulsory briefing",
    "briefing",
    "advertised",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _write_log(prefix: str, data: Dict[str, Any]) -> str:
    try:
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
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
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(0)
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
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _clean(match.group(0))
    return ""


def _doc_url(url: str) -> bool:
    u = _lower(url)
    return any(x in u for x in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"])


def _is_contact_or_menu(text: Any) -> bool:
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
    text = " ".join(
        _clean(item.get(k))
        for k in ["title", "description", "raw_text", "document_url", "detail_url"]
        if _clean(item.get(k))
    ).lower()

    score = 0
    reasons: List[str] = []

    if _is_contact_or_menu(item.get("title")):
        score -= 45
        reasons.append("contact_menu_or_noise_title")

    excluded = [x for x in EXCLUDED if x in text]
    if excluded:
        score -= 80
        reasons.append("excluded:" + ",".join(excluded[:5]))

    procurement_hits = [x for x in POSITIVE_PROCUREMENT if x in text]
    strong_supply_hits = [x for x in SUPPLY_STRONG if x in text]
    rfq_hits = [x for x in RFQ_SIGNALS if x in text]

    if procurement_hits:
        score += min(35, len(procurement_hits) * 8)
    else:
        reasons.append("no_procurement_signal")

    if strong_supply_hits:
        score += min(35, len(strong_supply_hits) * 12)
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
        "strong_supply_hits": strong_supply_hits[:10],
        "rfq_hits": rfq_hits[:10],
        "excluded_hits": excluded[:10],
        "checked_at": _now(),
    }


def _apply_flags(item: Dict[str, Any]) -> Dict[str, Any]:
    decision = item.get("v35_playwright_extraction", {}).get("decision")
    score = item.get("v35_playwright_extraction", {}).get("score")
    reasons = item.get("v35_playwright_extraction", {}).get("reasons", [])

    if decision == "accept":
        item["eligible"] = True
        item["quote_ready"] = True
        item["pipeline_status"] = "v35_playwright_accepted"
        item["submission_status"] = ""
        item["exclusion_reason"] = ""
        item["eligibility_reason"] = f"V35 Playwright extractor accepted with score {score}"
    elif decision == "review":
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "v35_playwright_review"
        item["submission_status"] = "manual_review_required"
        item["exclusion_reason"] = ";".join(reasons)
        item["eligibility_reason"] = f"V35 review with score {score}"
    else:
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "v35_playwright_rejected"
        item["submission_status"] = "skipped"
        item["exclusion_reason"] = ";".join(reasons)
        item["eligibility_reason"] = f"V35 rejected with score {score}"
    return item


def _choose_title_from_cells(cells: List[str]) -> str:
    useful = []
    for c in cells:
        if not _is_contact_or_menu(c):
            useful.append(c)

    procurement = [c for c in useful if any(w in c.lower() for w in POSITIVE_PROCUREMENT)]
    if procurement:
        return max(procurement, key=len)[:240]

    if useful:
        return max(useful, key=len)[:240]
    return ""


def _row_to_item(row: Dict[str, Any], portal: Dict[str, Any]) -> Dict[str, Any] | None:
    cells = [_clean(c) for c in row.get("cells", []) if _clean(c)]
    raw = _clean(" ".join(cells))
    if len(cells) < 2 or _is_contact_or_menu(raw):
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

    title = _choose_title_from_cells(cells)
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
        "source": portal.get("source", "v35-portal"),
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
    item["v35_playwright_extraction"] = _score(item)
    return _apply_flags(item)


def _card_to_item(card: Dict[str, Any], portal: Dict[str, Any]) -> Dict[str, Any] | None:
    raw = _clean(card.get("text"))
    if len(raw) < 40 or _is_contact_or_menu(raw):
        return None

    low = raw.lower()
    if not any(w in low for w in RFQ_SIGNALS + POSITIVE_PROCUREMENT):
        return None

    links = card.get("links", []) or []
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

    title = _clean(card.get("title")) or raw[:220]
    if _is_contact_or_menu(title):
        return None

    reference = _ref(raw) or _ref(title) or title[:120]
    item = {
        "title": title[:240],
        "description": raw[:3000],
        "raw_text": raw[:6000],
        "buyer_name": portal.get("name", ""),
        "buyer_rfq_number": reference,
        "rfq_number": reference,
        "reference_number": reference,
        "source": portal.get("source", "v35-portal"),
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
    item["v35_playwright_extraction"] = _score(item)
    return _apply_flags(item)


def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        key = (
            _lower(item.get("buyer_rfq_number")),
            _lower(item.get("title")),
            _lower(item.get("document_url") or item.get("detail_url")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def extract_live_dom_portal(portal: Dict[str, Any]) -> Dict[str, Any]:
    url = _clean(portal.get("url"))
    if not url:
        return {"status": "error", "service_version": SERVICE_VERSION, "message": "Missing URL", "items": []}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": f"Playwright is not available: {exc}",
            "items": [],
        }

    screenshot_path = str(PROOF_DIR / f"v35_{portal.get('source','portal')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

            for selector in portal.get("wait_selectors", []):
                try:
                    page.wait_for_selector(selector, timeout=8000)
                    break
                except Exception:
                    pass

            page.wait_for_timeout(WAIT_MS)

            try:
                page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                screenshot_path = ""

            rows = page.evaluate(
                       """ (maxRows) => Array.from(document.querySelectorAll('table tr')).slice(0, maxRows[0]).map((tr) => {
                    const cells = Array.from(tr.querySelectorAll('td,th')).map(td => (td.innerText || '').trim()).filter(Boolean);
                    const links = Array.from(tr.querySelectorAll('a[href]')).map(a => ({href: a.href, text: (a.innerText || '').trim()}));
                    return {cells, links, text: (tr.innerText || '').trim()};
                })""",
                MAX_ROWS,
            )

            cards = page.evaluate(
                        """(maxCards) => {
                    const selectors = ['.card','.panel','.views-row','.tender','.tender-item','.opportunity','.opportunity-item','article','li','div[class*=tender]','div[class*=rfq]','div[class*=bid]'];
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
            "proof_screenshot": screenshot_path if screenshot_path else "",
            "items": [],
        }

    items: List[Dict[str, Any]] = []

    for row in rows or []:
        item = _row_to_item(row, portal)
        if item:
            items.append(item)

    for card in cards or []:
        item = _card_to_item(card, portal)
        if item:
            items.append(item)

    items = _dedupe(items)

    accepted = [x for x in items if x.get("v35_playwright_extraction", {}).get("decision") == "accept"]
    review = [x for x in items if x.get("v35_playwright_extraction", {}).get("decision") == "review"]
    rejected = [x for x in items if x.get("v35_playwright_extraction", {}).get("decision") == "reject"]

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal": portal,
        "url": url,
        "proof_screenshot": screenshot_path,
        "raw_row_count": len(rows or []),
        "raw_card_count": len(cards or []),
        "candidate_total": len(items),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len(rejected),
        "items": items,
        "accepted_items": accepted,
        "review_items": review,
        "rejected_items": rejected,
    }


def run_v35_live_dom_extraction(
    max_portals: int = 3,
    enable_auto_quote: bool = True,
    persist_to_live_store: bool = True,
    include_review_in_pipeline: bool = False,
) -> Dict[str, Any]:
    portals = PORTALS[:max(1, int(max_portals or 3))]
    portal_results: List[Dict[str, Any]] = []
    all_items: List[Dict[str, Any]] = []
    accepted: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []

    for portal in portals:
        result = extract_live_dom_portal(portal)
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
                source="v35-playwright-live-dom",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{"status": "error", "stage": "v35_pipeline_batch", "message": str(exc)}]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal_count": len(portals),
        "candidate_total": len(all_items),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len([x for x in all_items if x.get("v35_playwright_extraction", {}).get("decision") == "reject"]),
        "pipeline_candidate_total": len(pipeline_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "portal_results": portal_results,
        "items": all_items,
        "accepted_items": accepted,
        "review_items": review,
    }
    result["log_path"] = _write_log("v35_live_dom_extraction", result)
    return result
