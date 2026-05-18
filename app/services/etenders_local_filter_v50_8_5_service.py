"""
LMCP V50.8.6 - eTenders Local Structured Filter + Row Deduplication Engine

Purpose:
- Keep the V50.8.5 local structured filtering behavior.
- Fix row overcounting caused by recursive nested objects and child rows.
- Deduplicate rows by stable tender identity:
    id, tenderId, tender_ID, tender_No, tenderNumber, ocid, releaseId.
- Deduplicate candidate document/detail URLs.
- Exclude weak numeric IDs extracted from timestamps / dates / sentinel values.
- Improve filtering stability for autonomous RFQ discovery.

Drop-in replacement:
    app/services/etenders_local_filter_v50_8_5_service.py

Optional new API/service version:
    service_version returns V50.8.6 while keeping the same route if you replace V50.8.5 file.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests


SERVICE_VERSION = "V50.8.6_ETENDERS_LOCAL_STRUCTURED_FILTER_DEDUP"

ETENDERS_BASE = "https://www.etenders.gov.za"
ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"
PAGINATED_ENDPOINT = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

DEFAULT_STATUSES = ["1", "2"]
DEFAULT_STARTS = [0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
DEFAULT_LENGTH = 50

BAD_ID_VALUES = {
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "9999999",
    "99999999",
    "999999999",
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


def _json_blob(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value or "")


def _is_tender_like_row(row: Dict[str, Any]) -> bool:
    """
    Avoid recursively treating nested awards/company/subcontractor objects as separate tenders.
    A true eTenders row should have enough top-level tender fields.
    """
    if not isinstance(row, dict):
        return False

    strong_keys = {
        "id",
        "tender_No",
        "tenderNumber",
        "description",
        "category",
        "organ_of_State",
        "department",
        "closing_Date",
        "date_Published",
        "status",
        "type",
        "actions",
    }

    key_hits = sum(1 for key in strong_keys if key in row)

    # Main tender row almost always has id + description.
    if row.get("id") is not None and row.get("description"):
        return True

    # Allow older variants but avoid nested awards.
    if key_hits >= 4 and (row.get("tender_No") or row.get("description")):
        return True

    return False


def _flatten_rows(value: Any) -> List[Dict[str, Any]]:
    """
    Extract only true tender rows from a DataTables JSON response.
    This intentionally avoids recursive inclusion of nested award/company objects
    as standalone rows, which was causing inflated row counts in V50.8.5.
    """
    rows: List[Dict[str, Any]] = []

    if isinstance(value, dict):
        for key in ("data", "aaData", "results", "items", "rows", "records"):
            sub = value.get(key)
            if isinstance(sub, list):
                for item in sub:
                    if isinstance(item, dict) and _is_tender_like_row(item):
                        rows.append(item)

        # Fallback only if no top-level table rows found.
        if not rows:
            for sub in value.values():
                if isinstance(sub, list):
                    for item in sub:
                        if isinstance(item, dict) and _is_tender_like_row(item):
                            rows.append(item)

    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and _is_tender_like_row(item):
                rows.append(item)

    return rows


def _row_text(row: Dict[str, Any]) -> str:
    priority_keys = [
        "id",
        "tenderId",
        "tender_ID",
        "tenderNumber",
        "tender_No",
        "tenderNo",
        "description",
        "tenderDescription",
        "category",
        "organOfState",
        "organ_of_State",
        "department",
        "buyer",
        "buyerName",
        "province",
        "actions",
        "documents",
        "documentName",
        "fileName",
        "file",
        "contactPerson",
        "email",
        "closing_Date",
        "date_Published",
        "briefingDate",
        "type",
        "status",
        "conditions",
        "delivery",
    ]

    parts: List[str] = []

    for key in priority_keys:
        if key in row:
            parts.append(_clean(row.get(key)))

    for key, value in row.items():
        if key not in priority_keys:
            # Keep nested fields available for text search, but not as separate rows.
            if isinstance(value, (dict, list)):
                parts.append(_json_blob(value))
            else:
                parts.append(_clean(value))

    return _clean(" ".join(parts))


def _stable_row_key(row: Dict[str, Any]) -> str:
    """
    Deduplicate by true tender identity. Avoid award ids and timestamp numbers.
    """
    for key in ("id", "tenderId", "tender_ID"):
        value = _clean(row.get(key))
        if value and value not in BAD_ID_VALUES:
            return f"id:{value}"

    tender_no = _clean(row.get("tender_No") or row.get("tenderNumber") or row.get("tenderNo"))
    organ = _clean(row.get("organ_of_State") or row.get("department") or row.get("buyerName"))
    description = _clean(row.get("description") or row.get("tenderDescription"))
    closing = _clean(row.get("closing_Date"))

    if tender_no:
        return f"tender_no:{tender_no}|{organ}|{closing}"

    ocid = _clean(row.get("ocid"))
    if ocid:
        return f"ocid:{ocid}"

    if description:
        return f"description:{description[:180]}|{organ}|{closing}"

    return _json_blob(row)[:700]


def _tokenise(text: str) -> List[str]:
    text = _safe_lower(text)
    text = re.sub(r"[^a-z0-9/]+", " ", text)
    stop = {
        "the", "and", "for", "with", "including", "copies", "copy",
        "supply", "delivery", "deliver", "of", "a", "an", "to", "in",
        "on", "at", "rfq", "rfp", "bid", "tender", "days", "day",
        "service", "services", "printed", "request", "quotation",
        "appointment", "provider", "procurement",
    }
    return [t for t in text.split() if len(t) >= 4 and t not in stop]


def _match_score(title: str, row_text: str, extra_markers: Optional[List[str]] = None) -> Dict[str, Any]:
    row_low = _safe_lower(row_text)
    title_low = _safe_lower(title)

    tokens = _tokenise(title)
    hits = [t for t in tokens if t in row_low]
    score = len(hits) / max(len(tokens), 1) if tokens else 0.0

    phrase = re.sub(r"\s+in\s+\d+\s+days?$", "", title_low, flags=re.I).strip()
    if phrase and len(phrase) >= 35 and phrase[:55] in row_low:
        score += 0.25

    default_markers = [
        "digital book",
        "jda 25th anniversary",
        "jdamark/digitalbook",
        "jdamark",
        "anniversary",
    ]

    markers: List[str] = []
    for marker in (extra_markers or []) + default_markers:
        marker = _safe_lower(marker)
        if marker and marker not in markers:
            markers.append(marker)

    marker_hits = [
        marker for marker in markers
        if marker in row_low
        and (
            marker in title_low
            or marker in {"jdamark/digitalbook", "jdamark", "anniversary"}
        )
    ]

    if "jdamark/digitalbook" in row_low:
        score = max(score, 0.95)
    elif "digital book" in row_low and "anniversary" in row_low:
        score = max(score, 0.90)
    elif len(marker_hits) >= 3:
        score = max(score, 0.85)
    elif len(marker_hits) == 2:
        score = max(score, 0.70)
    elif len(marker_hits) == 1:
        score = max(score, 0.45)

    return {
        "score": round(min(score, 1.0), 4),
        "hits": hits,
        "marker_hits": marker_hits,
        "target_token_count": len(tokens),
    }


def _extract_guids(blob: str) -> List[str]:
    out: List[str] = []
    pattern = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    for guid in re.findall(pattern, blob):
        guid = guid.lower()
        if guid not in out:
            out.append(guid)
    return out


def _extract_ids(blob: str, row: Dict[str, Any]) -> List[str]:
    """
    Only extract strong tender/document ids.
    Avoid timestamp fragments and sentinel max date values.
    """
    out: List[str] = []

    strong_keys = (
        "id",
        "ID",
        "tenderId",
        "tender_ID",
        "documentId",
        "docId",
        "fileId",
        "tendersID",
    )

    for key in strong_keys:
        value = row.get(key)
        if value is None:
            continue
        for match in re.findall(r"\b\d{3,10}\b", str(value)):
            if match not in BAD_ID_VALUES and match not in out:
                out.append(match)

    # Explicit JSON/html field names only. Do not collect arbitrary numbers from blob.
    explicit_patterns = [
        r'"(?:id|tenderId|tender_ID|documentId|docId|fileId|tendersID)"\s*:\s*(\d{3,10})',
        r"(?:documentId|tenderId|tendersID|docId|fileId)\s*[=:]\s*['\"]?(\d{3,10})",
    ]

    for pattern in explicit_patterns:
        for match in re.findall(pattern, blob, flags=re.I):
            if match not in BAD_ID_VALUES and match not in out:
                out.append(match)

    return out


def _extract_filenames(blob: str) -> List[str]:
    out: List[str] = []
    for match in re.findall(r"([A-Za-z0-9 _+\-–—(),.&/]+?\.(?:pdf|docx?|xlsx?|xls|zip))", blob, flags=re.I):
        name = _clean(match).strip(" ,;:'\"")
        if len(name) >= 8 and name not in out:
            out.append(name)
    return out


def _extract_emails(blob: str) -> List[str]:
    return sorted(set(re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", blob)))


def _candidate_urls(ids: List[str], guids: List[str], filenames: List[str]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen = set()

    download_endpoints = [
        "/Home/DownloadSpec",
        "/Home/DownloadTenderDocument",
        "/Home/DownloadFile",
        "/Home/DownloadDocument",
    ]

    detail_endpoints = [
        "/home/tenderdetails",
        "/Home/TenderDetails",
    ]

    for ident in ids:
        for endpoint in download_endpoints:
            for key in ("documentId", "id"):
                qs = urlencode({key: ident, "source": "sharepoint"})
                url = f"{ETENDERS_BASE}{endpoint}?{qs}"
                if url not in seen:
                    seen.add(url)
                    candidates.append({
                        "url": url,
                        "kind": "document",
                        "source": "id_pattern",
                        "id": ident,
                    })

        for endpoint in detail_endpoints:
            qs = urlencode({"id": ident})
            url = f"{ETENDERS_BASE}{endpoint}?{qs}"
            if url not in seen:
                seen.add(url)
                candidates.append({
                    "url": url,
                    "kind": "detail",
                    "source": "id_pattern",
                    "id": ident,
                })

    for guid in guids:
        for endpoint in download_endpoints:
            for key in ("documentGuid", "documentId", "id"):
                qs = urlencode({key: guid, "source": "sharepoint"})
                url = f"{ETENDERS_BASE}{endpoint}?{qs}"
                if url not in seen:
                    seen.add(url)
                    candidates.append({
                        "url": url,
                        "kind": "document",
                        "source": "guid_pattern",
                        "guid": guid,
                    })

    for ident in ids[:3]:
        for filename in filenames[:5]:
            for endpoint in download_endpoints:
                qs = urlencode({"documentId": ident, "fileName": filename, "source": "sharepoint"})
                url = f"{ETENDERS_BASE}{endpoint}?{qs}"
                if url not in seen:
                    seen.add(url)
                    candidates.append({
                        "url": url,
                        "kind": "document",
                        "source": "filename_pattern",
                        "id": ident,
                        "filename": filename,
                    })

    return candidates


def _make_params(status: str, start: int, length: int) -> Dict[str, str]:
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
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "_": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
    }

    if status != "":
        params["status"] = status

    return params


def _fetch_page(status: str, start: int, length: int) -> Dict[str, Any]:
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
        resp = requests.get(
            PAGINATED_ENDPOINT,
            params=_make_params(status, start, length),
            headers=headers,
            timeout=25,
        )

        content_type = resp.headers.get("content-type", "")

        if "json" not in content_type.lower():
            return {
                "ok": False,
                "status_code": resp.status_code,
                "url": resp.url,
                "status_filter": status,
                "start": start,
                "length": length,
                "row_count": 0,
                "records_total": None,
                "records_filtered": None,
                "rows": [],
                "error": f"non_json_response:{content_type}",
            }

        data = resp.json()
        rows = _flatten_rows(data)

        # Deduplicate within the page immediately.
        deduped_rows: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = _stable_row_key(row)
            if key not in deduped_rows:
                deduped_rows[key] = row

        return {
            "ok": 200 <= resp.status_code < 400,
            "status_code": resp.status_code,
            "url": resp.url,
            "status_filter": status,
            "start": start,
            "length": length,
            "row_count": len(rows),
            "deduped_row_count": len(deduped_rows),
            "records_total": data.get("recordsTotal") if isinstance(data, dict) else None,
            "records_filtered": data.get("recordsFiltered") if isinstance(data, dict) else None,
            "rows": list(deduped_rows.values()),
            "error": "",
        }

    except Exception as exc:
        return {
            "ok": False,
            "status_code": 0,
            "url": PAGINATED_ENDPOINT,
            "status_filter": status,
            "start": start,
            "length": length,
            "row_count": 0,
            "deduped_row_count": 0,
            "records_total": None,
            "records_filtered": None,
            "rows": [],
            "error": str(exc),
        }


def filter_etenders_locally(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    title = _clean(
        payload.get("title")
        or payload.get("description")
        or payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or ""
    )

    statuses = payload.get("statuses")
    if not isinstance(statuses, list) or not statuses:
        statuses = DEFAULT_STATUSES

    starts = payload.get("starts")
    if not isinstance(starts, list) or not starts:
        starts = DEFAULT_STARTS

    length = int(payload.get("length") or DEFAULT_LENGTH)
    min_match_score = float(payload.get("min_match_score") or 0.35)

    extra_markers = payload.get("markers")
    if not isinstance(extra_markers, list):
        extra_markers = []

    responses: List[Dict[str, Any]] = []
    rows_by_key: Dict[str, Dict[str, Any]] = {}
    duplicate_row_count = 0
    raw_row_count = 0
    page_deduped_row_count = 0

    for status in statuses:
        for start in starts:
            page = _fetch_page(str(status), int(start), length)

            raw_row_count += int(page.get("row_count") or 0)
            page_deduped_row_count += int(page.get("deduped_row_count") or 0)

            responses.append({k: v for k, v in page.items() if k != "rows"})

            for row in page.get("rows") or []:
                if not isinstance(row, dict):
                    continue

                key = _stable_row_key(row)

                if key in rows_by_key:
                    duplicate_row_count += 1
                    continue

                rows_by_key[key] = row

    matched_rows: List[Dict[str, Any]] = []

    for key, row in rows_by_key.items():
        blob = _json_blob(row)
        text = _row_text(row)
        match = _match_score(title, text, extra_markers)
        score = float(match.get("score") or 0.0)

        if score < min_match_score:
            continue

        ids = _extract_ids(blob, row)
        guids = _extract_guids(blob)
        filenames = _extract_filenames(blob)
        emails = _extract_emails(blob)
        candidates = _candidate_urls(ids, guids, filenames)

        matched_rows.append({
            "dedup_key": key,
            "match_score": round(score, 4),
            "match_hits": match.get("hits") or [],
            "marker_hits": match.get("marker_hits") or [],
            "ids": ids,
            "guids": guids,
            "filenames": filenames,
            "emails": emails,
            "candidate_url_count": len(candidates),
            "candidate_urls": candidates[:40],
            "raw_keys": sorted(row.keys()),
            "tender_id": row.get("id"),
            "tender_no": row.get("tender_No") or row.get("tenderNumber"),
            "description": row.get("description"),
            "buyer": row.get("organ_of_State") or row.get("department") or row.get("buyerName"),
            "status": row.get("status"),
            "closing_date": row.get("closing_Date"),
            "published_date": row.get("date_Published"),
            "contact_person": row.get("contactPerson"),
            "email": row.get("email"),
            "text_preview": text[:1200],
            "raw_row": row,
        })

    matched_rows.sort(key=lambda x: float(x.get("match_score") or 0), reverse=True)

    action = "matched_local_rows_found" if matched_rows else "no_local_matches_found"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "filtered_at": _now(),
        "title": title,
        "statuses": statuses,
        "starts": starts,
        "length": length,
        "min_match_score": min_match_score,
        "response_count": len(responses),
        "response_summaries": responses[:80],
        "raw_row_count_before_dedup": raw_row_count,
        "page_deduped_row_count": page_deduped_row_count,
        "duplicate_row_count_removed": duplicate_row_count,
        "unique_row_count": len(rows_by_key),
        "matched_row_count": len(matched_rows),
        "recommended_action": action,
        "matched_rows": matched_rows[:25],
        "notes": [
            "V50.8.6 fixes row overcounting by avoiding recursive nested award/company objects as tender rows.",
            "Rows are deduplicated by stable tender identity before scoring.",
            "Candidate URLs are deduplicated and generated only from strong ids/guids.",
            "Use matched_rows[0].candidate_urls to feed the next document probe/download engine.",
        ],
    }


def get_v50_8_5_status() -> Dict[str, Any]:
    """
    Keep same function name for backward-compatible API import.
    """
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_statuses": DEFAULT_STATUSES,
        "default_starts": DEFAULT_STARTS,
        "default_length": DEFAULT_LENGTH,
        "capabilities": [
            "server_search_bypass",
            "local_structured_row_filtering",
            "multi_status_page_fetching",
            "marker_based_matching",
            "stable_row_deduplication",
            "nested_award_row_suppression",
            "candidate_document_url_deduplication",
            "raw_row_exposure",
        ],
    }


def get_v50_8_6_status() -> Dict[str, Any]:
    return get_v50_8_5_status()
