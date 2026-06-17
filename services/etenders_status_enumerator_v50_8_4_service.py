"""
LMCP V50.8.4 - eTenders Multi-Status Dataset Enumerator

Purpose:
- eTenders DataTables endpoint uses a `status` parameter.
- Previous V50.8.3 only queried status=1.
- This engine queries multiple status values and pages, merges rows, de-duplicates,
  and matches structured rows against the target RFQ title/reference.

Drop-in:
    app/services/etenders_status_enumerator_v50_8_4_service.py
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests


SERVICE_VERSION = "V50.8.4_ETENDERS_STATUS_ENUMERATOR"

ETENDERS_OPPORTUNITIES = "https://www.etenders.gov.za/Home/opportunities"
PAGINATED_ENDPOINT = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"

DEFAULT_STATUSES = ["0", "1", "2", "3", "4", "5", "", "Open", "Closed", "Cancelled", "Awarded"]


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

    marker_boosts = [
        "jdamark/digitalbook",
        "digitalbook",
        "jda 25th anniversary",
        "digital book",
    ]
    for marker in marker_boosts:
        if marker in row_low and marker in _safe_lower(target_title + " JDAMARK/DIGITALBOOK"):
            score = max(score, 0.85)

    return {
        "score": round(min(score, 1.0), 4),
        "hits": hits,
        "target_token_count": len(tokens),
    }


def _flatten_rows(value: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if isinstance(value, dict):
        for key in ("data", "aaData", "results", "items", "rows", "records"):
            sub = value.get(key)
            if isinstance(sub, list):
                for item in sub:
                    if isinstance(item, dict):
                        rows.append(item)
                    if isinstance(item, (dict, list)):
                        rows.extend(_flatten_rows(item))

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
        return json.dumps(row, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(row or "")


def _row_text(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    priority_keys = [
        "id",
        "tenderId",
        "tenderNumber",
        "tender_No",
        "tenderNo",
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
        "contactPerson",
        "email",
        "closing_Date",
        "date_Published",
    ]
    for key in priority_keys:
        if key in row:
            parts.append(_clean(row.get(key)))

    for key, value in row.items():
        if key not in priority_keys:
            if isinstance(value, (dict, list)):
                parts.append(_row_blob(value))
            else:
                parts.append(_clean(value))

    return _clean(" ".join(parts))


def _fingerprint_row(row: Dict[str, Any]) -> str:
    for key in ("id", "tenderId", "tender_ID", "tenderNumber", "tender_No", "description"):
        value = _clean(row.get(key))
        if value:
            return f"{key}:{value}"
    return _row_blob(row)[:500]


def _extract_guids(blob: str) -> List[str]:
    pattern = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    out: List[str] = []
    for guid in re.findall(pattern, blob):
        guid = guid.lower()
        if guid not in out:
            out.append(guid)
    return out


def _extract_ids(blob: str, row: Dict[str, Any]) -> List[str]:
    out: List[str] = []

    for key in ("id", "ID", "tenderId", "tender_ID", "documentId", "docId", "fileId"):
        value = row.get(key)
        if value is None:
            continue
        for match in re.findall(r"\b\d{3,10}\b", str(value)):
            if match not in out:
                out.append(match)

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


def _make_datatables_params(status: str, search_value: str, start: int, length: int) -> Dict[str, str]:
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
        "search[value]": search_value,
        "search[regex]": "false",
        "_": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
    }
    if status != "":
        params["status"] = str(status)
    return params


def _fetch_status_page(status: str, search_value: str, start: int, length: int) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": ETENDERS_OPPORTUNITIES,
        "X-Requested-With": "XMLHttpRequest",
    }

    params = _make_datatables_params(status, search_value, start, length)

    try:
        r = requests.get(PAGINATED_ENDPOINT, params=params, headers=headers, timeout=25)
        data = r.json() if r.text else {}
        rows = _flatten_rows(data)
        return {
            "ok": 200 <= r.status_code < 400,
            "status_code": r.status_code,
            "url": r.url,
            "content_type": r.headers.get("content-type", ""),
            "status_filter": status,
            "search_value": search_value,
            "start": start,
            "length": length,
            "row_count": len(rows),
            "records_total": data.get("recordsTotal") if isinstance(data, dict) else None,
            "records_filtered": data.get("recordsFiltered") if isinstance(data, dict) else None,
            "rows": rows,
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 0,
            "url": PAGINATED_ENDPOINT,
            "content_type": "",
            "status_filter": status,
            "search_value": search_value,
            "start": start,
            "length": length,
            "row_count": 0,
            "records_total": None,
            "records_filtered": None,
            "rows": [],
            "error": str(exc),
        }


def enumerate_etenders_statuses(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    search_variants: List[str] = []
    for variant in [
        title,
        re.sub(r"\s+in\s+\d+\s+days?$", "", title, flags=re.I).strip(),
        "DIGITAL BOOK" if "digital" in _safe_lower(title) else "",
        "JDA 25TH ANNIVERSARY" if "jda" in _safe_lower(title) else "",
        "JDAMARK/DIGITALBOOK" if "digital" in _safe_lower(title) else "",
        "",
    ]:
        variant = _clean(variant)
        if variant not in search_variants:
            search_variants.append(variant)

    length = int(payload.get("length") or 50)
    starts = payload.get("starts")
    if not isinstance(starts, list) or not starts:
        starts = [0, 50, 100, 150, 200]

    responses: List[Dict[str, Any]] = []
    unique_rows: Dict[str, Dict[str, Any]] = {}

    for status in statuses:
        status_str = str(status)
        for search_value in search_variants[:6]:
            # If searching exact terms, usually first page is enough; empty search scans configured pages.
            run_starts = starts if search_value == "" else [0]
            for start in run_starts:
                resp = _fetch_status_page(status_str, search_value, int(start), length)
                responses.append({k: v for k, v in resp.items() if k != "rows"})
                for row in resp.get("rows") or []:
                    if not isinstance(row, dict):
                        continue
                    fp = _fingerprint_row(row)
                    if fp not in unique_rows:
                        unique_rows[fp] = row

    matched_rows: List[Dict[str, Any]] = []

    for fp, row in unique_rows.items():
        blob = _row_blob(row)
        text = _row_text(row)
        match = _match_score(title, text)
        score = float(match.get("score") or 0.0)

        if "jdamark/digitalbook" in _safe_lower(text):
            score = max(score, 0.95)

        if score < 0.35:
            continue

        matched_rows.append({
            "fingerprint": fp,
            "match_score": round(score, 4),
            "match_hits": match.get("hits") or [],
            "ids": _extract_ids(blob, row),
            "guids": _extract_guids(blob),
            "filenames": _extract_filenames(blob),
            "raw_keys": sorted(row.keys()),
            "text_preview": text[:1000],
            "raw_row": row,
        })

    matched_rows.sort(key=lambda x: float(x.get("match_score") or 0), reverse=True)

    action = "matched_rows_found" if matched_rows else "no_matching_rows_across_statuses"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "enumerated_at": _now(),
        "title": title,
        "statuses_tested": statuses,
        "search_variants": search_variants,
        "starts_tested": starts,
        "response_count": len(responses),
        "response_summaries": responses[:80],
        "unique_row_count": len(unique_rows),
        "matched_row_count": len(matched_rows),
        "recommended_action": action,
        "matched_rows": matched_rows[:20],
        "notes": [
            "V50.8.4 enumerates multiple eTenders status values and pages.",
            "It returns raw_row for matched rows so the next engine can learn exact field keys.",
            "If matched_row_count is still zero, the tender may require session context or be removed from the public dataset.",
        ],
    }


def get_v50_8_4_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_statuses": DEFAULT_STATUSES,
        "capabilities": [
            "multi_status_datatables_fetch",
            "multi_page_enumeration",
            "structured_row_deduplication",
            "cross_status_title_matching",
            "raw_row_field_exposure_for_learning",
        ],
    }
