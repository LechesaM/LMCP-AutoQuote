"""
LMCP V50.8.3 - eTenders Structured JSON Row Parser

Purpose:
- Parse the actual JSON row objects returned by:
    /Home/PaginatedTenderOpportunities
- Stop relying mainly on noisy page/script text chunks.
- Extract useful row fields:
    id, tenderNumber, description, category, buyer/org, province,
    document file names, document GUIDs, action HTML, onclick handlers.
- Reconstruct safe detail/document candidates from structured row fields.
- Probe candidates and only promote downloadable documents when verified.

Drop-in:
    app/services/etenders_structured_json_parser_v50_8_3_service.py
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import requests


SERVICE_VERSION = "V50.8.3_ETENDERS_STRUCTURED_JSON_ROW_PARSER"

ETENDERS_BASE = "https://www.etenders.gov.za"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"
PAGINATED_ENDPOINT = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

GOOD_CONTENT_HINTS = (
    "application/pdf",
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats",
    "application/vnd.ms-excel",
    "octet-stream",
)

BAD_CONTENT_HINTS = (
    "text/html",
    "application/json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _tokenise(text: str) -> List[str]:
    text = _safe_lower(text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {
        "the", "and", "for", "with", "including", "copies", "copy",
        "supply", "delivery", "deliver", "of", "a", "an", "to",
        "in", "on", "at", "rfq", "rfp", "bid", "tender", "days",
        "day", "service", "services", "printed", "request", "quotation",
    }
    return [t for t in text.split() if len(t) >= 4 and t not in stop]


def _match_score(target_title: str, row_text: str) -> Dict[str, Any]:
    tokens = _tokenise(target_title)
    row_low = _safe_lower(row_text)
    hits = [t for t in tokens if t in row_low]
    score = len(hits) / max(len(tokens), 1) if tokens else 0.0

    phrase = _safe_lower(target_title)
    phrase = re.sub(r"\s+in\s+\d+\s+days?$", "", phrase).strip()
    if phrase and len(phrase) >= 35 and phrase[:55] in row_low:
        score += 0.25

    # Date formats can be inverted in eTenders JSON, so make date matching optional.
    dates = re.findall(r"\b\d{2}/\d{2}/20\d{2}\b", target_title)
    date_hits = [d for d in dates if d in row_text]
    if dates and date_hits:
        score += 0.15

    return {
        "score": round(min(score, 1.0), 4),
        "hits": hits,
        "target_token_count": len(tokens),
        "date_hits": date_hits,
    }


def _flatten_rows(value: Any) -> List[Any]:
    rows: List[Any] = []
    if isinstance(value, dict):
        for key in ("data", "aaData", "results", "items", "rows", "records"):
            if isinstance(value.get(key), list):
                rows.extend(value[key])
        for sub in value.values():
            if isinstance(sub, (dict, list)):
                rows.extend(_flatten_rows(sub))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                rows.append(item)
            if isinstance(item, (dict, list)):
                rows.extend(_flatten_rows(item))
    return rows


def _row_blob(row: Any) -> str:
    try:
        return json.dumps(row, ensure_ascii=False)
    except Exception:
        return str(row or "")


def _row_text(row: Dict[str, Any]) -> str:
    priority_keys = [
        "tenderNumber",
        "tender_No",
        "tenderNo",
        "tender_No_",
        "description",
        "tenderDescription",
        "category",
        "organOfState",
        "department",
        "buyer",
        "buyerName",
        "province",
        "actions",
        "documents",
        "documentName",
        "fileName",
        "file",
    ]
    parts: List[str] = []
    for key in priority_keys:
        if key in row:
            parts.append(_clean(row.get(key)))

    # Add everything else after priority fields.
    for key, value in row.items():
        if key not in priority_keys:
            if isinstance(value, (dict, list)):
                parts.append(_row_blob(value))
            else:
                parts.append(_clean(value))
    return _clean(" ".join(parts))


def _extract_guids(blob: str) -> List[str]:
    pattern = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    out: List[str] = []
    for guid in re.findall(pattern, blob):
        guid = guid.lower()
        if guid not in out:
            out.append(guid)
    return out


def _extract_ids_from_row(row: Dict[str, Any], blob: str) -> List[str]:
    out: List[str] = []

    preferred_keys = [
        "id",
        "ID",
        "tenderId",
        "tender_ID",
        "tenderID",
        "tenderIdNo",
        "tender_No",
        "tenderNoId",
        "documentId",
        "docId",
        "fileId",
        "tenderNumberId",
    ]

    for key in preferred_keys:
        value = row.get(key)
        if value is None:
            continue
        for match in re.findall(r"\b\d{3,10}\b", str(value)):
            if match not in out:
                out.append(match)

    for match in re.findall(r"\b(?:id|tenderid|documentid|docid|fileid)\s*[=:]\s*['\"]?(\d{3,10})", blob, flags=re.I):
        if match not in out:
            out.append(match)

    # Known eTenders tender ids in DataTables output are often 5-6 digits.
    for match in re.findall(r"\b(\d{5,8})\b", blob):
        if match not in out:
            out.append(match)

    return out


def _extract_filenames(blob: str) -> List[str]:
    out: List[str] = []
    for match in re.findall(r"([A-Za-z0-9 _+\-–—(),.&/]+?\.(?:pdf|docx?|xlsx?|xls|zip))", blob, flags=re.I):
        name = _clean(match).strip(" ,;:'\"")
        if len(name) >= 8 and name not in out:
            out.append(name)
    return out


def _extract_href_links(blob: str) -> List[str]:
    out: List[str] = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', blob, flags=re.I):
        url = urljoin(ETENDERS_BASE, html.unescape(href))
        if url not in out:
            out.append(url)
    for url in re.findall(r"https?://[^\s\"'<>]+", blob):
        if url not in out:
            out.append(url)
    return out


def _extract_js_routes(blob: str, ids: List[str], guids: List[str]) -> List[str]:
    out: List[str] = []

    # Routes discovered in site.js and eTenders conventions.
    for tender_id in ids:
        for path in [
            f"/home/tenderdetails?id={tender_id}",
            f"/Home/TenderDetails?id={tender_id}",
            f"/Home/DownloadSpec?documentId={tender_id}&source=sharepoint",
            f"/Home/DownloadTenderDocument?documentId={tender_id}&source=sharepoint",
            f"/Home/DownloadFile?documentId={tender_id}&source=sharepoint",
            f"/Home/DownloadDocument?documentId={tender_id}&source=sharepoint",
            f"/Esubmission/esubmission?id={tender_id}",
        ]:
            out.append(urljoin(ETENDERS_BASE, path))

    for guid in guids:
        for path in [
            f"/Home/DownloadSpec?documentGuid={guid}&source=sharepoint",
            f"/Home/DownloadTenderDocument?documentGuid={guid}&source=sharepoint",
            f"/Home/DownloadFile?documentGuid={guid}&source=sharepoint",
            f"/Home/DownloadDocument?documentGuid={guid}&source=sharepoint",
            f"/Home/DownloadSpec?documentId={guid}&source=sharepoint",
        ]:
            out.append(urljoin(ETENDERS_BASE, path))

    for fn in _extract_filenames(blob):
        for tender_id in ids[:3]:
            for endpoint in [
                "/Home/DownloadSpec",
                "/Home/DownloadTenderDocument",
                "/Home/DownloadFile",
                "/Home/DownloadDocument",
            ]:
                out.append(
                    f"{ETENDERS_BASE}{endpoint}?"
                    + urlencode({"documentId": tender_id, "fileName": fn, "source": "sharepoint"})
                )

    # Explicit route-like strings in JS.
    for route in re.findall(r"['\"](/(?:Home|home|Esubmission|esubmission)/[^'\"]+)['\"]", blob):
        out.append(urljoin(ETENDERS_BASE, route))

    # de-dupe
    clean: List[str] = []
    seen = set()
    for url in out:
        if url and url not in seen:
            seen.add(url)
            clean.append(url)
    return clean


def _fetch_datatables_json(search_value: str = "", length: int = 25) -> Dict[str, Any]:
    params = {
        "draw": "1",
        "columns[0][data]": "",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "false",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "category",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "description",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "false",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "columns[3][data]": "eSubmission",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",
        "columns[4][data]": "date_Published",
        "columns[4][name]": "",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "true",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",
        "columns[5][data]": "closing_Date",
        "columns[5][name]": "",
        "columns[5][searchable]": "true",
        "columns[5][orderable]": "true",
        "columns[5][search][value]": "",
        "columns[5][search][regex]": "false",
        "columns[6][data]": "actions",
        "columns[6][name]": "",
        "columns[6][searchable]": "true",
        "columns[6][orderable]": "true",
        "columns[6][search][value]": "",
        "columns[6][search][regex]": "false",
        "order[0][column]": "2",
        "order[0][dir]": "desc",
        "start": "0",
        "length": str(length),
        "search[value]": search_value,
        "search[regex]": "false",
        "status": "1",
        "_": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": ETENDERS_OPPORTUNITIES,
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        response = requests.get(PAGINATED_ENDPOINT, params=params, headers=headers, timeout=25)
        return {
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "url": response.url,
            "content_type": response.headers.get("content-type", ""),
            "data": response.json() if response.text else {},
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 0,
            "url": PAGINATED_ENDPOINT,
            "content_type": "",
            "data": {},
            "error": str(exc),
        }


def _probe_url(url: str, timeout: int = 10) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": "application/pdf,application/zip,application/octet-stream,*/*",
        "Referer": ETENDERS_OPPORTUNITIES,
    }

    result = {
        "url": url,
        "ok": False,
        "verified_download": False,
        "status_code": 0,
        "final_url": url,
        "content_type": "",
        "content_length": 0,
        "content_disposition": "",
        "reason": "",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
        result["status_code"] = response.status_code
        result["final_url"] = response.url
        result["content_type"] = response.headers.get("content-type", "")
        result["content_disposition"] = response.headers.get("content-disposition", "")
        try:
            result["content_length"] = int(response.headers.get("content-length") or 0)
        except Exception:
            result["content_length"] = 0

        first = b""
        try:
            first = next(response.iter_content(chunk_size=512), b"")
        except StopIteration:
            first = b""
        except Exception:
            first = b""

        ctype = _safe_lower(result["content_type"])
        cdisp = _safe_lower(result["content_disposition"])
        byte_hint = first.startswith(b"%PDF") or first.startswith(b"PK") or first.startswith(b"\xd0\xcf\x11\xe0")
        good_ctype = any(x in ctype for x in GOOD_CONTENT_HINTS)
        bad_ctype = any(x in ctype for x in BAD_CONTENT_HINTS)
        attachment = "attachment" in cdisp or "filename" in cdisp

        if 200 <= response.status_code < 400 and (byte_hint or attachment or (good_ctype and not bad_ctype)):
            result["ok"] = True
            result["verified_download"] = True
            result["reason"] = "download_verified"
        else:
            result["reason"] = f"not_verified:{result['status_code']}:{result['content_type']}"

        try:
            response.close()
        except Exception:
            pass

        return result
    except Exception as exc:
        result["reason"] = f"probe_exception:{exc}"
        return result


@dataclass
class StructuredCandidate:
    url: str
    score: float
    reasons: List[str]
    is_document_like: bool
    row_match_score: float
    ids: List[str]
    guids: List[str]
    filenames: List[str]
    probe: Dict[str, Any]


def parse_etenders_structured_json(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    title = _clean(
        payload.get("title")
        or payload.get("description")
        or payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or ""
    )

    # Use multiple search variants because eTenders search can be strict/odd.
    search_variants = []
    for variant in [
        title,
        re.sub(r"\s+in\s+\d+\s+days?$", "", title, flags=re.I).strip(),
        "DIGITAL BOOK",
        "JDA 25TH ANNIVERSARY",
        "JDAMARK/DIGITALBOOK",
    ]:
        variant = _clean(variant)
        if variant and variant not in search_variants:
            search_variants.append(variant)

    responses = []
    for search in search_variants[:5]:
        responses.append(_fetch_datatables_json(search_value=search, length=50))

    # Add empty search fallback to inspect current first page.
    responses.append(_fetch_datatables_json(search_value="", length=25))

    all_rows: List[Dict[str, Any]] = []
    for resp in responses:
        rows = _flatten_rows(resp.get("data"))
        for row in rows:
            if isinstance(row, dict):
                all_rows.append(row)

    matched_rows: List[Dict[str, Any]] = []
    candidate_urls: List[Dict[str, Any]] = []

    seen_row_blobs = set()
    for idx, row in enumerate(all_rows):
        blob = _row_blob(row)
        if blob in seen_row_blobs:
            continue
        seen_row_blobs.add(blob)

        text = _row_text(row)
        match = _match_score(title, text)
        score = float(match.get("score") or 0.0)

        # Also accept strong tender number marker from row.
        if "jdamark/digitalbook" in _safe_lower(text):
            score = max(score, 0.95)

        if score < 0.35:
            continue

        ids = _extract_ids_from_row(row, blob)
        guids = _extract_guids(blob)
        filenames = _extract_filenames(blob)
        hrefs = _extract_href_links(blob)
        routes = _extract_js_routes(blob, ids, guids)

        urls = []
        for u in hrefs + routes:
            if u not in urls:
                urls.append(u)

        row_record = {
            "index": idx,
            "match_score": round(score, 4),
            "match_hits": match.get("hits") or [],
            "date_hits": match.get("date_hits") or [],
            "ids": ids,
            "guids": guids,
            "filenames": filenames,
            "url_count": len(urls),
            "text_preview": text[:900],
            "raw_keys": sorted(list(row.keys())),
        }

        matched_rows.append(row_record)

        for url in urls:
            low = _safe_lower(url)
            is_doc = any(x in low for x in ["download", "documentid", "documentguid", ".pdf", ".doc", ".xls", ".zip"])
            candidate_urls.append({
                "url": url,
                "row_match_score": score,
                "ids": ids,
                "guids": guids,
                "filenames": filenames,
                "is_document_like": is_doc,
            })

    # Dedupe candidates.
    dedup: Dict[str, Dict[str, Any]] = {}
    for c in candidate_urls:
        url = c["url"]
        if url not in dedup or c["row_match_score"] > dedup[url]["row_match_score"]:
            dedup[url] = c

    candidates = sorted(
        dedup.values(),
        key=lambda c: (
            0 if c.get("is_document_like") else 1,
            -float(c.get("row_match_score") or 0),
            c.get("url", ""),
        ),
    )

    structured_candidates: List[StructuredCandidate] = []
    probed_count = 0

    for c in candidates[:30]:
        url = c["url"]
        score = float(c.get("row_match_score") or 0.0)
        reasons = ["structured_json_row_match"]

        if c.get("is_document_like"):
            score += 0.2
            reasons.append("document_like_url")

        if c.get("guids"):
            score += 0.1
            reasons.append("guid_present")

        if c.get("filenames"):
            score += 0.1
            reasons.append("filename_present")

        probe = {}
        if c.get("is_document_like"):
            probe = _probe_url(url)
            probed_count += 1
            if probe.get("verified_download"):
                score += 0.25
                reasons.append("probe_verified_download")
            else:
                reasons.append("probe_not_verified")
        else:
            probe = {
                "url": url,
                "verified_download": False,
                "reason": "not_document_like_not_probed",
            }

        structured_candidates.append(StructuredCandidate(
            url=url,
            score=round(min(score, 1.0), 4),
            reasons=reasons,
            is_document_like=bool(c.get("is_document_like")),
            row_match_score=float(c.get("row_match_score") or 0.0),
            ids=list(c.get("ids") or []),
            guids=list(c.get("guids") or []),
            filenames=list(c.get("filenames") or []),
            probe=probe,
        ))

    verified_docs = [
        c for c in structured_candidates
        if c.is_document_like and c.probe.get("verified_download")
    ]

    verified_details = [
        c for c in structured_candidates
        if not c.is_document_like
        and c.score >= 0.55
        and "tenderdetails" in _safe_lower(c.url)
    ]

    if verified_docs:
        action = "promote_verified_structured_document"
    elif verified_details:
        action = "promote_verified_structured_detail"
    elif structured_candidates:
        action = "structured_candidates_found_but_not_verified"
    elif matched_rows:
        action = "matched_structured_rows_but_no_urls"
    else:
        action = "no_matching_structured_rows"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "parsed_at": _now(),
        "title": title,
        "search_variants": search_variants,
        "response_count": len(responses),
        "response_summaries": [
            {
                "ok": r.get("ok"),
                "status_code": r.get("status_code"),
                "url": r.get("url"),
                "content_type": r.get("content_type"),
                "error": r.get("error"),
            }
            for r in responses
        ],
        "row_count": len(all_rows),
        "matched_row_count": len(matched_rows),
        "candidate_url_count": len(candidates),
        "probed_candidate_count": probed_count,
        "verified_document_count": len(verified_docs),
        "verified_detail_count": len(verified_details),
        "recommended_action": action,
        "safe_to_download": bool(verified_docs),
        "safe_to_follow_detail": bool(verified_details),
        "recommended_document_links": [asdict(c) for c in verified_docs[:10]],
        "recommended_detail_links": [asdict(c) for c in verified_details[:10]],
        "structured_candidates": [asdict(c) for c in structured_candidates[:30]],
        "matched_rows": matched_rows[:20],
        "notes": [
            "V50.8.3 parses the structured PaginatedTenderOpportunities JSON directly.",
            "It promotes documents only after download probe verification.",
            "If matched rows have IDs/GUIDs but no verified URL, inspect structured_candidates and matched_rows.",
        ],
    }


def get_v50_8_3_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "capabilities": [
            "direct_paginated_tender_opportunities_fetch",
            "structured_json_row_parsing",
            "action_html_route_extraction",
            "tender_id_guid_filename_extraction",
            "structured_candidate_url_generation",
            "safe_download_probe_verification",
        ],
    }
