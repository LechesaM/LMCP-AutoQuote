"""
LMCP V50.9.6 - eTenders Hidden API Discovery + DownloadSpec Replay Engine

Purpose:
- V50.9.5 confirmed:
    - /Home/TenderDetails?id=155559 returns JSON only
    - visible DOM has no document links
    - /Home/DownloadSpec?documentId=NN&source=sharepoint is a real eTenders download pattern
- V50.9.6 focuses on discovering hidden document metadata/API routes for a tender_id.

What it does:
1. Fetches TenderDetails JSON.
2. Tries known and likely hidden document metadata endpoints.
3. Probes DownloadSpec documentId ranges safely.
4. Captures useful non-404 / attachment / filename responses.
5. Saves verified downloads to runtime/playwright/downloads.
6. Returns candidate document IDs and replayable URLs.

Routes:
    GET  /v50-9-6-hidden-api-discovery/status
    POST /v50-9-6-hidden-api-discovery/discover
    POST /v50-9-6-hidden-api-discovery/replay-download

Drop-in:
    app/services/etenders_hidden_api_discovery_v50_9_6_service.py
"""

from __future__ import annotations

import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import requests


SERVICE_VERSION = "V50.9.6_ETENDERS_HIDDEN_API_DISCOVERY"
DEFAULT_OUTPUT_DIR = "runtime/playwright/downloads"
BASE = "https://www.etenders.gov.za"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(filename: str, fallback: str = "etenders_download.bin") -> str:
    name = _clean(filename) or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
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
    }
    if extra:
        h.update(extra)
    return h


def _content_disposition_filename(value: str) -> str:
    if not value:
        return ""
    # filename*=UTF-8''...
    m = re.search(r"filename\*=UTF-8''([^;]+)", value, re.I)
    if m:
        try:
            from urllib.parse import unquote
            return unquote(m.group(1)).strip('" ')
        except Exception:
            return m.group(1).strip('" ')
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
    content = resp.content[:20]
    return content.startswith(b"%PDF") or content.startswith(b"PK")


def _response_summary(resp: requests.Response, url: str) -> Dict[str, Any]:
    text_preview = ""
    try:
        text_preview = resp.text[:500]
    except Exception:
        text_preview = ""

    return {
        "url": url,
        "ok": resp.ok,
        "status_code": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "content_disposition": resp.headers.get("content-disposition", ""),
        "content_length_header": resp.headers.get("content-length", ""),
        "size": len(resp.content or b""),
        "text_preview": text_preview,
    }


def _deep_find_docs(obj: Any) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(x: Any, path: str = "$") -> None:
        if isinstance(x, dict):
            blob = json.dumps(x, ensure_ascii=False).lower()
            if any(k in blob for k in [
                "document", "support", "filename", "file_name", "download", "attachment",
                "sharepoint", ".pdf", ".doc", ".xls", ".zip", "guid"
            ]):
                found.append({"path": path, "value": x})
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, item in enumerate(x):
                walk(item, f"{path}[{i}]")

    walk(obj)
    return found[:200]


def fetch_tender_details(tender_id: str) -> Dict[str, Any]:
    url = f"{BASE}/Home/TenderDetails?id={quote(str(tender_id))}"
    try:
        r = requests.get(url, headers=_headers({"Accept": "application/json, text/plain, */*"}), timeout=20)
        summary = _response_summary(r, url)
        data = None
        try:
            data = r.json()
        except Exception:
            data = None
        return {
            "ok": r.ok,
            "url": url,
            "summary": summary,
            "data": data,
            "document_like_nodes": _deep_find_docs(data) if data is not None else [],
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc), "data": None, "document_like_nodes": []}


def _candidate_metadata_urls(tender_id: str, support_document_id: str = "") -> List[str]:
    tid = quote(str(tender_id))
    guid = quote(str(support_document_id or ""))

    paths = [
        f"/Home/TenderDocuments?id={tid}",
        f"/Home/GetTenderDocuments?id={tid}",
        f"/Home/GetTenderDocuments?tenderId={tid}",
        f"/Home/TenderDocument?id={tid}",
        f"/Home/TenderDocument?tenderId={tid}",
        f"/Home/SupportDocuments?id={tid}",
        f"/Home/GetSupportDocuments?id={tid}",
        f"/Home/GetSupportDocuments?tenderId={tid}",
        f"/Home/SupportDocument?id={tid}",
        f"/Home/GetTenderSupportDocuments?id={tid}",
        f"/Home/GetTenderSupportDocuments?tenderId={tid}",
        f"/Home/TenderDetailsDocuments?id={tid}",
        f"/Home/TenderDetailsDocument?id={tid}",
        f"/Home/GetTenderDetailsDocuments?id={tid}",
        f"/Home/GetDocuments?id={tid}",
        f"/Home/GetDocuments?tenderId={tid}",
        f"/Home/Documents?id={tid}",
        f"/Home/Documents?tenderId={tid}",
        f"/Home/DownloadDocuments?id={tid}",
        f"/Home/GetDocumentList?id={tid}",
        f"/Home/GetDocumentList?tenderId={tid}",
        f"/Home/GetFiles?id={tid}",
        f"/Home/GetFiles?tenderId={tid}",
        f"/Home/TenderFiles?id={tid}",
        f"/Home/TenderFiles?tenderId={tid}",
        f"/Home/DocumentList?id={tid}",
        f"/Home/DocumentList?tenderId={tid}",
        f"/Home/AttachmentList?id={tid}",
        f"/Home/AttachmentList?tenderId={tid}",
        f"/Home/GetAttachments?id={tid}",
        f"/Home/GetAttachments?tenderId={tid}",
        f"/Home/TenderAttachments?id={tid}",
        f"/Home/TenderAttachments?tenderId={tid}",
        f"/Home/LoadTenderDocuments?id={tid}",
        f"/Home/LoadTenderDocuments?tenderId={tid}",
        f"/Home/LoadDocuments?id={tid}",
        f"/Home/LoadDocuments?tenderId={tid}",
        f"/home/tenderdetails?id={tid}",
    ]

    if support_document_id:
        paths += [
            f"/Home/SupportDocument?id={guid}",
            f"/Home/GetSupportDocument?id={guid}",
            f"/Home/GetSupportDocument?documentId={guid}",
            f"/Home/GetSupportDocument?supportDocumentID={guid}",
            f"/Home/DownloadSupportDocument?supportDocumentID={guid}",
            f"/Home/DownloadSupportDocument?documentId={guid}",
            f"/Home/DownloadDocument?documentId={guid}",
            f"/Home/DownloadDocument?supportDocumentID={guid}",
            f"/Home/DownloadTenderDocument?documentId={guid}",
            f"/Home/DownloadTenderDocument?supportDocumentID={guid}",
        ]

    # de-dupe preserving order
    out = []
    seen = set()
    for p in paths:
        url = BASE + p
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def probe_metadata_endpoints(tender_id: str, support_document_id: str = "") -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for url in _candidate_metadata_urls(tender_id, support_document_id):
        try:
            r = requests.get(url, headers=_headers(), timeout=15)
            summary = _response_summary(r, url)
            useful = False
            parsed = None
            docs = []

            if r.status_code not in (404, 500):
                useful = True

            try:
                parsed = r.json()
                docs = _deep_find_docs(parsed)
                if docs:
                    useful = True
            except Exception:
                parsed = None

            if _is_download_response(r):
                useful = True

            results.append({
                **summary,
                "useful": useful,
                "json": parsed if useful else None,
                "document_like_nodes": docs if useful else [],
                "is_download_response": _is_download_response(r),
            })
        except Exception as exc:
            results.append({"url": url, "ok": False, "error": str(exc), "useful": False})
    return results


def _downloadspec_urls(document_id: int) -> List[str]:
    return [
        f"{BASE}/Home/DownloadSpec?documentId={document_id}&source=sharepoint",
        f"{BASE}/Home/DownloadSpec?documentId={document_id}",
        f"{BASE}/Home/DownloadDocument?documentId={document_id}&source=sharepoint",
        f"{BASE}/Home/DownloadDocument?documentId={document_id}",
        f"{BASE}/Home/DownloadTenderDocument?documentId={document_id}&source=sharepoint",
        f"{BASE}/Home/DownloadTenderDocument?documentId={document_id}",
    ]


def probe_downloadspec_range(
    tender_id: str,
    start_id: int = 1,
    end_id: int = 250,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    save_verified: bool = True,
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    verified: List[Dict[str, Any]] = []
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    for document_id in range(int(start_id), int(end_id) + 1):
        for url in _downloadspec_urls(document_id):
            try:
                r = requests.get(
                    url,
                    headers=_headers({
                        "Accept": "*/*",
                        "Referer": f"{BASE}/Home/opportunities",
                    }),
                    timeout=20,
                    allow_redirects=True,
                )
                summary = _response_summary(r, url)
                summary["document_id"] = document_id
                summary["is_download_response"] = _is_download_response(r)

                # Keep useful attempts only to avoid huge output.
                useful = (
                    r.status_code not in (404, 500)
                    or _is_download_response(r)
                    or "filename" in (r.headers.get("content-disposition") or "").lower()
                )
                summary["useful"] = useful

                if _is_download_response(r):
                    filename = _content_disposition_filename(r.headers.get("content-disposition", ""))
                    if not filename:
                        ext = mimetypes.guess_extension((r.headers.get("content-type") or "").split(";")[0].strip()) or ".bin"
                        filename = f"documentId_{document_id}{ext}"
                    safe = _safe_filename(filename)
                    path = output / f"ETENDERS_{tender_id}__documentId_{document_id}__{safe}"
                    if save_verified:
                        path.write_bytes(r.content)
                    item = {
                        **summary,
                        "filename": filename,
                        "saved_path": str(path),
                        "saved": save_verified,
                        "saved_size": path.stat().st_size if path.exists() else 0,
                    }
                    verified.append(item)
                    attempts.append(item)
                elif useful:
                    attempts.append(summary)

            except Exception as exc:
                # Only log unusual errors.
                if document_id % 25 == 0:
                    attempts.append({"document_id": document_id, "url": url, "ok": False, "error": str(exc), "useful": False})

    return {
        "attempt_count": len(attempts),
        "verified_count": len(verified),
        "attempts": attempts[-300:],
        "verified_downloads": verified,
    }


def discover_hidden_api(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = _clean(payload.get("tender_id") or payload.get("tenderId") or payload.get("id") or "155559")
    support_document_id = _clean(
        payload.get("supportDocumentID")
        or payload.get("support_document_id")
        or payload.get("document_guid")
        or payload.get("guid")
        or ""
    )
    output_dir = _clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR)

    start_id = int(payload.get("start_document_id") or payload.get("start_id") or 1)
    end_id = int(payload.get("end_document_id") or payload.get("end_id") or 250)

    details = fetch_tender_details(tender_id)
    endpoint_results = probe_metadata_endpoints(tender_id, support_document_id)
    useful_endpoints = [r for r in endpoint_results if r.get("useful")]

    range_probe = probe_downloadspec_range(
        tender_id=tender_id,
        start_id=start_id,
        end_id=end_id,
        output_dir=output_dir,
        save_verified=bool(payload.get("save_verified", True)),
    )

    result = {
        "status": "ok" if (useful_endpoints or range_probe.get("verified_count")) else "no_hidden_document_api_found_yet",
        "service_version": SERVICE_VERSION,
        "discovered_at": _now(),
        "tender_id": tender_id,
        "support_document_id": support_document_id,
        "details_ok": details.get("ok", False),
        "details": details,
        "useful_endpoint_count": len(useful_endpoints),
        "useful_endpoints": useful_endpoints,
        "downloadspec_probe": range_probe,
        "safe_to_process": bool(range_probe.get("verified_count")),
        "notes": [
            "TenderDetails returns JSON and may not include document metadata.",
            "DownloadSpec is confirmed as a real eTenders action pattern.",
            "If verified downloads are unrelated, narrow documentId range after inspecting filenames.",
            "Next step after finding the correct documentId is wiring replay-download into acquisition.",
        ],
    }

    log_path = Path(output_dir) / f"ETENDERS_{tender_id}__v50_9_6_hidden_api_discovery.json"
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result["discovery_log"] = str(log_path)
    except Exception as exc:
        result["discovery_log_error"] = str(exc)

    return result


def replay_download(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = _clean(payload.get("tender_id") or "UNKNOWN")
    document_id = payload.get("document_id")
    url = _clean(payload.get("url") or "")
    output_dir = Path(_clean(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    filename_hint = _clean(payload.get("filename") or "")

    if not url:
        if document_id is None:
            return {
                "status": "error",
                "service_version": SERVICE_VERSION,
                "message": "Provide either url or document_id.",
                "safe_to_process": False,
            }
        url = f"{BASE}/Home/DownloadSpec?documentId={int(document_id)}&source=sharepoint"

    try:
        r = requests.get(url, headers=_headers({"Accept": "*/*"}), timeout=30, allow_redirects=True)
        summary = _response_summary(r, url)
        is_download = _is_download_response(r)

        if not is_download:
            return {
                "status": "not_verified_download",
                "service_version": SERVICE_VERSION,
                "url": url,
                "response": summary,
                "safe_to_process": False,
            }

        filename = _content_disposition_filename(r.headers.get("content-disposition", "")) or filename_hint
        if not filename:
            ext = mimetypes.guess_extension((r.headers.get("content-type") or "").split(";")[0].strip()) or ".bin"
            filename = f"document_{document_id or 'url'}{ext}"

        safe = _safe_filename(filename)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"ETENDERS_{tender_id}__{safe}"
        path.write_bytes(r.content)

        return {
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "downloaded_at": _now(),
            "url": url,
            "filename": filename,
            "saved_path": str(path),
            "saved_size": path.stat().st_size,
            "response": summary,
            "safe_to_process": path.stat().st_size > 0,
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "url": url,
            "error": str(exc),
            "safe_to_process": False,
        }


def get_v50_9_6_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "tenderdetails_json_fetch",
            "hidden_metadata_endpoint_probe",
            "document_like_json_deep_scan",
            "downloadspec_range_probe",
            "content_disposition_filename_extract",
            "verified_binary_download_save",
            "download_replay",
            "discovery_log_generation",
        ],
    }
