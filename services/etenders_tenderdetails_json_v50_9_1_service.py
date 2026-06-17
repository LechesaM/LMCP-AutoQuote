"""
LMCP V50.9.1 - eTenders TenderDetails JSON Parser + Download Bridge

Purpose:
- V50.9 proved direct document GUID patterns return 404.
- TenderDetails endpoint returns JSON for a tender id.
- This engine:
    1. calls /home/tenderdetails?id=<tender_id>
    2. parses JSON deeply
    3. extracts supportDocument / file metadata / GUIDs / filenames
    4. builds improved candidate download URLs
    5. probes and downloads the first verified document

Routes:
    GET  /v50-9-1-tenderdetails-json/status
    POST /v50-9-1-tenderdetails-json/inspect
    POST /v50-9-1-tenderdetails-json/download

Drop-in:
    app/services/etenders_tenderdetails_json_v50_9_1_service.py
"""

from __future__ import annotations

import os
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote

import requests


SERVICE_VERSION = "V50.9.1_ETENDERS_TENDERDETAILS_JSON_PARSER"

ETENDERS_BASE = "https://www.etenders.gov.za"
DETAIL_ENDPOINTS = [
    "https://www.etenders.gov.za/home/tenderdetails",
    "https://www.etenders.gov.za/Home/TenderDetails",
]
REFERER = "https://www.etenders.gov.za/Home/opportunities"

DEFAULT_OUTPUT_DIR = str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "playwright" / "downloads")

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
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_filename(filename: str, fallback: str = "etenders_document.pdf") -> str:
    name = _clean(filename) or fallback
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


def _headers(accept: str = "application/json, text/javascript, */*; q=0.01") -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": accept,
        "Referer": REFERER,
        "X-Requested-With": "XMLHttpRequest",
    }


def _fetch_tenderdetails(tender_id: Any) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []

    for base_url in DETAIL_ENDPOINTS:
        url = f"{base_url}?{urlencode({'id': str(tender_id)})}"
        item: Dict[str, Any] = {
            "url": url,
            "ok": False,
            "status_code": 0,
            "content_type": "",
            "data": None,
            "text_preview": "",
            "error": "",
        }
        try:
            resp = requests.get(url, headers=_headers(), timeout=25)
            item["status_code"] = resp.status_code
            item["content_type"] = resp.headers.get("content-type", "")
            item["text_preview"] = resp.text[:500]

            if 200 <= resp.status_code < 400 and "json" in item["content_type"].lower():
                item["data"] = resp.json()
                item["ok"] = True
                attempts.append(item)
                return {
                    "ok": True,
                    "winning_url": url,
                    "attempts": attempts,
                    "data": item["data"],
                }

            # Some eTenders endpoints return JSON without json content-type.
            if 200 <= resp.status_code < 400:
                try:
                    item["data"] = resp.json()
                    item["ok"] = True
                    attempts.append(item)
                    return {
                        "ok": True,
                        "winning_url": url,
                        "attempts": attempts,
                        "data": item["data"],
                    }
                except Exception:
                    pass

            item["error"] = f"not_json_or_bad_status:{resp.status_code}:{item['content_type']}"
        except Exception as exc:
            item["error"] = str(exc)

        attempts.append(item)

    return {
        "ok": False,
        "winning_url": "",
        "attempts": attempts,
        "data": None,
    }


def _walk(value: Any, path: str = "") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        out.append({"path": path or "$", "type": "dict", "value": value})
        for k, v in value.items():
            out.extend(_walk(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(value, list):
        out.append({"path": path or "$", "type": "list", "value": value})
        for i, v in enumerate(value):
            out.extend(_walk(v, f"{path}[{i}]"))
    return out


def _extract_guid(text: str) -> List[str]:
    pattern = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    return sorted(set(g.lower() for g in re.findall(pattern, text or "")))


def _extract_documents_from_details(data: Any) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    seen = set()

    def add_doc(raw: Dict[str, Any], source_path: str) -> None:
        blob = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        guids = _extract_guid(blob)

        filename = (
            raw.get("fileName")
            or raw.get("filename")
            or raw.get("documentName")
            or raw.get("name")
            or raw.get("supportDocumentName")
            or raw.get("originalFileName")
            or ""
        )

        support_id = (
            raw.get("supportDocumentID")
            or raw.get("supportDocumentId")
            or raw.get("documentID")
            or raw.get("documentId")
            or raw.get("id")
            or ""
        )

        tender_id = raw.get("tendersID") or raw.get("tenderId") or raw.get("tender_id") or ""

        extension = raw.get("extension") or Path(str(filename)).suffix or ""

        key = f"{filename}|{support_id}|{'|'.join(guids)}|{source_path}"
        if key in seen:
            return
        seen.add(key)

        if filename or support_id or guids:
            docs.append({
                "source_path": source_path,
                "filename": filename,
                "safe_filename": _safe_filename(str(filename or f'{support_id}.pdf')),
                "support_document_id": support_id,
                "tender_id": tender_id,
                "extension": extension,
                "guids": guids,
                "raw": raw,
            })

    for node in _walk(data):
        value = node.get("value")
        path = node.get("path", "")

        if isinstance(value, dict):
            low_keys = " ".join(str(k).lower() for k in value.keys())
            blob = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()

            looks_doc = (
                "supportdocument" in low_keys
                or "filename" in low_keys
                or "document" in low_keys
                or ".pdf" in blob
                or ".doc" in blob
                or ".xls" in blob
                or ".zip" in blob
            )

            if looks_doc:
                add_doc(value, path)

        elif isinstance(value, list):
            # Add dict children are handled by recursion.
            pass

    return docs


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

    return {
        "verified": verified,
        "byte_pdf": byte_pdf,
        "byte_zip": byte_zip,
        "byte_doc": byte_doc,
        "good_content_type": good_ctype,
        "bad_content_type": bad_ctype,
        "attachment_header": attachment,
    }


def _build_download_candidates(tender_id: Any, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()

    endpoints = [
        "/Home/DownloadSupportDocument",
        "/home/DownloadSupportDocument",
        "/Home/DownloadTenderDocument",
        "/home/DownloadTenderDocument",
        "/Home/DownloadDocument",
        "/home/DownloadDocument",
        "/Home/DownloadFile",
        "/home/DownloadFile",
        "/Home/DownloadSpec",
        "/home/DownloadSpec",
        "/Home/GetDocument",
        "/home/GetDocument",
        "/Home/GetFile",
        "/home/GetFile",
    ]

    filename = str(doc.get("filename") or "")
    support_id = str(doc.get("support_document_id") or "")
    doc_tender_id = str(doc.get("tender_id") or tender_id or "")
    guids = [str(g) for g in (doc.get("guids") or [])]

    def add(path: str, params: Dict[str, Any], reason: str) -> None:
        clean_params = {k: v for k, v in params.items() if v not in (None, "")}
        url = f"{ETENDERS_BASE}{path}?{urlencode(clean_params)}"
        if url not in seen:
            seen.add(url)
            out.append({"url": url, "reason": reason, "params": clean_params})

    for endpoint in endpoints:
        if support_id:
            for key in ("supportDocumentID", "supportDocumentId", "documentId", "documentID", "id"):
                add(endpoint, {key: support_id, "source": "sharepoint"}, f"{endpoint}:{key}=support_id")

        for guid in guids:
            for key in ("supportDocumentID", "supportDocumentId", "documentGuid", "documentId", "id"):
                add(endpoint, {key: guid, "source": "sharepoint"}, f"{endpoint}:{key}=guid")

        if doc_tender_id and filename:
            add(endpoint, {"tenderId": doc_tender_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:tenderId+fileName")
            add(endpoint, {"tendersID": doc_tender_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:tendersID+fileName")
            add(endpoint, {"documentId": doc_tender_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:documentId+fileName")

        if support_id and filename:
            add(endpoint, {"supportDocumentID": support_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:support_id+fileName")
            add(endpoint, {"documentId": support_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:document_id+fileName")

        for guid in guids:
            if filename:
                add(endpoint, {"supportDocumentID": guid, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:guid+fileName")
                add(endpoint, {"documentGuid": guid, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:documentGuid+fileName")

    # Some ASP.NET actions use only fileName and tendersID.
    for endpoint in endpoints:
        if filename:
            add(endpoint, {"fileName": filename, "tendersID": doc_tender_id}, f"{endpoint}:fileName+tendersID")
            add(endpoint, {"fileName": filename, "tenderId": doc_tender_id}, f"{endpoint}:fileName+tenderId")

    return out


def _download_candidate(url: str, output_path: Path, timeout: int = 35) -> Dict[str, Any]:
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

    headers = _headers("application/pdf,application/zip,application/octet-stream,*/*")

    try:
        with requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True) as resp:
            result["status_code"] = resp.status_code
            result["final_url"] = resp.url
            result["content_type"] = resp.headers.get("content-type", "")
            result["content_disposition"] = resp.headers.get("content-disposition", "")

            chunks: List[bytes] = []
            total = 0
            first = b""

            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not first:
                    first = chunk[:512]
                chunks.append(chunk)
                total += len(chunk)
                if total > 150 * 1024 * 1024:
                    result["error"] = "download_too_large_over_150mb"
                    return result

            result["content_length"] = total
            result["validation"] = _looks_like_download(result["content_type"], result["content_disposition"], first)

            if not (200 <= resp.status_code < 400):
                result["error"] = f"http_status_{resp.status_code}"
                return result

            if not result["validation"].get("verified"):
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


def inspect_tenderdetails_json(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = payload.get("tender_id") or payload.get("tenderId") or payload.get("id")

    fetched = _fetch_tenderdetails(tender_id)
    docs = _extract_documents_from_details(fetched.get("data")) if fetched.get("ok") else []

    return {
        "status": "ok" if fetched.get("ok") else "error",
        "service_version": SERVICE_VERSION,
        "inspected_at": _now(),
        "tender_id": tender_id,
        "details_ok": fetched.get("ok"),
        "details_url": fetched.get("winning_url"),
        "details_attempts": fetched.get("attempts"),
        "document_count": len(docs),
        "documents": docs,
        "raw_details": fetched.get("data"),
        "notes": [
            "This endpoint inspects TenderDetails JSON and exposes document metadata.",
            "Use /download to attempt verified download from extracted document metadata.",
        ],
    }


def download_from_tenderdetails_json(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    tender_id = payload.get("tender_id") or payload.get("tenderId") or payload.get("id")
    preferred_guid = str(payload.get("document_guid") or payload.get("documentGuid") or payload.get("guid") or "").lower()
    preferred_filename = _clean(payload.get("filename") or payload.get("fileName") or "")
    output_dir = Path(str(payload.get("output_dir") or DEFAULT_OUTPUT_DIR))

    inspected = inspect_tenderdetails_json({"tender_id": tender_id})

    if inspected.get("status") != "ok":
        return {
            "status": "error",
            "service_version": SERVICE_VERSION,
            "message": "Could not fetch TenderDetails JSON.",
            "inspection": inspected,
            "safe_to_process": False,
        }

    docs = inspected.get("documents") or []

    def doc_score(doc: Dict[str, Any]) -> int:
        score = 0
        fname = _clean(doc.get("filename"))
        guids = [str(g).lower() for g in (doc.get("guids") or [])]
        if preferred_guid and preferred_guid in guids:
            score += 100
        if preferred_filename and preferred_filename.lower() == fname.lower():
            score += 80
        if preferred_filename and preferred_filename.lower() in fname.lower():
            score += 50
        if fname.lower().endswith(".pdf"):
            score += 10
        return score

    docs = sorted(docs, key=doc_score, reverse=True)

    attempts: List[Dict[str, Any]] = []

    for doc in docs:
        safe_name = _safe_filename(doc.get("filename") or preferred_filename or f"tender_{tender_id}_document.pdf")
        output_path = output_dir / f"ETENDERS_{tender_id}__{safe_name}"
        candidates = _build_download_candidates(tender_id, doc)

        for candidate in candidates:
            attempt = _download_candidate(candidate["url"], output_path)
            attempt["candidate_reason"] = candidate["reason"]
            attempt["document"] = {
                "filename": doc.get("filename"),
                "support_document_id": doc.get("support_document_id"),
                "tender_id": doc.get("tender_id"),
                "guids": doc.get("guids"),
                "source_path": doc.get("source_path"),
            }
            attempts.append(attempt)

            if attempt.get("verified_download"):
                return {
                    "status": "ok",
                    "service_version": SERVICE_VERSION,
                    "downloaded_at": _now(),
                    "tender_id": tender_id,
                    "selected_document": doc,
                    "saved_path": attempt.get("saved_path"),
                    "content_type": attempt.get("content_type"),
                    "content_length": attempt.get("content_length"),
                    "winning_url": attempt.get("url"),
                    "winning_reason": candidate["reason"],
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                    "safe_to_process": True,
                    "notes": [
                        "Document downloaded using TenderDetails JSON metadata.",
                        "Use saved_path for the next RFQ parsing/pricing workflow.",
                    ],
                }

    return {
        "status": "error",
        "service_version": SERVICE_VERSION,
        "downloaded_at": _now(),
        "message": "TenderDetails JSON was parsed but no candidate produced a verified download.",
        "tender_id": tender_id,
        "document_count": len(docs),
        "documents": docs,
        "attempt_count": len(attempts),
        "attempts": attempts[:120],
        "safe_to_process": False,
        "notes": [
            "Detail JSON metadata extraction worked.",
            "The remaining issue is the exact eTenders file-download action pattern.",
            "Inspect attempts for non-404 or non-json responses to identify the correct action.",
        ],
    }


def get_v50_9_1_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "capabilities": [
            "tenderdetails_json_fetch",
            "deep_document_metadata_extraction",
            "support_document_guid_extraction",
            "filename_extraction",
            "improved_download_candidate_generation",
            "verified_document_download",
        ],
    }
