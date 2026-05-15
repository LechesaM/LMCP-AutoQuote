from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import hashlib
import json
import re

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


ENGINE_VERSION = "RFQ_DOCUMENT_INTELLIGENCE_V1"

RUNTIME_DIR = Path("runtime/rfq_document_intelligence")
DOWNLOAD_DIR = RUNTIME_DIR / "downloads"
REPORT_DIR = RUNTIME_DIR / "reports"

DEFAULT_TIMEOUT_SECONDS = 30
MAX_TEXT_PAGES = 40
MAX_TEXT_CHARS = 250_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _slug(value: Any, limit: int = 100) -> str:
    text = _safe_str(value)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (text[:limit].strip("-") or "rfq-document")


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        cleaned = _safe_str(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def extract_document_links(item: Dict[str, Any]) -> List[str]:
    """
    Extract candidate document/source URLs from an RFQ item.

    This function intentionally does not crawl deeply. It only uses URLs already
    present on the RFQ object so the engine remains safe and predictable.
    """
    if not isinstance(item, dict):
        return []

    keys = (
        "document_url",
        "source_url",
        "detail_url",
        "pdf_url",
        "download_url",
        "attachment_url",
        "tender_document_url",
    )

    links: List[str] = []

    for key in keys:
        value = item.get(key)
        if isinstance(value, list):
            links.extend(_safe_str(v) for v in value)
        else:
            links.append(_safe_str(value))

    for key in ("documents", "attachments", "supporting_documents", "links"):
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for inner_key in ("url", "href", "download_url", "document_url"):
                        links.append(_safe_str(entry.get(inner_key)))
                else:
                    links.append(_safe_str(entry))
        elif isinstance(value, dict):
            for inner_key in ("url", "href", "download_url", "document_url"):
                links.append(_safe_str(value.get(inner_key)))

    return [u for u in _unique_preserve_order(links) if _is_http_url(u)]


def _guess_extension(url: str, content_type: str = "") -> str:
    lowered_url = _safe_lower(url)
    lowered_type = _safe_lower(content_type)

    if ".pdf" in lowered_url or "application/pdf" in lowered_type or "pdf" in lowered_type:
        return ".pdf"
    if ".xlsx" in lowered_url or "spreadsheet" in lowered_type or "excel" in lowered_type:
        return ".xlsx"
    if ".xls" in lowered_url:
        return ".xls"
    if ".docx" in lowered_url or "wordprocessingml" in lowered_type:
        return ".docx"
    if ".doc" in lowered_url:
        return ".doc"
    if ".csv" in lowered_url or "text/csv" in lowered_type:
        return ".csv"
    if ".txt" in lowered_url or "text/plain" in lowered_type:
        return ".txt"
    return ".html"


def download_rfq_document(url: str, title: str = "", timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Download a single RFQ document or source page.

    Returns a structured result. It never raises for network failures.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    url = _safe_str(url)
    if not _is_http_url(url):
        return {
            "status": "failed",
            "url": url,
            "error": "invalid_url",
        }

    if requests is None:
        return {
            "status": "failed",
            "url": url,
            "error": "requests_not_available",
        }

    headers = {
        "User-Agent": "LMCP-AutoQuote RFQ Document Intelligence/1.0",
        "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(url, timeout=timeout_seconds, headers=headers, allow_redirects=True)
        content_type = response.headers.get("content-type", "")
        status_code = int(response.status_code)

        if status_code >= 400:
            return {
                "status": "failed",
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "error": "http_error",
            }

        ext = _guess_extension(str(response.url or url), content_type)
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:14]
        filename = f"{_slug(title or url)}__{digest}{ext}"
        path = DOWNLOAD_DIR / filename
        path.write_bytes(response.content)

        return {
            "status": "downloaded",
            "url": url,
            "final_url": str(response.url),
            "path": str(path),
            "filename": filename,
            "extension": ext,
            "content_type": content_type,
            "status_code": status_code,
            "size_bytes": len(response.content),
        }

    except Exception as exc:
        return {
            "status": "failed",
            "url": url,
            "error": str(exc),
        }


def _extract_pdf_text(path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except Exception:
        return ""

    try:
        doc = fitz.open(str(path))
        chunks: List[str] = []
        page_limit = min(len(doc), MAX_TEXT_PAGES)
        for index in range(page_limit):
            page = doc[index]
            chunks.append(page.get_text("text") or "")
        return "\n".join(chunks)[:MAX_TEXT_CHARS]
    except Exception:
        return ""


def _extract_html_text(path: Path) -> str:
    try:
        raw = path.read_text(errors="ignore")
    except Exception:
        return ""

    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"&nbsp;?", " ", raw, flags=re.I)
    raw = re.sub(r"&amp;?", "&", raw, flags=re.I)
    raw = re.sub(r"&lt;?", "<", raw, flags=re.I)
    raw = re.sub(r"&gt;?", ">", raw, flags=re.I)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:MAX_TEXT_CHARS]


def _extract_plain_text(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")[:MAX_TEXT_CHARS]
    except Exception:
        return ""


def extract_text_from_download(download: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract text from a downloaded file where possible.
    """
    if not isinstance(download, dict) or download.get("status") != "downloaded":
        return {
            "status": "skipped",
            "reason": "not_downloaded",
            "text": "",
            "text_length": 0,
        }

    path = Path(_safe_str(download.get("path")))
    if not path.exists():
        return {
            "status": "failed",
            "reason": "file_missing",
            "path": str(path),
            "text": "",
            "text_length": 0,
        }

    ext = _safe_lower(path.suffix)
    if ext == ".pdf":
        text = _extract_pdf_text(path)
        method = "pdf_pymupdf"
    elif ext in {".html", ".htm"}:
        text = _extract_html_text(path)
        method = "html_strip"
    elif ext in {".txt", ".csv"}:
        text = _extract_plain_text(path)
        method = "plain_text"
    else:
        text = ""
        method = "unsupported"

    return {
        "status": "ok" if text else "empty",
        "path": str(path),
        "extension": ext,
        "method": method,
        "text": text,
        "text_length": len(text),
    }


def _find_reference_numbers(text: str) -> List[str]:
    patterns = [
        r"\bRFQ\s*(?:NO|NUMBER|REF|REFERENCE)?\s*[:/#-]?\s*([A-Z0-9][A-Z0-9/&_. -]{3,60})",
        r"\bRFP\s*(?:NO|NUMBER|REF|REFERENCE)?\s*[:/#-]?\s*([A-Z0-9][A-Z0-9/&_. -]{3,60})",
        r"\bBID\s*(?:NO|NUMBER|REF|REFERENCE)?\s*[:/#-]?\s*([A-Z0-9][A-Z0-9/&_. -]{3,60})",
        r"\bTENDER\s*(?:NO|NUMBER|REF|REFERENCE)?\s*[:/#-]?\s*([A-Z0-9][A-Z0-9/&_. -]{3,60})",
        r"\bREF(?:ERENCE)?\s*(?:NO|NUMBER)?\s*[:/#-]?\s*([A-Z0-9][A-Z0-9/&_. -]{3,60})",
    ]

    found: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            value = re.sub(r"\s+", " ", match.group(1)).strip(" -:;,.")
            if value and len(value) >= 3:
                found.append(value[:80])

    return _unique_preserve_order(found)[:20]


def _find_dates(text: str) -> List[str]:
    patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b",
        r"\b20\d{2}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b",
    ]
    found: List[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.I))
    return _unique_preserve_order(found)[:30]


def _find_quantity_mentions(text: str) -> List[Dict[str, str]]:
    pattern = r"\b(\d+(?:[,.]\d+)?)\s*(each|ea|unit|units|box|boxes|pack|packs|litre|litres|liter|liters|ml|kg|g|ton|tons|metre|metres|meter|meters|m|mm|cm|pairs|sets|rolls|reams)\b"
    matches = re.findall(pattern, text, flags=re.I)
    out = []
    for quantity, unit in matches[:50]:
        out.append({
            "quantity": quantity,
            "unit": unit,
        })
    return out




def _normalise_for_match(value: Any) -> str:
    text = _safe_lower(value)
    text = re.sub(r"&amp;?", "&", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _best_title_candidates(item: Dict[str, Any]) -> List[str]:
    if not isinstance(item, dict):
        return []

    raw_candidates = [
        item.get("title"),
        item.get("buyer_rfq_number"),
        item.get("rfq_number"),
        item.get("reference_number"),
        item.get("description"),
    ]

    candidates: List[str] = []
    for value in raw_candidates:
        text = _safe_str(value)
        if not text:
            continue
        candidates.append(text)
        # Use a shorter prefix too because website text may truncate long titles.
        words = text.split()
        if len(words) >= 6:
            candidates.append(" ".join(words[:12]))
            candidates.append(" ".join(words[:8]))

    cleaned = []
    for candidate in candidates:
        norm = _normalise_for_match(candidate)
        if len(norm) >= 15:
            cleaned.append(candidate)

    return _unique_preserve_order(cleaned)


def _find_best_match_index(full_text: str, item: Dict[str, Any]) -> int:
    if not full_text:
        return -1

    full_norm = _normalise_for_match(full_text)
    if not full_norm:
        return -1

    # Build a rough mapping from normalised index to original index.
    # This is approximate but good enough for a nearby window.
    original_lower = _safe_lower(full_text)

    for candidate in _best_title_candidates(item):
        norm_candidate = _normalise_for_match(candidate)
        if not norm_candidate:
            continue

        idx_norm = full_norm.find(norm_candidate)
        if idx_norm >= 0:
            # Try exact lowercase first for better original positioning.
            exact = _safe_lower(candidate)
            exact_idx = original_lower.find(exact)
            if exact_idx >= 0:
                return exact_idx

            # Approximate original index by ratio.
            ratio = idx_norm / max(len(full_norm), 1)
            return int(ratio * len(full_text))

        # Fuzzy fallback: require at least first 5 meaningful words in sequence.
        words = [w for w in norm_candidate.split() if len(w) > 2]
        if len(words) >= 5:
            phrase = " ".join(words[:5])
            idx_norm = full_norm.find(phrase)
            if idx_norm >= 0:
                ratio = idx_norm / max(len(full_norm), 1)
                return int(ratio * len(full_text))

    return -1


def isolate_rfq_text_block(full_text: str, item: Dict[str, Any], before_chars: int = 1500, after_chars: int = 4500) -> Dict[str, Any]:
    """
    Isolate the text block most likely belonging to the current RFQ.

    Many procurement pages are listing pages containing multiple tenders. Analysing
    the whole page can cause false detections, especially compulsory briefing
    notices from unrelated tenders. This function narrows analysis to a local
    window around the current title/RFQ number when possible.
    """
    full_text = _safe_str(full_text)
    if not full_text:
        return {
            "status": "empty",
            "used_isolated_block": False,
            "match_index": -1,
            "text": "",
            "text_length": 0,
            "reason": "empty_text",
        }

    idx = _find_best_match_index(full_text, item)
    if idx < 0:
        return {
            "status": "fallback_full_text",
            "used_isolated_block": False,
            "match_index": -1,
            "text": full_text[:MAX_TEXT_CHARS],
            "text_length": min(len(full_text), MAX_TEXT_CHARS),
            "reason": "title_not_found",
        }

    start = max(0, idx - before_chars)
    end = min(len(full_text), idx + after_chars)
    block = full_text[start:end].strip()

    # Try to trim at obvious next tender boundaries after the match.
    local_match_pos = max(0, idx - start)
    after = block[local_match_pos:]
    boundary_patterns = [
        r"\bBID DESCRIPTION\s*:",
        r"\bTENDER ADVERT\s*:",
        r"\bRETENDER\s*:",
        r"\bRFQ\s+NO\s*:",
        r"\bRFP\s+\d+/",
        r"\bBid Number\s*:",
    ]

    possible_cuts = []
    for pattern in boundary_patterns:
        for m in re.finditer(pattern, after, flags=re.I):
            if m.start() > 250:
                possible_cuts.append(m.start())

    if possible_cuts:
        cut = min(possible_cuts)
        after = after[:cut]

    before = block[:local_match_pos]
    # Keep some leading context, but not too much.
    before = before[-700:]
    block = (before + " " + after).strip()

    return {
        "status": "ok",
        "used_isolated_block": True,
        "match_index": idx,
        "text": block[:MAX_TEXT_CHARS],
        "text_length": len(block[:MAX_TEXT_CHARS]),
        "reason": "matched_title_or_reference",
    }



def analyse_document_text(text: str) -> Dict[str, Any]:
    text = _safe_str(text)
    t = text.lower()

    briefing_terms = [
        "compulsory briefing",
        "mandatory briefing",
        "compulsory site meeting",
        "mandatory site meeting",
        "compulsory clarification meeting",
        "mandatory clarification meeting",
        "non-compulsory briefing",
        "non compulsory briefing",
        "information session",
    ]

    compulsory_briefing_terms = [
        "compulsory briefing",
        "mandatory briefing",
        "compulsory site meeting",
        "mandatory site meeting",
        "compulsory clarification meeting",
        "mandatory clarification meeting",
    ]

    pricing_terms = [
        "pricing schedule",
        "price schedule",
        "schedule of prices",
        "bill of quantities",
        "boq",
        "form of offer",
        "quotation schedule",
        "rate schedule",
    ]

    sbd_matches = sorted(set(re.findall(r"\bSBD\s*([0-9](?:\.[0-9])?)\b", text, flags=re.I)))

    return {
        "text_length": len(text),
        "has_text": bool(text.strip()),
        "reference_numbers": _find_reference_numbers(text),
        "date_mentions": _find_dates(text),
        "briefing_or_site_meeting_mentioned": any(term in t for term in briefing_terms),
        "compulsory_briefing_required": any(term in t for term in compulsory_briefing_terms),
        "has_pricing_schedule": any(term in t for term in pricing_terms),
        "has_boq": "boq" in t or "bill of quantities" in t,
        "has_sbd_forms": bool(sbd_matches),
        "sbd_forms_detected": [f"SBD {x}" for x in sbd_matches],
        "quantity_mentions": _find_quantity_mentions(text),
        "returnables_mentioned": any(term in t for term in [
            "returnable documents",
            "returnable schedules",
            "mandatory returnables",
            "compulsory returnables",
        ]),
        "tax_compliance_mentioned": "tax compliance" in t or "pin" in t and "tax" in t,
        "csd_mentioned": "central supplier database" in t or "csd" in t,
        "bbbee_mentioned": "b-bbee" in t or "bbbee" in t or "bbee" in t,
        "delivery_mentioned": "delivery" in t or "deliver" in t,
        "supply_mentioned": "supply" in t,
    }


def analyse_rfq_documents(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Main entry point for RFQ Document Intelligence.

    Downloads URLs already present in the RFQ item, extracts readable text,
    detects pricing/BOQ/SBD/briefing/quantity signals, and writes a JSON report.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not isinstance(item, dict):
        item = {}

    title = _safe_str(
        item.get("title")
        or item.get("buyer_rfq_number")
        or item.get("rfq_number")
        or "rfq"
    )

    links = extract_document_links(item)
    downloads = [download_rfq_document(url, title, timeout_seconds=timeout_seconds) for url in links]

    extracted_text_results: List[Dict[str, Any]] = []
    combined_text_parts: List[str] = []

    for download in downloads:
        text_result = extract_text_from_download(download)
        text = _safe_str(text_result.get("text"))
        clean_text_result = dict(text_result)
        clean_text_result.pop("text", None)
        extracted_text_results.append(clean_text_result)
        if text:
            combined_text_parts.append(text)

    fallback_text = " ".join([
        _safe_str(item.get("title")),
        _safe_str(item.get("description")),
        _safe_str(item.get("raw_text")),
        _safe_str(item.get("buyer_rfq_number")),
    ]).strip()

    combined_text = "\n\n".join(combined_text_parts).strip()
    if not combined_text and fallback_text:
        combined_text = fallback_text

    isolation = isolate_rfq_text_block(combined_text, item)
    analysis_text = _safe_str(isolation.get("text")) or combined_text

    intelligence = analyse_document_text(analysis_text)
    intelligence["rfq_block_isolation"] = {
        "status": isolation.get("status"),
        "used_isolated_block": isolation.get("used_isolated_block"),
        "match_index": isolation.get("match_index"),
        "text_length": isolation.get("text_length"),
        "reason": isolation.get("reason"),
    }

    quote_safe = not intelligence.get("compulsory_briefing_required", False)

    result: Dict[str, Any] = {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "analysed_at": _now_iso(),
        "title": title,
        "buyer_name": _safe_str(item.get("buyer_name")),
        "buyer_rfq_number": _safe_str(item.get("buyer_rfq_number")),
        "links": links,
        "downloads": downloads,
        "text_extraction": extracted_text_results,
        "document_intelligence": intelligence,
        "quote_safe": quote_safe,
        "quote_block_reason": "" if quote_safe else "compulsory_briefing_or_site_meeting_detected",
    }

    report_name = f"{_slug(title)}__document_intelligence.json"
    report_path = REPORT_DIR / report_name
    report_path.write_text(json.dumps(result, indent=2, default=str))
    result["report_path"] = str(report_path)

    return result


def analyse_rfq_document_intelligence(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Alias kept for future API naming compatibility.
    """
    return analyse_rfq_documents(item, timeout_seconds=timeout_seconds)


def get_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "runtime_dir": str(RUNTIME_DIR),
        "download_dir": str(DOWNLOAD_DIR),
        "report_dir": str(REPORT_DIR),
        "capabilities": [
            "download_document_source_detail_urls",
            "extract_pdf_text_with_pymupdf_when_available",
            "extract_html_text",
            "detect_compulsory_briefing_or_site_meeting",
            "detect_pricing_schedule_or_boq",
            "detect_sbd_forms",
            "detect_quantity_mentions",
            "write_json_report",
        ],
    }
