"""
LMCP V50.9 - eTenders Document Auto-Download Engine
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import requests


SERVICE_VERSION = "V50.9_ETENDERS_DOCUMENT_AUTO_DOWNLOAD"

ETENDERS_BASE = "https://www.etenders.gov.za"
ETENDERS_REFERER = "https://www.etenders.gov.za/Home/opportunities"
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


def _safe_filename(filename: str, fallback: str = "etenders_document.pdf") -> str:
    name = str(filename or "").strip() or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
    if not name:
        name = fallback
    if len(name) > 180:
        stem = Path(name).stem[:150]
        suffix = Path(name).suffix or ".pdf"
        name = f"{stem}{suffix}"
    return name


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


def _candidate_urls(tender_id: Optional[Any], document_guid: Optional[str], filename: Optional[str]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen = set()

    endpoints = [
        "/Home/DownloadSpec",
        "/Home/DownloadTenderDocument",
        "/Home/DownloadFile",
        "/Home/DownloadDocument",
    ]

    def add(url: str, reason: str) -> None:
        if url and url not in seen:
            seen.add(url)
            candidates.append({"url": url, "reason": reason})

    tid = str(tender_id or "").strip()
    guid = str(document_guid or "").strip()
    fname = str(filename or "").strip()

    if guid:
        for endpoint in endpoints:
            for key in ("documentGuid", "documentId", "id"):
                qs = urlencode({key: guid, "source": "sharepoint"})
                add(f"{ETENDERS_BASE}{endpoint}?{qs}", f"{endpoint}:{key}=guid")

    if tid:
        for endpoint in endpoints:
            for key in ("documentId", "id"):
                qs = urlencode({key: tid, "source": "sharepoint"})
                add(f"{ETENDERS_BASE}{endpoint}?{qs}", f"{endpoint}:{key}=tender_id")

    if tid and fname:
        for endpoint in endpoints:
            qs = urlencode({"documentId": tid, "fileName": fname, "source": "sharepoint"})
            add(f"{ETENDERS_BASE}{endpoint}?{qs}", f"{endpoint}:tender_id+filename")

    if guid and fname:
        for endpoint in endpoints:
            qs = urlencode({"documentGuid": guid, "fileName": fname, "source": "sharepoint"})
            add(f"{ETENDERS_BASE}{endpoint}?{qs}", f"{endpoint}:guid+filename")

    if tid:
        add(f"{ETENDERS_BASE}/home/tenderdetails?id={quote(tid)}", "detail_lowercase")
        add(f"{ETENDERS_BASE}/Home/TenderDetails?id={quote(tid)}", "detail_pascalcase")

    return candidates


def _download_url(url: str, output_path: Path, timeout: int = 35) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": "application/pdf,application/zip,application/octet-stream,*/*",
        "Referer": ETENDERS_REFERER,
    }

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
    }

    try:
        with requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True) as response:
            result["status_code"] = response.status_code
            result["final_url"] = response.url
            result["content_type"] = response.headers.get("content-type", "")
            result["content_disposition"] = response.headers.get("content-disposition", "")

            chunks: List[bytes] = []
            total = 0
            first_bytes = b""

            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not first_bytes:
                    first_bytes = chunk[:512]
                chunks.append(chunk)
                total += len(chunk)
                if total > 150 * 1024 * 1024:
                    result["error"] = "download_too_large_over_150mb"
                    return result

            result["content_length"] = total
            validation = _looks_like_download(result["content_type"], result["content_disposition"], first_bytes)
            result["validation"] = validation

            if not (200 <= response.status_code < 400):
                result["error"] = f"http_status_{response.status_code}"
                return result

            if not validation["verified"]:
                result["error"] = f"not_verified_download:{result['content_type']}"
                return result

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as f:
                for chunk in chunks:
                    f.write(chunk)

            result["ok"] = True
            result["verified_download"] = True
            result["saved_path"] = str(output_path)
            return result

    except Exception as exc:
        result["error"] = str(exc)
        return result


def download_etenders_document(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    tender_id = payload.get("tender_id") or payload.get("tenderId") or payload.get("id")
    document_guid = payload.get("document_guid") or payload.get("documentGuid") or payload.get("guid")
    filename = payload.get("filename") or payload.get("fileName") or payload.get("document_name")
    output_dir = Path(str(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))

    safe_name = _safe_filename(str(filename or f"tender_{tender_id or document_guid}_document.pdf"))
    prefix = f"ETENDERS_{tender_id}__" if tender_id else "ETENDERS__"
    output_path = output_dir / f"{prefix}{safe_name}"

    candidates = _candidate_urls(tender_id, document_guid, filename)
    attempts: List[Dict[str, Any]] = []

    for candidate in candidates:
        attempt = _download_url(candidate["url"], output_path)
        attempt["candidate_reason"] = candidate["reason"]
        attempts.append(attempt)

        if attempt.get("verified_download"):
            return {
                "status": "ok",
                "service_version": SERVICE_VERSION,
                "downloaded_at": _now(),
                "tender_id": tender_id,
                "document_guid": document_guid,
                "filename": filename,
                "safe_filename": safe_name,
                "saved_path": attempt.get("saved_path"),
                "content_type": attempt.get("content_type"),
                "content_length": attempt.get("content_length"),
                "winning_url": attempt.get("url"),
                "winning_reason": candidate["reason"],
                "attempt_count": len(attempts),
                "attempts": attempts,
                "safe_to_process": True,
                "notes": [
                    "Document downloaded and verified.",
                    "Use saved_path as input for RFQ parsing / SBD / quote workflow.",
                ],
            }

    return {
        "status": "error",
        "service_version": SERVICE_VERSION,
        "downloaded_at": _now(),
        "message": "No candidate URL produced a verified downloadable document.",
        "tender_id": tender_id,
        "document_guid": document_guid,
        "filename": filename,
        "safe_filename": safe_name,
        "candidate_count": len(candidates),
        "attempt_count": len(attempts),
        "attempts": attempts,
        "safe_to_process": False,
        "notes": [
            "The document may require a different eTenders endpoint pattern.",
            "Inspect attempts for HTTP status, content_type, and final_url.",
            "If attempts return HTML, the next step is a detail-page parser or Playwright-assisted fallback.",
        ],
    }


def get_v50_9_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "document_guid_download_patterns",
            "tender_id_download_patterns",
            "filename_aware_download_patterns",
            "pdf_zip_office_validation",
            "safe_runtime_download_storage",
            "download_attempt_audit_trail",
        ],
    }
