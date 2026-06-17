"""
LMCP V50.9.7 - eTenders Tender Document Mapping Resolver

Purpose:
- V50.9.6 proved DownloadSpec works, but documentId is a global eTenders document id,
  not tender-specific by itself.
- V50.9.7 resolves the missing mapping layer:
    tender_id / tender_no / title -> DataTables row -> action HTML -> detail/control payload ->
    support document metadata -> real DownloadSpec documentId(s)

Routes:
    GET  /v50-9-7-document-mapping-resolver/status
    POST /v50-9-7-document-mapping-resolver/resolve
    POST /v50-9-7-document-mapping-resolver/download-mapped

Drop-in:
    app/services/etenders_document_mapping_resolver_v50_9_7_service.py
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode, urljoin

import requests


SERVICE_VERSION = "V50.9.7_ETENDERS_DOCUMENT_MAPPING_RESOLVER"
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
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/Home/opportunities",
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


def _resp_summary(resp: requests.Response, url: str) -> Dict[str, Any]:
    try:
        preview = resp.text[:800]
    except Exception:
        preview = ""
    return {
        "url": url,
        "ok": resp.ok,
        "status_code": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "content_disposition": resp.headers.get("content-disposition", ""),
        "content_length_header": resp.headers.get("content-length", ""),
        "size": len(resp.content or b""),
        "text_preview": preview,
    }


def _extract_ids_from_text(text: str) -> Dict[str, List[str]]:
    text = text or ""
    return {
        "document_ids": sorted(set(re.findall(r"(?:documentId|documentID|docId|id)\s*[=:]\s*['\"]?(\d{1,9})", text, flags=re.I))),
        "downloadspec_ids": sorted(set(re.findall(r"DownloadSpec\?documentId=(\d+)", text, flags=re.I))),
        "tender_ids": sorted(set(re.findall(r"(?:tenderId|tender_id|id)\s*[=:]\s*['\"]?(\d{3,9})", text, flags=re.I))),
        "guids": sorted(set(re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text))),
    }


def _deep_scan(obj: Any) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(x: Any, path: str) -> None:
        if isinstance(x, dict):
            blob = json.dumps(x, ensure_ascii=False)
            low = blob.lower()
            if any(k in low for k in [
                "download", "document", "support", "filename", "file", "attachment",
                "sharepoint", "guid", ".pdf", ".doc", ".xls", ".zip", "jdamark", "digital book"
            ]):
                found.append({"path": path, "value": x, "ids": _extract_ids_from_text(blob)})
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, item in enumerate(x):
                walk(item, f"{path}[{i}]")
        elif isinstance(x, str):
            low = x.lower()
            if any(k in low for k in ["download", "document", "support", "sharepoint", ".pdf", ".doc", ".xls", ".zip"]):
                found.append({"path": path, "value": x[:2000], "ids": _extract_ids_from_text(x)})

    walk(obj, "$")
    return found[:500]


def fetch_tender_details(tender_id: str) -> Dict[str, Any]:
    url = f"{BASE}/Home/TenderDetails?id={quote(str(tender_id))}"
    try:
        r = requests.get(url, headers=_headers({"Accept": "application/json, text/plain, */*"}), timeout=20)
        data = None
        try:
            data = r.json()
        except Exception:
            pass
        return {
            "ok": r.ok,
            "summary": _resp_summary(r, url),
            "data": data,
            "scan": _deep_scan(data) if data is not None else [],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "data": None, "scan": []}


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


def fetch_datatables_rows(search_terms: List[str], statuses: List[str], max_pages: int = 8, length: int = 50) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    matched_rows: List[Dict[str, Any]] = []

    for search in search_terms:
        for status in statuses:
            for page in range(max_pages):
                start = page * length
                url = _build_datatables_url(status=status, search=search, start=start, length=length, draw=page + 1)
                try:
                    r = requests.get(url, headers=_headers(), timeout=25)
                    summary = _resp_summary(r, url)
                    data = None
                    rows = []
                    try:
                        data = r.json()
                        rows = data.get("data") if isinstance(data, dict) else []
                        if rows is None:
                            rows = []
                    except Exception:
                        rows = []

                    calls.append({
                        "search": search,
                        "status": status,
                        "start": start,
                        "summary": summary,
                        "row_count": len(rows),
                    })

                    for row in rows:
                        blob = json.dumps(row, ensure_ascii=False)
                        low = blob.lower()
                        if any(term.lower() in low for term in search_terms if term):
                            matched_rows.append({
                                "search": search,
                                "status": status,
                                "start": start,
                                "row": row,
                                "ids": _extract_ids_from_text(blob),
                                "scan": _deep_scan(row),
                            })

                    # Stop if fewer than requested rows returned.
                    if len(rows) < length:
                        break
                except Exception as exc:
                    calls.append({"search": search, "status": status, "start": start, "error": str(exc), "row_count": 0})

    # de-dupe rows by JSON blob
    deduped = []
    seen = set()
    for item in matched_rows:
        key = json.dumps(item.get("row"), sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return {
        "call_count": len(calls),
        "calls": calls[-100:],
        "matched_row_count": len(deduped),
        "matched_rows": deduped[:100],
    }


def candidate_detail_urls_from_row(row_item: Dict[str, Any], tender_id: str) -> List[str]:
    row = row_item.get("row") or {}
    blob = json.dumps(row, ensure_ascii=False)
    ids = _extract_ids_from_text(blob)
    urls = set()

    # Any href in action HTML / row JSON.
    for href in re.findall(r'href=["\']([^"\']+)["\']', blob, flags=re.I):
        urls.add(urljoin(BASE, href.replace("\\/", "/")))

    # JS location URLs.
    for href in re.findall(r"(?:window\.location\.href|location\.href)\s*=\s*['\"]([^'\"]+)['\"]", blob, flags=re.I):
        urls.add(urljoin(BASE, href.replace("\\/", "/")))

    # Tender ids discovered in row.
    for tid in set(ids.get("tender_ids") or []) | {str(tender_id)}:
        if tid:
            urls.update([
                f"{BASE}/Home/TenderDetails?id={tid}",
                f"{BASE}/Home/GetTenderDetails?id={tid}",
                f"{BASE}/Home/TenderDocuments?id={tid}",
                f"{BASE}/Home/GetTenderDocuments?id={tid}",
                f"{BASE}/Home/GetSupportDocuments?tenderId={tid}",
                f"{BASE}/Home/GetDocuments?tenderId={tid}",
            ])

    for did in ids.get("document_ids") or []:
        urls.update([
            f"{BASE}/Home/DownloadSpec?documentId={did}&source=sharepoint",
            f"{BASE}/Home/DownloadSpec?documentId={did}",
        ])

    return list(urls)


def probe_candidate_urls(urls: List[str], output_dir: str, tender_id: str, save: bool = True) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    downloads: List[Dict[str, Any]] = []
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    for url in urls:
        try:
            r = requests.get(url, headers=_headers({"Accept": "*/*"}), timeout=30, allow_redirects=True)
            summary = _resp_summary(r, url)
            is_dl = _is_download_response(r)
            item = {
                **summary,
                "is_download_response": is_dl,
                "ids": _extract_ids_from_text(summary.get("text_preview", "")),
            }
            parsed = None
            try:
                parsed = r.json()
                item["json"] = parsed
                item["scan"] = _deep_scan(parsed)
            except Exception:
                pass

            if is_dl:
                filename = _content_disposition_filename(r.headers.get("content-disposition", ""))
                if not filename:
                    ext = mimetypes.guess_extension((r.headers.get("content-type") or "").split(";")[0].strip()) or ".bin"
                    filename = f"mapped_download{ext}"
                safe = _safe_filename(filename)
                path = output / f"ETENDERS_{tender_id}__MAPPED__{safe}"
                if save:
                    path.write_bytes(r.content)
                item.update({"filename": filename, "saved_path": str(path), "saved_size": path.stat().st_size if path.exists() else 0})
                downloads.append(item)

            # Keep only useful attempts
            if is_dl or item.get("scan") or r.status_code not in (404, 500):
                attempts.append(item)
        except Exception as exc:
            attempts.append({"url": url, "ok": False, "error": str(exc), "is_download_response": False})

    return {
        "attempt_count": len(attempts),
        "attempts": attempts[-200:],
        "download_count": len(downloads),
        "downloads": downloads,
    }


def resolve_mapping(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = _clean(payload.get("tender_id") or payload.get("id") or "155559")
    tender_no = _clean(payload.get("tender_no") or "JDAMARK/DIGITALBOOK /05/2026")
    title = _clean(payload.get("title") or payload.get("description") or "DIGITAL BOOK")
    output_dir = _clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR)
    save_downloads = bool(payload.get("save_downloads", True))

    statuses = payload.get("statuses") or ["1", "2", "3", "4", "5", "", "Published", "Open"]
    search_terms = []
    for x in [tender_id, tender_no, "JDAMARK", "DIGITALBOOK", "DIGITAL BOOK", title]:
        x = _clean(x)
        if x and x not in search_terms:
            search_terms.append(x)

    details = fetch_tender_details(tender_id)
    datatables = fetch_datatables_rows(search_terms=search_terms, statuses=statuses, max_pages=int(payload.get("max_pages") or 6), length=int(payload.get("length") or 50))

    candidate_urls = set()
    for row_item in datatables.get("matched_rows") or []:
        for url in candidate_detail_urls_from_row(row_item, tender_id):
            candidate_urls.add(url)

    # Always include known detail and common route candidates.
    candidate_urls.update([
        f"{BASE}/Home/TenderDetails?id={quote(tender_id)}",
        f"{BASE}/Home/GetTenderDetails?id={quote(tender_id)}",
        f"{BASE}/Home/TenderDocuments?id={quote(tender_id)}",
        f"{BASE}/Home/GetTenderDocuments?id={quote(tender_id)}",
        f"{BASE}/Home/GetSupportDocuments?tenderId={quote(tender_id)}",
        f"{BASE}/Home/GetDocuments?tenderId={quote(tender_id)}",
        f"{BASE}/Home/GetAttachments?tenderId={quote(tender_id)}",
    ])

    probed = probe_candidate_urls(sorted(candidate_urls), output_dir=output_dir, tender_id=tender_id, save=save_downloads)

    result = {
        "status": "mapped_download_found" if probed.get("download_count") else ("row_mapping_found" if datatables.get("matched_row_count") else "mapping_not_found_yet"),
        "service_version": SERVICE_VERSION,
        "resolved_at": _now(),
        "tender_id": tender_id,
        "tender_no": tender_no,
        "title": title,
        "details": details,
        "datatables": datatables,
        "candidate_url_count": len(candidate_urls),
        "candidate_urls": sorted(candidate_urls)[:300],
        "probe_results": probed,
        "safe_to_process": bool(probed.get("download_count")),
        "notes": [
            "If row_mapping_found but no mapped download, inspect datatables.matched_rows[*].row.actions and scan nodes.",
            "If mapping_not_found_yet, rerun with exact tender_no/title from TenderDetails JSON.",
            "This resolver avoids blind global documentId scanning and focuses on tender-specific row/action mapping.",
        ],
    }

    log_path = Path(output_dir) / f"ETENDERS_{tender_id}__v50_9_7_document_mapping.json"
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result["mapping_log"] = str(log_path)
    except Exception as exc:
        result["mapping_log_error"] = str(exc)

    return result


def download_mapped(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = _clean(payload.get("tender_id") or "UNKNOWN")
    output_dir = _clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR)
    url = _clean(payload.get("url") or "")
    document_id = payload.get("document_id")

    if not url:
        if document_id is None:
            return {"status": "error", "service_version": SERVICE_VERSION, "message": "Provide url or document_id.", "safe_to_process": False}
        url = f"{BASE}/Home/DownloadSpec?documentId={int(document_id)}&source=sharepoint"

    probed = probe_candidate_urls([url], output_dir=output_dir, tender_id=tender_id, save=True)
    if probed.get("download_count"):
        return {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "download": probed["downloads"][0],
            "safe_to_process": True,
        }
    return {
        "status": "not_verified_download",
        "service_version": SERVICE_VERSION,
        "probe_results": probed,
        "safe_to_process": False,
    }


def get_v50_9_7_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "tenderdetails_json_fetch",
            "datatables_row_search_by_tender_id_number_title",
            "action_html_href_onclick_extraction",
            "row_json_deep_document_scan",
            "candidate_tender_specific_route_probe",
            "mapped_download_validation",
            "mapped_download_save",
            "mapping_log_generation",
        ],
    }
