from __future__ import annotations

"""
LMCP V33 Real Portal RFQ Extraction Engine

Drop-in:
    app/services/real_portal_rfq_extraction_v33_service.py

Purpose:
    Extract real RFQ/tender rows from portal pages instead of page headers like:
      - "Tenders"
      - "ADVERTISED TENDERS"
      - "Request for Bid (Open-Tender)"

Important:
    This is a safe add-on. It does not replace the old harvester.
    It focuses on HTML table/anchor extraction and PDF/XLS/DOC link discovery.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.core.runtime_paths import PROJECT_ROOT, ensure_directories

SERVICE_VERSION = "V33_REAL_PORTAL_RFQ_EXTRACTION_ENGINE"

DEFAULT_TIMEOUT = int(str(os.getenv("V33_PORTAL_TIMEOUT", "30")).strip() or "30")
MAX_LINKS_PER_PORTAL = int(str(os.getenv("V33_MAX_LINKS_PER_PORTAL", "80")).strip() or "80")
MAX_ROWS_PER_PORTAL = int(str(os.getenv("V33_MAX_ROWS_PER_PORTAL", "80")).strip() or "80")

LOG_DIR = PROJECT_ROOT / "runtime" / "v33_real_portal_extraction" / "logs"


def ensure_v33_runtime_dirs() -> None:
    ensure_directories([LOG_DIR])

DEFAULT_PORTALS = [
    {
        "name": "National Treasury eTenders",
        "url": "https://www.etenders.gov.za/Home/opportunities",
        "source": "v33-etenders",
    },
    {
        "name": "Eskom Tenders",
        "url": "https://www.eskom.co.za/tenderbulletin/",
        "source": "v33-eskom",
    },
    {
        "name": "Transnet Tenders",
        "url": "https://transnetetenders.azurewebsites.net/",
        "source": "v33-transnet",
    },
    {
        "name": "SANRAL Tenders",
        "url": "https://www.nra.co.za/service-provider-zone/tenders/",
        "source": "v33-sanral",
    },
]

NOISE_TITLES = {
    "tenders",
    "tender",
    "advertised tenders",
    "request for bid",
    "request for bid (open-tender)",
    "open tender",
    "opportunities",
    "download",
    "downloads",
    "click here",
    "home",
    "login",
    "register",
    "rfq",
}

EXCLUDED_KEYWORDS = [
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

SUPPLY_KEYWORDS = [
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
]

RFQ_KEYWORDS = [
    "rfq",
    "request for quotation",
    "quotation",
    "quote",
    "bid",
    "tender",
    "closing date",
    "closing time",
    "submission",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    text = str(value or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _write_log(prefix: str, payload: Dict[str, Any]) -> str:
    try:
        ensure_v33_runtime_dirs()
        path = LOG_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _is_noise(title: Any) -> bool:
    t = _lower(title)
    if not t:
        return True
    if t in NOISE_TITLES:
        return True
    if len(t) < 15:
        return True
    if "@" in t and len(t.split()) <= 2:
        return True
    return False


def _contains_any(text: str, words: List[str]) -> bool:
    return any(word in text for word in words)


def _extract_date(text: str) -> str:
    text = _clean(text)
    patterns = [
        r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]20\d{2}\b",
        r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _looks_like_document_url(url: str) -> bool:
    u = _lower(url)
    return any(ext in u for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"])


def _score_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join([
        _clean(item.get("title")),
        _clean(item.get("description")),
        _clean(item.get("raw_text")),
        _clean(item.get("document_url")),
        _clean(item.get("detail_url")),
    ]).lower()

    score = 0
    reasons = []

    if _is_noise(item.get("title")):
        score -= 45
        reasons.append("noise_title")

    excluded = [w for w in EXCLUDED_KEYWORDS if w in text]
    if excluded:
        score -= 80
        reasons.append("excluded:" + ",".join(excluded[:5]))

    supply_hits = [w for w in SUPPLY_KEYWORDS if w in text]
    rfq_hits = [w for w in RFQ_KEYWORDS if w in text]

    if supply_hits:
        score += min(45, len(supply_hits) * 15)
    else:
        reasons.append("no_supply_signal")

    if rfq_hits:
        score += min(30, len(rfq_hits) * 8)
    else:
        reasons.append("no_rfq_signal")

    if _clean(item.get("closing_date")):
        score += 15
    else:
        reasons.append("no_closing_date")

    if _clean(item.get("document_url")) and _looks_like_document_url(_clean(item.get("document_url"))):
        score += 20
    elif _clean(item.get("document_url") or item.get("detail_url")):
        score += 8
    else:
        reasons.append("no_document_or_detail_url")

    score = max(0, min(100, int(score)))

    if excluded:
        decision = "reject"
    elif score >= 65:
        decision = "accept"
    elif score >= 45:
        decision = "review"
    else:
        decision = "reject"

    return {
        "service_version": SERVICE_VERSION,
        "decision": decision,
        "score": score,
        "reasons": reasons,
        "supply_hits": supply_hits[:10],
        "rfq_hits": rfq_hits[:10],
        "excluded_hits": excluded[:10],
        "checked_at": _now(),
    }


def _candidate_from_row(row, portal: Dict[str, Any], base_url: str) -> Dict[str, Any] | None:
    cells = [_clean(c.get_text(" ", strip=True)) for c in row.find_all(["td", "th"])]
    text = _clean(" ".join(cells))
    if not text:
        return None

    links = []
    for a in row.find_all("a", href=True):
        href = urljoin(base_url, a.get("href"))
        label = _clean(a.get_text(" ", strip=True))
        links.append({"url": href, "label": label})

    document_url = ""
    detail_url = ""
    for link in links:
        if _looks_like_document_url(link["url"]):
            document_url = link["url"]
            break

    if not document_url and links:
        detail_url = links[0]["url"]

    title = ""
    # Prefer non-header looking cell with enough text.
    for cell in cells:
        low = cell.lower()
        if len(cell) >= 15 and low not in NOISE_TITLES and "closing date" not in low:
            title = cell
            break

    if not title:
        title = links[0]["label"] if links and links[0]["label"] else text[:180]

    closing_date = _extract_date(text)

    item = {
        "title": title[:220],
        "description": text[:2500],
        "raw_text": text[:5000],
        "buyer_name": portal.get("name", ""),
        "source": portal.get("source", "v33-portal"),
        "source_name": portal.get("name", ""),
        "portal_name": portal.get("name", ""),
        "source_url": base_url,
        "document_url": document_url,
        "detail_url": detail_url,
        "closing_date": closing_date,
        "submission_method": "portal",
        "recipient_email": "",
        "buyer_email": "",
        "briefing_required": "compulsory briefing" in text.lower(),
        "harvested_at": _now(),
        "items": [],
        "line_items": [],
        "auto_quote_enabled": False,
    }
    ref = _extract_reference(text) or title[:120]
    item["buyer_rfq_number"] = ref
    item["rfq_number"] = ref
    item["reference_number"] = ref
    return item


def _extract_reference(text: str) -> str:
    patterns = [
        r"\bRFQ[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bRFP[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bBID[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\bTENDER[\s:/#-]*[A-Z0-9][A-Z0-9/_.-]{2,}\b",
        r"\b[A-Z]{1,6}/[A-Z0-9]{1,6}\s*\d{1,4}/\d{2,4}\b",
        r"\b[A-Z]{2,8}\s*\d{2,5}/\d{2,4}\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return _clean(m.group(0))
    return ""


def _candidate_from_anchor(a, portal: Dict[str, Any], base_url: str) -> Dict[str, Any] | None:
    href = urljoin(base_url, a.get("href", ""))
    label = _clean(a.get_text(" ", strip=True))
    title = label or Path(urlparse(href).path).name

    if not href.startswith("http") or _is_noise(title):
        return None

    combined = f"{title} {href}"
    if not (_looks_like_document_url(href) or _contains_any(combined.lower(), RFQ_KEYWORDS + SUPPLY_KEYWORDS)):
        return None

    ref = _extract_reference(combined) or title[:120]

    return {
        "title": title[:220],
        "description": combined[:1500],
        "raw_text": combined[:2500],
        "buyer_name": portal.get("name", ""),
        "buyer_rfq_number": ref,
        "rfq_number": ref,
        "reference_number": ref,
        "source": portal.get("source", "v33-portal"),
        "source_name": portal.get("name", ""),
        "portal_name": portal.get("name", ""),
        "source_url": base_url,
        "document_url": href if _looks_like_document_url(href) else "",
        "detail_url": "" if _looks_like_document_url(href) else href,
        "closing_date": _extract_date(combined),
        "submission_method": "portal",
        "recipient_email": "",
        "buyer_email": "",
        "briefing_required": "compulsory briefing" in combined.lower(),
        "harvested_at": _now(),
        "items": [],
        "line_items": [],
        "auto_quote_enabled": False,
    }


def fetch_portal_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.text


def extract_portal_rfqs(portal: Dict[str, Any]) -> Dict[str, Any]:
    url = _clean(portal.get("url"))
    if not url:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Missing portal URL",
            "items": [],
        }

    try:
        html = fetch_portal_html(url)
    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "url": url,
            "message": str(exc),
            "items": [],
        }

    soup = BeautifulSoup(html, "html.parser")
    candidates: List[Dict[str, Any]] = []

    for row in soup.find_all("tr")[:MAX_ROWS_PER_PORTAL]:
        candidate = _candidate_from_row(row, portal, url)
        if candidate:
            candidates.append(candidate)

    for a in soup.find_all("a", href=True)[:MAX_LINKS_PER_PORTAL]:
        candidate = _candidate_from_anchor(a, portal, url)
        if candidate:
            candidates.append(candidate)

    # Dedupe by ref/title/url.
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in candidates:
        key = (
            _lower(item.get("buyer_rfq_number")),
            _lower(item.get("title")),
            _lower(item.get("document_url") or item.get("detail_url")),
        )
        if key in seen:
            continue
        seen.add(key)

        classification = _score_candidate(item)
        item["v33_real_portal_extraction"] = classification
        if classification["decision"] == "accept":
            item["eligible"] = True
            item["quote_ready"] = True
            item["pipeline_status"] = "v33_real_portal_accepted"
            item["exclusion_reason"] = ""
        elif classification["decision"] == "review":
            item["eligible"] = False
            item["quote_ready"] = False
            item["pipeline_status"] = "v33_real_portal_review"
            item["submission_status"] = "manual_review_required"
            item["exclusion_reason"] = ";".join(classification.get("reasons", []))
        else:
            item["eligible"] = False
            item["quote_ready"] = False
            item["pipeline_status"] = "v33_real_portal_rejected"
            item["submission_status"] = "skipped"
            item["exclusion_reason"] = ";".join(classification.get("reasons", []))
        deduped.append(item)

    accepted = [x for x in deduped if x.get("v33_real_portal_extraction", {}).get("decision") == "accept"]
    review = [x for x in deduped if x.get("v33_real_portal_extraction", {}).get("decision") == "review"]
    rejected = [x for x in deduped if x.get("v33_real_portal_extraction", {}).get("decision") == "reject"]

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


def run_v33_real_portal_extraction(
    max_portals: int = 4,
    enable_auto_quote: bool = True,
    persist_to_live_store: bool = True,
    include_review_in_pipeline: bool = False,
) -> Dict[str, Any]:
    portals = DEFAULT_PORTALS[:max(1, int(max_portals or 4))]

    portal_results: List[Dict[str, Any]] = []
    all_items: List[Dict[str, Any]] = []
    accepted_items: List[Dict[str, Any]] = []
    review_items: List[Dict[str, Any]] = []

    for portal in portals:
        result = extract_portal_rfqs(portal)
        portal_results.append(result)
        all_items.extend(result.get("items", []))
        accepted_items.extend(result.get("accepted_items", []))
        review_items.extend(result.get("review_items", []))

    pipeline_items = list(accepted_items)
    if include_review_in_pipeline:
        pipeline_items.extend(review_items)

    auto_quote_results: List[Dict[str, Any]] = []
    if enable_auto_quote and pipeline_items:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_batch
            auto_quote_results = run_tender_pipeline_batch(
                pipeline_items,
                source="v33-real-portal-extraction",
                persist_to_live_store=persist_to_live_store,
            )
        except Exception as exc:
            auto_quote_results = [{
                "status": "error",
                "stage": "v33_pipeline_batch",
                "message": str(exc),
            }]

    result = {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "checked_at": _now(),
        "portal_count": len(portals),
        "candidate_total": len(all_items),
        "accepted_total": len(accepted_items),
        "review_total": len(review_items),
        "rejected_total": len([x for x in all_items if x.get("v33_real_portal_extraction", {}).get("decision") == "reject"]),
        "pipeline_candidate_total": len(pipeline_items),
        "auto_quote_enabled": enable_auto_quote,
        "auto_quote_results": auto_quote_results,
        "persist_to_live_store": persist_to_live_store,
        "portal_results": portal_results,
        "items": all_items,
        "accepted_items": accepted_items,
        "review_items": review_items,
    }
    result["log_path"] = _write_log("v33_real_portal_extraction", result)
    return result
