"""
LMCP V50.9.8 - eTenders Download Replay Reconstruction Engine

Purpose:
- V50.9.7 found tender row mapping but not yet the final support-document mapping.
- V50.9.8 reconstructs replayable download attempts from:
    - TenderDetails JSON
    - PaginatedTenderOpportunities rows
    - row action HTML
    - biddersdoc / biddersdoclink fields
    - href / onclick / JS patterns
    - candidate GET/POST ASP.NET routes
    - DownloadSpec route variants

Routes:
    GET  /v50-9-8-download-replay-reconstruction/status
    POST /v50-9-8-download-replay-reconstruction/reconstruct
    POST /v50-9-8-download-replay-reconstruction/replay

Drop-in:
    app/services/etenders_download_replay_reconstruction_v50_9_8_service.py
"""

from __future__ import annotations

import json
import os
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode, urljoin, urlparse, parse_qs

import requests


SERVICE_VERSION = "V50.9.8_ETENDERS_DOWNLOAD_REPLAY_RECONSTRUCTION"
BASE = "https://www.etenders.gov.za"
DEFAULT_OUTPUT_DIR = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "playwright" / "downloads")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(filename: str, fallback: str = "etenders_download.bin") -> str:
    name = _clean(filename) or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name).strip().strip(". ")
    if not name:
        name = fallback
    if len(name) > 180:
        stem = Path(name).stem[:150]
        suffix = Path(name).suffix or ".bin"
        name = f"{stem}{suffix}"
    return name


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/Home/opportunities",
        "Origin": BASE,
    }
    if extra:
        h.update(extra)
    return h


def _content_disposition_filename(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"filename\*=UTF-8''([^;]+)", value, re.I)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1)).strip('" ')
    m = re.search(r'filename="?([^";]+)"?', value, re.I)
    if m:
        return m.group(1).strip()
    return ""


def _is_download_response(resp: requests.Response) -> bool:
    ctype = (resp.headers.get("content-type") or "").lower()
    cdisp = (resp.headers.get("content-disposition") or "").lower()
    if resp.status_code != 200:
        return False
    if "attachment" in cdisp or "filename" in cdisp:
        return True
    if any(x in ctype for x in [
        "application/pdf",
        "application/octet-stream",
        "application/zip",
        "application/vnd",
        "application/msword",
    ]):
        return True
    head = resp.content[:20]
    return head.startswith(b"%PDF") or head.startswith(b"PK")


def _resp_summary(resp: requests.Response, url: str, method: str = "GET") -> Dict[str, Any]:
    try:
        preview = resp.text[:800]
    except Exception:
        preview = ""
    return {
        "method": method,
        "url": url,
        "ok": resp.ok,
        "status_code": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "content_disposition": resp.headers.get("content-disposition", ""),
        "content_length_header": resp.headers.get("content-length", ""),
        "size": len(resp.content or b""),
        "text_preview": preview,
    }


def _extract_ids(text: str) -> Dict[str, List[str]]:
    text = text or ""
    return {
        "document_ids": sorted(set(re.findall(r"(?:documentId|documentID|docId|document_Id|fileId|fileID|id)\s*[=:]\s*['\"]?(\d{1,10})", text, flags=re.I))),
        "downloadspec_ids": sorted(set(re.findall(r"DownloadSpec\?documentId=(\d+)", text, flags=re.I))),
        "tender_ids": sorted(set(re.findall(r"(?:tenderId|tendersID|tender_id|tendersId|id)\s*[=:]\s*['\"]?(\d{3,10})", text, flags=re.I))),
        "guids": sorted(set(re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text))),
        "hrefs": sorted(set(re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I))),
        "onclicks": sorted(set(re.findall(r'onclick=["\']([^"\']+)["\']', text, flags=re.I))),
        "urls": sorted(set(re.findall(r'https?://[^\s"\']+', text))),
    }


def _deep_scan(obj: Any) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(x: Any, path: str) -> None:
        if isinstance(x, dict):
            blob = json.dumps(x, ensure_ascii=False)
            low = blob.lower()
            if any(k in low for k in [
                "download", "document", "support", "filename", "file", "attachment",
                "sharepoint", ".pdf", ".doc", ".xls", ".zip", "biddersdoc", "biddersdoclink",
                "digital book", "jdamark"
            ]):
                found.append({"path": path, "value": x, "ids": _extract_ids(blob)})
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, item in enumerate(x):
                walk(item, f"{path}[{i}]")
        elif isinstance(x, str):
            low = x.lower()
            if any(k in low for k in ["download", "document", "support", "sharepoint", ".pdf", ".doc", ".xls", ".zip", "biddersdoc"]):
                found.append({"path": path, "value": x[:2500], "ids": _extract_ids(x)})

    walk(obj, "$")
    return found[:800]


def _build_datatables_url(status: str, search: str, start: int, length: int, draw: int = 1) -> str:
    params = {
        "draw": draw,
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
        "start": start,
        "length": length,
        "search[value]": search,
        "search[regex]": "false",
        "status": status,
    }
    return f"{BASE}/Home/PaginatedTenderOpportunities?{urlencode(params)}"


def fetch_tender_details(tender_id: str) -> Dict[str, Any]:
    url = f"{BASE}/Home/TenderDetails?id={quote(str(tender_id))}"
    try:
        r = requests.get(url, headers=_headers({"Accept": "application/json, text/plain, */*"}), timeout=25)
        data = None
        try:
            data = r.json()
        except Exception:
            pass
        return {
            "summary": _resp_summary(r, url),
            "data": data,
            "scan": _deep_scan(data) if data is not None else [],
        }
    except Exception as exc:
        return {"error": str(exc), "data": None, "scan": []}


def fetch_matching_rows(tender_id: str, tender_no: str, title: str, statuses: List[str], max_pages: int, length: int) -> Dict[str, Any]:
    search_terms = []
    for x in [str(tender_id), tender_no, title, "JDAMARK", "DIGITALBOOK", "DIGITAL BOOK"]:
        x = _clean(x)
        if x and x not in search_terms:
            search_terms.append(x)

    rows = []
    calls = []
    target_needles = [str(tender_id).lower(), tender_no.lower(), "jdamark", "digital book", "digitalbook"]

    for search in search_terms:
        for status in statuses:
            for page in range(max_pages):
                start = page * length
                url = _build_datatables_url(status=status, search=search, start=start, length=length, draw=page + 1)
                try:
                    r = requests.get(url, headers=_headers(), timeout=35)
                    summary = _resp_summary(r, url)
                    data = None
                    page_rows = []
                    try:
                        data = r.json()
                        page_rows = data.get("data") if isinstance(data, dict) else []
                        if page_rows is None:
                            page_rows = []
                    except Exception:
                        page_rows = []

                    calls.append({"search": search, "status": status, "start": start, "row_count": len(page_rows), "summary": summary})

                    for row in page_rows:
                        blob = json.dumps(row, ensure_ascii=False)
                        low = blob.lower()
                        score = sum(1 for n in target_needles if n and n in low)
                        if score > 0:
                            rows.append({
                                "score": score,
                                "search": search,
                                "status": status,
                                "start": start,
                                "row": row,
                                "ids": _extract_ids(blob),
                                "scan": _deep_scan(row),
                            })

                    if len(page_rows) < length:
                        break
                except Exception as exc:
                    calls.append({"search": search, "status": status, "start": start, "error": str(exc), "row_count": 0})

    # Deduplicate
    out = []
    seen = set()
    for item in sorted(rows, key=lambda x: x.get("score", 0), reverse=True):
        key = json.dumps(item.get("row"), sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(item)

    return {"call_count": len(calls), "calls": calls[-150:], "matched_row_count": len(out), "matched_rows": out[:200]}


def build_replay_candidates(tender_id: str, support_guid: str, rows: List[Dict[str, Any]], details: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    def add(method: str, url: str, data: Optional[Dict[str, Any]] = None, source: str = "", note: str = ""):
        if not url:
            return
        full_url = urljoin(BASE, url.replace("\\/", "/"))
        key = (method.upper(), full_url, json.dumps(data or {}, sort_keys=True))
        candidates.append({"method": method.upper(), "url": full_url, "data": data or None, "source": source, "note": note, "_key": key})

    # Direct standard routes
    tid = quote(str(tender_id))
    guid = quote(str(support_guid or ""))

    route_names = [
        "DownloadSpec",
        "DownloadDocument",
        "DownloadTenderDocument",
        "DownloadSupportDocument",
        "GetDocument",
        "GetTenderDocument",
        "GetSupportDocument",
        "SupportDocument",
        "TenderDocument",
        "TenderDocuments",
        "GetTenderDocuments",
        "GetSupportDocuments",
    ]

    for route in route_names:
        add("GET", f"/Home/{route}?tenderId={tid}", source="standard_tenderId")
        add("GET", f"/Home/{route}?id={tid}", source="standard_id")
        add("POST", f"/Home/{route}", {"tenderId": str(tender_id)}, source="standard_post_tenderId")
        add("POST", f"/Home/{route}", {"id": str(tender_id)}, source="standard_post_id")
        if support_guid:
            add("GET", f"/Home/{route}?supportDocumentID={guid}", source="standard_guid")
            add("GET", f"/Home/{route}?documentGuid={guid}", source="standard_guid")
            add("GET", f"/Home/{route}?id={guid}", source="standard_guid")
            add("POST", f"/Home/{route}", {"supportDocumentID": support_guid}, source="standard_post_guid")
            add("POST", f"/Home/{route}", {"documentGuid": support_guid}, source="standard_post_guid")

    # From details and rows: hrefs, onclicks, ids.
    blobs = []
    blobs.append(json.dumps(details, ensure_ascii=False))
    for row_item in rows:
        blobs.append(json.dumps(row_item.get("row"), ensure_ascii=False))
        for scan in row_item.get("scan") or []:
            blobs.append(json.dumps(scan, ensure_ascii=False))

    for blob in blobs:
        ids = _extract_ids(blob)

        for href in ids.get("hrefs") or []:
            add("GET", href, source="href_extracted")

        for url in ids.get("urls") or []:
            add("GET", url, source="url_extracted")

        for onclick in ids.get("onclicks") or []:
            # Common JS function params e.g. download(123), getDocument('123'), showTenderDetails(155559)
            for n in re.findall(r"['\"]?(\d{1,10})['\"]?", onclick):
                for route in route_names:
                    add("GET", f"/Home/{route}?documentId={n}&source=sharepoint", source="onclick_numeric_param", note=onclick[:300])
                    add("GET", f"/Home/{route}?id={n}", source="onclick_numeric_param", note=onclick[:300])
                    add("POST", f"/Home/{route}", {"documentId": n, "source": "sharepoint"}, source="onclick_numeric_param", note=onclick[:300])

            for g in re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", onclick):
                for route in route_names:
                    add("GET", f"/Home/{route}?supportDocumentID={quote(g)}", source="onclick_guid_param", note=onclick[:300])
                    add("POST", f"/Home/{route}", {"supportDocumentID": g}, source="onclick_guid_param", note=onclick[:300])

        for did in set((ids.get("document_ids") or []) + (ids.get("downloadspec_ids") or [])):
            for route in ["DownloadSpec", "DownloadDocument", "DownloadTenderDocument", "DownloadSupportDocument"]:
                add("GET", f"/Home/{route}?documentId={did}&source=sharepoint", source="document_id_extracted")
                add("GET", f"/Home/{route}?documentId={did}", source="document_id_extracted")
                add("POST", f"/Home/{route}", {"documentId": did, "source": "sharepoint"}, source="document_id_extracted")

    # eTenders row often has eSubmission/action fields. Try all row values that look like ids.
    for row_item in rows:
        row = row_item.get("row") or {}
        for k, v in row.items():
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
                n = str(v)
                if 1 <= len(n) <= 10:
                    for route in route_names:
                        add("GET", f"/Home/{route}?id={n}", source=f"row_numeric_field:{k}")
                        add("GET", f"/Home/{route}?tenderId={n}", source=f"row_numeric_field:{k}")
                        add("GET", f"/Home/{route}?documentId={n}&source=sharepoint", source=f"row_numeric_field:{k}")
                        add("POST", f"/Home/{route}", {"id": n}, source=f"row_numeric_field:{k}")

        # Explicit fields
        for fld in ["biddersdoclink", "biddersdoc", "actions", "supportDocuments", "documents", "document", "file", "files"]:
            val = row.get(fld)
            if val:
                val_blob = json.dumps(val, ensure_ascii=False)
                ids = _extract_ids(val_blob)
                for href in ids.get("hrefs") or []:
                    add("GET", href, source=f"row_field:{fld}")
                for url in ids.get("urls") or []:
                    add("GET", url, source=f"row_field:{fld}")

    # Deduplicate preserving first occurrence.
    deduped = []
    seen = set()
    for c in candidates:
        key = c.pop("_key", None)
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return deduped[:1500]


def execute_candidate(candidate: Dict[str, Any], output_dir: Path, tender_id: str, save: bool) -> Dict[str, Any]:
    method = candidate.get("method", "GET").upper()
    url = candidate.get("url")
    data = candidate.get("data") or None

    try:
        if method == "POST":
            resp = requests.post(url, headers=_headers({"Accept": "*/*"}), data=data, timeout=35, allow_redirects=True)
        else:
            resp = requests.get(url, headers=_headers({"Accept": "*/*"}), timeout=35, allow_redirects=True)

        item = {
            **candidate,
            "response": _resp_summary(resp, url, method),
            "is_download_response": _is_download_response(resp),
            "ids": _extract_ids(resp.text[:5000] if not _is_download_response(resp) else ""),
        }

        try:
            parsed = resp.json()
            item["json"] = parsed
            item["scan"] = _deep_scan(parsed)
        except Exception:
            pass

        if _is_download_response(resp):
            filename = _content_disposition_filename(resp.headers.get("content-disposition", ""))
            if not filename:
                ext = mimetypes.guess_extension((resp.headers.get("content-type") or "").split(";")[0].strip()) or ".bin"
                filename = "replayed_download" + ext
            safe = _safe_filename(filename)
            path = output_dir / f"ETENDERS_{tender_id}__V50_9_8__{safe}"
            if save:
                output_dir.mkdir(parents=True, exist_ok=True)
                path.write_bytes(resp.content)
            item["download"] = {
                "filename": filename,
                "saved_path": str(path),
                "saved": save,
                "saved_size": path.stat().st_size if path.exists() else 0,
            }
        return item

    except Exception as exc:
        return {**candidate, "error": str(exc), "is_download_response": False}


def reconstruct_download_replay(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = _clean(payload.get("tender_id") or "155559")
    support_guid = _clean(payload.get("supportDocumentID") or payload.get("support_document_id") or payload.get("document_guid") or "")
    tender_no = _clean(payload.get("tender_no") or "JDAMARK/DIGITALBOOK /05/2026")
    title = _clean(payload.get("title") or "RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY")
    statuses = payload.get("statuses") or ["1", "Published", "Open"]
    max_pages = int(payload.get("max_pages") or 10)
    length = int(payload.get("length") or 50)
    save_downloads = bool(payload.get("save_downloads", True))
    output_dir = Path(_clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    max_candidates_to_execute = int(payload.get("max_candidates_to_execute") or 250)

    details = fetch_tender_details(tender_id)
    row_result = fetch_matching_rows(tender_id, tender_no, title, statuses, max_pages, length)
    candidates = build_replay_candidates(tender_id, support_guid, row_result.get("matched_rows") or [], details)

    executed = []
    downloads = []
    useful = []

    for candidate in candidates[:max_candidates_to_execute]:
        item = execute_candidate(candidate, output_dir, tender_id, save_downloads)
        if item.get("is_download_response"):
            downloads.append(item)
            executed.append(item)
        else:
            resp = item.get("response") or {}
            if item.get("scan") or resp.get("status_code") not in (404, 500) or item.get("ids", {}).get("document_ids"):
                useful.append(item)
                executed.append(item)

    result = {
        "status": "download_replay_found" if downloads else ("replay_candidates_found" if candidates else "no_replay_candidates_found"),
        "service_version": SERVICE_VERSION,
        "reconstructed_at": _now(),
        "tender_id": tender_id,
        "support_document_id": support_guid,
        "tender_no": tender_no,
        "title": title,
        "details": details,
        "row_result": row_result,
        "candidate_count": len(candidates),
        "candidates_preview": candidates[:120],
        "executed_count": len(executed),
        "useful_count": len(useful),
        "useful_results": useful[:150],
        "download_count": len(downloads),
        "downloads": downloads,
        "safe_to_process": bool(downloads),
        "notes": [
            "If download_count > 0, the final replay route is solved.",
            "If only replay_candidates_found, inspect row_result.matched_rows and useful_results for hidden JSON/document IDs.",
            "This engine avoids blind global scanning; it reconstructs requests from tender-specific evidence.",
        ],
    }

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / f"ETENDERS_{tender_id}__v50_9_8_download_replay_reconstruction.json"
        log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result["reconstruction_log"] = str(log_path)
    except Exception as exc:
        result["reconstruction_log_error"] = str(exc)

    return result


def replay_one(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = _clean(payload.get("tender_id") or "UNKNOWN")
    output_dir = Path(_clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    candidate = {
        "method": _clean(payload.get("method") or "GET").upper(),
        "url": _clean(payload.get("url") or ""),
        "data": payload.get("data") or None,
        "source": "manual_replay",
    }

    if not candidate["url"]:
        document_id = payload.get("document_id")
        if document_id is None:
            return {"status": "error", "service_version": SERVICE_VERSION, "message": "Provide url or document_id.", "safe_to_process": False}
        candidate["url"] = f"{BASE}/Home/DownloadSpec?documentId={int(document_id)}&source=sharepoint"

    item = execute_candidate(candidate, output_dir, tender_id, save=True)
    return {
        "status": "ok" if item.get("is_download_response") else "not_verified_download",
        "service_version": SERVICE_VERSION,
        "result": item,
        "safe_to_process": bool(item.get("is_download_response")),
    }


def get_v50_9_8_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "tender_specific_row_reconstruction",
            "href_onclick_url_extraction",
            "aspnet_get_post_route_replay",
            "downloadspec_variant_replay",
            "json_document_id_scan",
            "mapped_binary_download_save",
            "replay_log_generation",
        ],
    }
