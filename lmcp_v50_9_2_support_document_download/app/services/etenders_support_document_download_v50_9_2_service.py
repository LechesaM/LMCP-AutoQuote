"""
LMCP V50.9.2 - eTenders SupportDocument Direct Download Probe

Purpose:
- V50.8.6 found supportDocument metadata inside PaginatedTenderOpportunities rows.
- V50.9 direct guesses returned 404.
- V50.9.1 confirmed TenderDetails only returns summary, not documents.
- This engine targets supportDocumentID directly and probes broader ASP.NET-style
  eTenders action patterns.

Route:
    GET  /v50-9-2-support-document-download/status
    POST /v50-9-2-support-document-download/probe
    POST /v50-9-2-support-document-download/download

Drop-in:
    app/services/etenders_support_document_download_v50_9_2_service.py
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests


SERVICE_VERSION = "V50.9.2_ETENDERS_SUPPORT_DOCUMENT_DOWNLOAD"

ETENDERS_BASE = "https://www.etenders.gov.za"
REFERER = "https://www.etenders.gov.za/Home/opportunities"
DEFAULT_OUTPUT_DIR = "runtime/playwright/downloads"

GOOD_CONTENT_HINTS = (
    "application/pdf",
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats",
    "application/vnd.ms-excel",
    "application/octet-stream",
)

BAD_CONTENT_HINTS = (
    "text/html",
    "application/json",
    "text/plain",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(filename: str, fallback: str = "etenders_support_document.pdf") -> str:
    name = _clean(filename) or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name).strip(". ")
    if not name:
        name = fallback
    if len(name) > 180:
        stem = Path(name).stem[:150]
        suffix = Path(name).suffix or ".pdf"
        name = f"{stem}{suffix}"
    return name


def _headers(accept: str = "application/pdf,application/zip,application/octet-stream,*/*") -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": accept,
        "Referer": REFERER,
        "X-Requested-With": "XMLHttpRequest",
    }


def _looks_like_download(content_type: str, content_disposition: str, first_bytes: bytes) -> Dict[str, Any]:
    ctype = (content_type or "").lower()
    cdisp = (content_disposition or "").lower()

    byte_pdf = first_bytes.startswith(b"%PDF")
    byte_zip = first_bytes.startswith(b"PK")
    byte_doc = first_bytes.startswith(b"\xd0\xcf\x11\xe0")
    good_ctype = any(h in ctype for h in GOOD_CONTENT_HINTS)
    bad_ctype = any(h in ctype for h in BAD_CONTENT_HINTS)
    attachment = "attachment" in cdisp or "filename" in cdisp

    verified = bool(byte_pdf or byte_zip or byte_doc or attachment or (good_ctype and not bad_ctype))

    if byte_pdf:
        detected = "pdf"
    elif byte_zip:
        detected = "zip_or_office_openxml"
    elif byte_doc:
        detected = "legacy_office"
    elif attachment:
        detected = "attachment_header"
    elif good_ctype and not bad_ctype:
        detected = "content_type"
    else:
        detected = "unknown_or_html"

    return {
        "verified": verified,
        "detected_type": detected,
        "byte_pdf": byte_pdf,
        "byte_zip": byte_zip,
        "byte_doc": byte_doc,
        "good_content_type": good_ctype,
        "bad_content_type": bad_ctype,
        "attachment_header": attachment,
    }


def _extract_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    support_document_id = (
        payload.get("supportDocumentID")
        or payload.get("support_document_id")
        or payload.get("document_guid")
        or payload.get("documentGuid")
        or payload.get("guid")
    )

    tender_id = (
        payload.get("tender_id")
        or payload.get("tendersID")
        or payload.get("tenderId")
        or payload.get("id")
    )

    filename = (
        payload.get("filename")
        or payload.get("fileName")
        or payload.get("document_name")
        or payload.get("supportDocumentName")
    )

    extension = payload.get("extension") or Path(str(filename or "")).suffix or ".pdf"

    return {
        "support_document_id": _clean(support_document_id),
        "tender_id": _clean(tender_id),
        "filename": _clean(filename),
        "extension": _clean(extension),
    }


def build_support_document_candidates(payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    payload = payload or {}
    data = _extract_payload(payload)

    sid = data["support_document_id"]
    tid = data["tender_id"]
    fname = data["filename"]

    candidates: List[Dict[str, Any]] = []
    seen = set()

    # Broad ASP.NET MVC action guesses, including likely support document action names.
    endpoints = [
        "/Home/DownloadSupportDocument",
        "/home/DownloadSupportDocument",
        "/Home/DownloadTenderSupportDocument",
        "/home/DownloadTenderSupportDocument",
        "/Home/GetSupportDocument",
        "/home/GetSupportDocument",
        "/Home/DownloadDocument",
        "/home/DownloadDocument",
        "/Home/GetDocument",
        "/home/GetDocument",
        "/Home/DownloadFile",
        "/home/DownloadFile",
        "/Home/GetFile",
        "/home/GetFile",
        "/Home/DownloadTenderDocument",
        "/home/DownloadTenderDocument",
        "/Home/DownloadSpec",
        "/home/DownloadSpec",
        "/Home/Download",
        "/home/Download",
        "/Home/GetTenderDocuments",
        "/home/GetTenderDocuments",
    ]

    def add(endpoint: str, params: Dict[str, Any], reason: str) -> None:
        clean_params = {k: v for k, v in params.items() if v not in ("", None)}
        if not clean_params:
            return
        url = f"{ETENDERS_BASE}{endpoint}?{urlencode(clean_params)}"
        if url in seen:
            return
        seen.add(url)
        candidates.append({"url": url, "endpoint": endpoint, "params": clean_params, "reason": reason})

    id_keys = [
        "supportDocumentID",
        "supportDocumentId",
        "supportdocumentid",
        "SupportDocumentID",
        "documentGuid",
        "documentGUID",
        "documentId",
        "documentID",
        "fileId",
        "id",
    ]

    for endpoint in endpoints:
        if sid:
            for key in id_keys:
                add(endpoint, {key: sid}, f"{endpoint}:{key}=support_id")
                add(endpoint, {key: sid, "source": "sharepoint"}, f"{endpoint}:{key}=support_id+source")
                if fname:
                    add(endpoint, {key: sid, "fileName": fname}, f"{endpoint}:{key}=support_id+fileName")
                    add(endpoint, {key: sid, "filename": fname}, f"{endpoint}:{key}=support_id+filename")
                    add(endpoint, {key: sid, "fileName": fname, "source": "sharepoint"}, f"{endpoint}:{key}=support_id+fileName+source")

        if tid and fname:
            for tid_key in ("tendersID", "tenderId", "tenderID", "id", "documentId"):
                add(endpoint, {tid_key: tid, "fileName": fname}, f"{endpoint}:{tid_key}+fileName")
                add(endpoint, {tid_key: tid, "filename": fname}, f"{endpoint}:{tid_key}+filename")
                add(endpoint, {tid_key: tid, "fileName": fname, "source": "sharepoint"}, f"{endpoint}:{tid_key}+fileName+source")

        if sid and tid and fname:
            add(endpoint, {"supportDocumentID": sid, "tendersID": tid, "fileName": fname}, f"{endpoint}:support+tender+file")
            add(endpoint, {"supportDocumentID": sid, "tenderId": tid, "fileName": fname}, f"{endpoint}:support+tenderId+file")
            add(endpoint, {"documentGuid": sid, "tendersID": tid, "fileName": fname}, f"{endpoint}:guid+tender+file")

    # Non-/Home API-ish candidates.
    api_endpoints = [
        "/api/Tender/DownloadSupportDocument",
        "/api/Tenders/DownloadSupportDocument",
        "/api/TenderDocuments/Download",
        "/api/Documents/Download",
    ]

    for endpoint in api_endpoints:
        if sid:
            add(endpoint, {"supportDocumentID": sid}, f"{endpoint}:support_id")
            add(endpoint, {"id": sid}, f"{endpoint}:id")
        if sid and tid:
            add(endpoint, {"supportDocumentID": sid, "tendersID": tid}, f"{endpoint}:support+tender")
        if sid and fname:
            add(endpoint, {"supportDocumentID": sid, "fileName": fname}, f"{endpoint}:support+fileName")

    return candidates


def _probe_candidate(url: str, save_path: Optional[Path] = None, timeout: int = 30) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "url": url,
        "ok": False,
        "verified_download": False,
        "status_code": 0,
        "final_url": url,
        "content_type": "",
        "content_disposition": "",
        "content_length": 0,
        "saved_path": "",
        "error": "",
        "validation": {},
        "body_preview": "",
    }

    try:
        with requests.get(url, headers=_headers(), timeout=timeout, stream=True, allow_redirects=True) as resp:
            result["status_code"] = resp.status_code
            result["final_url"] = resp.url
            result["content_type"] = resp.headers.get("content-type", "")
            result["content_disposition"] = resp.headers.get("content-disposition", "")

            chunks: List[bytes] = []
            first = b""
            total = 0

            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not first:
                    first = chunk[:512]
                if total < 4096:
                    chunks.append(chunk)
                else:
                    if save_path is not None:
                        chunks.append(chunk)
                total += len(chunk)
                if total > 150 * 1024 * 1024:
                    result["error"] = "download_too_large_over_150mb"
                    return result

            result["content_length"] = total
            result["validation"] = _looks_like_download(result["content_type"], result["content_disposition"], first)

            if first and not result["validation"].get("verified"):
                try:
                    result["body_preview"] = first.decode("utf-8", errors="replace")[:500]
                except Exception:
                    result["body_preview"] = repr(first[:200])

            if not (200 <= resp.status_code < 400):
                result["error"] = f"http_status_{resp.status_code}"
                return result

            if not result["validation"].get("verified"):
                result["error"] = f"not_verified_download:{result['content_type']}"
                return result

            if save_path is not None:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with save_path.open("wb") as f:
                    for chunk in chunks:
                        f.write(chunk)

                result["saved_path"] = str(save_path)

            result["ok"] = True
            result["verified_download"] = True
            return result

    except Exception as exc:
        result["error"] = str(exc)
        return result


def probe_support_document(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    data = _extract_payload(payload)
    candidates = build_support_document_candidates(payload)

    attempts: List[Dict[str, Any]] = []
    useful_attempts: List[Dict[str, Any]] = []

    max_attempts = int(payload.get("max_attempts") or 160)

    for candidate in candidates[:max_attempts]:
        attempt = _probe_candidate(candidate["url"], save_path=None)
        attempt["candidate_reason"] = candidate["reason"]
        attempt["params"] = candidate.get("params", {})
        attempts.append(attempt)

        if attempt.get("status_code") not in (0, 404) or attempt.get("content_type") or attempt.get("body_preview"):
            useful_attempts.append(attempt)

        if attempt.get("verified_download"):
            useful_attempts.append(attempt)
            break

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "probed_at": _now(),
        "input": data,
        "candidate_count": len(candidates),
        "attempt_count": len(attempts),
        "verified_found": any(a.get("verified_download") for a in attempts),
        "first_verified": next((a for a in attempts if a.get("verified_download")), None),
        "useful_attempt_count": len(useful_attempts),
        "useful_attempts": useful_attempts[:50],
        "attempts": attempts[:80],
        "notes": [
            "This probes supportDocumentID endpoint/action patterns.",
            "If useful_attempts show JSON/HTML with route hints, use that to build the next exact downloader.",
        ],
    }


def download_support_document(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    data = _extract_payload(payload)
    filename = data["filename"] or f"{data['support_document_id']}.pdf"
    safe_name = _safe_filename(filename)
    output_dir = Path(str(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))
    prefix = f"ETENDERS_{data['tender_id']}__" if data["tender_id"] else "ETENDERS__"
    output_path = output_dir / f"{prefix}{safe_name}"

    candidates = build_support_document_candidates(payload)
    attempts: List[Dict[str, Any]] = []
    max_attempts = int(payload.get("max_attempts") or 220)

    for candidate in candidates[:max_attempts]:
        attempt = _probe_candidate(candidate["url"], save_path=output_path)
        attempt["candidate_reason"] = candidate["reason"]
        attempt["params"] = candidate.get("params", {})
        attempts.append(attempt)

        if attempt.get("verified_download"):
            return {
                "status": "ok",
                "service_version": SERVICE_VERSION,
                "downloaded_at": _now(),
                "input": data,
                "saved_path": attempt.get("saved_path"),
                "winning_url": attempt.get("url"),
                "winning_reason": candidate["reason"],
                "content_type": attempt.get("content_type"),
                "content_length": attempt.get("content_length"),
                "attempt_count": len(attempts),
                "attempts": attempts,
                "safe_to_process": True,
                "notes": [
                    "Support document downloaded and verified.",
                    "Use saved_path as RFQ source document.",
                ],
            }

    return {
        "status": "error",
        "service_version": SERVICE_VERSION,
        "downloaded_at": _now(),
        "message": "No supportDocumentID candidate produced a verified download.",
        "input": data,
        "candidate_count": len(candidates),
        "attempt_count": len(attempts),
        "useful_attempts": [
            a for a in attempts
            if a.get("status_code") not in (0, 404) or a.get("content_type") or a.get("body_preview")
        ][:80],
        "attempts": attempts[:120],
        "safe_to_process": False,
        "notes": [
            "SupportDocument metadata is correct, but exact download route is still unresolved.",
            "Inspect useful_attempts for non-404 patterns.",
            "If all are 404, next fallback is Playwright click on row supportDocument link using structured row id.",
        ],
    }


def get_v50_9_2_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "support_document_id_probe",
            "broad_aspnet_action_pattern_testing",
            "support_document_direct_download",
            "verified_pdf_zip_office_download",
            "useful_attempt_extraction",
            "safe_runtime_storage",
        ],
    }
