from __future__ import annotations

"""
LMCP V34 Structured RFQ Extractor

Drop-in:
    app/services/structured_rfq_extractor_v34_service.py

Purpose:
    Upgrade V33 by extracting structured tender rows/cards instead of menus,
    contact blocks, page headings, and generic links.

Key idea:
    - Prefer table rows with enough cells and RFQ/date/link signals.
    - Reject contact-directory rows.
    - Reject headers and navigation.
    - Accept broader procurement language: provision, appointment, procurement,
      supply, delivery, goods, services only when appropriate.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SERVICE_VERSION = "V34_STRUCTURED_RFQ_EXTRACTOR"

PROJECT_ROOT = Path(os.getenv("LMCP_PROJECT_ROOT", "/app")).resolve()
LOG_DIR = PROJECT_ROOT / "runtime" / "v34_structured_rfq_extractor" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = int(str(os.getenv("V34_TIMEOUT", "35")).strip() or "35")
MAX_ROWS = int(str(os.getenv("V34_MAX_ROWS", "250")).strip() or "250")
MAX_CARDS = int(str(os.getenv("V34_MAX_CARDS", "150")).strip() or "150")

PORTALS = [
    {
        "name": "National Treasury eTenders",
        "url": "https://www.etenders.gov.za/Home/opportunities",
        "source": "v34-etenders",
    },
    {
        "name": "Transnet Tenders",
        "url": "https://transnetetenders.azurewebsites.net/",
        "source": "v34-transnet",
    },
    {
        "name": "SANRAL Tenders",
        "url": "https://www.nra.co.za/service-provider-zone/tenders/",
        "source": "v34-sanral",
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


def _fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


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


def _is_contact_or_menu(text: str) -> bool:
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


def _cell_title(cells: List[str]) -> str:
    # Prefer the longest procurement-looking cell, not headers.
    useful = []
    for c in cells:
        low = c.lower()
        if _is_contact_or_menu(c):
            continue
        if low in NOISE_EXACT:
            continue
        useful.append(c)

    if not useful:
        return ""

    procurement = [
        c for c in useful
        if any(w in c.lower() for w in POSITIVE_PROCUREMENT)
    ]
    if procurement:
        return max(procurement, key=len)[:240]
    return max(useful, key=len)[:240]


def _score(item: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(
        _clean(item.get(k))
        for k in ["title", "description", "raw_text", "document_url", "detail_url"]
        if _clean(item.get(k))
    ).lower()

    score = 0
    reasons = []

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


def _item_from_row(row, portal: Dict[str, Any], base_url: str) -> Dict[str, Any] | None:
    cells = [_clean(c.get_text(" ", strip=True)) for c in row.find_all(["td", "th"])]
    cells = [c for c in cells if c]
    if len(cells) < 2:
        return None

    raw = _clean(" ".join(cells))
    if _is_contact_or_menu(raw):
        return None

    # Reject pure table headers.
    low = raw.lower()
    header_terms = ["tender no", "project type", "province", "description", "queries", "closing date"]
    if sum(1 for h in header_terms if h in low) >= 4 and len(cells) <= 8:
        return None

    links = []
    for a in row.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        label = _clean(a.get_text(" ", strip=True))
        if href.startswith("mailto:"):
            continue
        links.append({"url": href, "label": label})

    doc = ""
    detail = ""
    for link in links:
        if _doc_url(link["url"]):
            doc = link["url"]
            break
    if not doc and links:
        detail = links[0]["url"]

    title = _cell_title(cells)
    if not title:
        return None

    reference = _ref(raw) or _ref(title) or title[:120]
    closing = _date(raw)

    item = {
        "title": title,
        "description": raw[:3000],
        "raw_text": raw[:6000],
        "buyer_name": portal.get("name", ""),
        "buyer_rfq_number": reference,
        "rfq_number": reference,
        "reference_number": reference,
        "source": portal.get("source", "v34-portal"),
        "source_name": portal.get("name", ""),
        "portal_name": portal.get("name", ""),
        "source_url": base_url,
        "document_url": doc,
        "detail_url": detail,
        "closing_date": closing,
        "submission_method": "portal",
        "recipient_email": "",
        "buyer_email": "",
        "briefing_required": "compulsory briefing" in low,
        "items": [],
        "line_items": [],
        "auto_quote_enabled": False,
        "harvested_at": _now(),
    }
    item["v34_structured_extraction"] = _score(item)
    _apply_flags(item)
    return item


def _item_from_card(node, portal: Dict[str, Any], base_url: str) -> Dict[str, Any] | None:
    raw = _clean(node.get_text(" ", strip=True))
    if len(raw) < 40 or _is_contact_or_menu(raw):
        return None

    low = raw.lower()
    if not any(w in low for w in RFQ_SIGNALS + POSITIVE_PROCUREMENT):
        return None

    links = []
    for a in node.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if href.startswith("mailto:"):
            continue
        label = _clean(a.get_text(" ", strip=True))
        links.append({"url": href, "label": label})

    doc = ""
    detail = ""
    for link in links:
        if _doc_url(link["url"]):
            doc = link["url"]
            break
    if not doc and links:
        detail = links[0]["url"]

    # Card title preference: heading, then first strong anchor, then first sentence.
    title = ""
    for tag in node.find_all(["h1", "h2", "h3", "h4", "strong", "b", "a"]):
        t = _clean(tag.get_text(" ", strip=True))
        if len(t) >= 15 and not _is_contact_or_menu(t):
            title = t[:240]
            break
    if not title:
        title = raw[:220]

    reference = _ref(raw) or _ref(title) or title[:120]
    item = {
        "title": title,
        "description": raw[:3000],
        "raw_text": raw[:6000],
        "buyer_name": portal.get("name", ""),
        "buyer_rfq_number": reference,
        "rfq_number": reference,
        "reference_number": reference,
        "source": portal.get("source", "v34-portal"),
        "source_name": portal.get("name", ""),
        "portal_name": portal.get("name", ""),
        "source_url": base_url,
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
    item["v34_structured_extraction"] = _score(item)
    _apply_flags(item)
    return item


def _apply_flags(item: Dict[str, Any]) -> None:
    decision = item.get("v34_structured_extraction", {}).get("decision")
    score = item.get("v34_structured_extraction", {}).get("score")
    reasons = item.get("v34_structured_extraction", {}).get("reasons", [])
    if decision == "accept":
        item["eligible"] = True
        item["quote_ready"] = True
        item["pipeline_status"] = "v34_structured_accepted"
        item["submission_status"] = ""
        item["exclusion_reason"] = ""
        item["eligibility_reason"] = f"V34 structured extractor accepted with score {score}"
    elif decision == "review":
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "v34_structured_review"
        item["submission_status"] = "manual_review_required"
        item["exclusion_reason"] = ";".join(reasons)
        item["eligibility_reason"] = f"V34 review with score {score}"
    else:
        item["eligible"] = False
        item["quote_ready"] = False
        item["pipeline_status"] = "v34_structured_rejected"
        item["submission_status"] = "skipped"
        item["exclusion_reason"] = ";".join(reasons)
        item["eligibility_reason"] = f"V34 rejected with score {score}"


def extract_structured_portal(portal: Dict[str, Any]) -> Dict[str, Any]:
    url = _clean(portal.get("url"))
    try:
        html = _fetch(url)
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "portal": portal,
            "url": url,
            "message": str(exc),
            "items": [],
        }

    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    # 1. Structured table rows.
    for row in soup.select("table tr")[:MAX_ROWS]:
        item = _item_from_row(row, portal, url)
        if item:
            items.append(item)

    # 2. Common cards/list containers.
    card_selectors = [
        ".card", ".panel", ".views-row", ".tender", ".tender-item",
        ".opportunity", ".opportunity-item", "article", "li",
        "div[class*='tender']", "div[class*='rfq']", "div[class*='bid']",
    ]
    seen_nodes = set()
    for selector in card_selectors:
        for node in soup.select(selector)[:MAX_CARDS]:
            ident = id(node)
            if ident in seen_nodes:
                continue
            seen_nodes.add(ident)
            item = _item_from_card(node, portal, url)
            if item:
                items.append(item)

    # Dedupe.
    deduped = []
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

    accepted = [x for x in deduped if x.get("v34_structured_extraction", {}).get("decision") == "accept"]
    review = [x for x in deduped if x.get("v34_structured_extraction", {}).get("decision") == "review"]
    rejected = [x for x in deduped if x.get("v34_structured_extraction", {}).get("decision") == "reject"]

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal": portal,
        "url": url,
        "candidate_total": len(deduped),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len(rejected),
        "items": deduped,
        "accepted_items": accepted,
        "review_items": review,
        "rejected_items": rejected,
    }


def run_v34_structured_extraction(
    max_portals: int = 3,
    enable_auto_quote: bool = True,
    persist_to_live_store: bool = True,
    include_review_in_pipeline: bool = False,
) -> Dict[str, Any]:
    portals = PORTALS[:max(1, int(max_portals or 3))]
    portal_results = []
    all_items = []
    accepted = []
    review = []

    for portal in portals:
        result = extract_structured_portal(portal)
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
                source="v34-structured-rfq-extractor",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{
                "status": "error",
                "stage": "v34_pipeline_batch",
                "message": str(exc),
            }]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal_count": len(portals),
        "candidate_total": len(all_items),
        "accepted_total": len(accepted),
        "review_total": len(review),
        "rejected_total": len([x for x in all_items if x.get("v34_structured_extraction", {}).get("decision") == "reject"]),
        "pipeline_candidate_total": len(pipeline_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "portal_results": portal_results,
        "items": all_items,
        "accepted_items": accepted,
        "review_items": review,
    }
    result["log_path"] = _write_log("v34_structured_extraction", result)
    return result
