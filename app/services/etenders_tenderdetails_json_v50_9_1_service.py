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

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, quote, parse_qsl, urljoin, urlparse

import requests


SERVICE_VERSION = "V50.9.1_ETENDERS_TENDERDETAILS_JSON_PARSER"

ETENDERS_BASE = "https://www.etenders.gov.za"
DETAIL_ENDPOINTS = [
    "https://www.etenders.gov.za/home/tenderdetails",
    "https://www.etenders.gov.za/Home/TenderDetails",
]
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
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _snippet(value: Any, limit: int = 220) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _unique_compact(values: List[Any], limit: int = 40) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = _clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _json_value_looks_like_filename(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    lowered = text.lower()
    return bool(re.search(r"\.(pdf|zip|docx?|xlsx?|xls|csv|txt|rtf|msg|eml)$", lowered) or re.search(r"[\w\-]+\.(pdf|zip|docx?|xlsx?|xls|csv|txt|rtf|msg|eml)(?:\?|$)", lowered))


def _json_value_looks_like_url(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    return bool(re.match(r"^https?://", text, flags=re.I) or text.startswith("/Home/") or text.startswith("Home/") or text.startswith("/"))


def _json_value_looks_like_doc_id(name: str, value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    if not re.search(r"\d", text) and not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text):
        return False
    lower_name = _clean(name).lower()
    if any(token in lower_name for token in ("document", "support", "file", "doc", "attachment", "blob", "download")):
        return True
    if lower_name == "id" and len(text) >= 3:
        return True
    return False


def _json_value_is_filename_only(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    if text.startswith(("http://", "https://", "/")):
        return False
    if "/" in text or "\\" in text:
        return False
    return bool(re.search(r"\.(pdf|zip|docx?|xlsx?|xls|csv|txt|rtf|msg|eml)$", text, flags=re.I))


def _json_resolve_explicit_value(value: Any, detail_page_url: str) -> str:
    text = _clean(value)
    if not text or _json_value_is_filename_only(text):
        return ""
    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        if parsed.netloc and "etenders.gov.za" not in parsed.netloc.lower():
            return ""
        return text
    if text.startswith("/"):
        return urljoin(ETENDERS_BASE, text)
    if text.startswith("Home/") or text.startswith("home/"):
        return urljoin(ETENDERS_BASE + "/", text)
    if any(sep in text for sep in ("/", "\\")):
        return urljoin(detail_page_url or ETENDERS_BASE, text)
    return ""


def _json_extract_document_row_evidence(value: Dict[str, Any], tender_id: Any = "") -> Dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    tender_text = _clean(tender_id)
    evidence: Dict[str, Any] = {
        "has_explicit_url_or_path": False,
        "has_blob_name": False,
        "has_filename": False,
        "has_distinct_document_id": False,
        "candidate_document_id": "",
        "available_keys_limited": [],
        "direct_url_value": "",
        "blob_name_value": "",
        "downloaded_file_name_value": "",
        "filename_value": "",
        "row_keys": [],
    }
    row_keys: List[str] = []
    doc_like_keys = ("document", "documents", "support", "supporting", "attachment", "file", "filename", "filepath", "path", "blob", "url", "download", "spec", "sbd", "boq", "returnable")
    explicit_keys = {
        "downloadurl",
        "documenturl",
        "attachmenturl",
        "fileurl",
        "url",
        "href",
        "downloadpath",
        "documentpath",
        "filepath",
        "path",
    }
    filename_keys = {"filename", "file_name", "name", "downloadedfilename", "downloaded_file_name"}
    blob_keys = {"blobname", "blob_name"}
    candidate_doc_ids: List[str] = []

    for key, nested in value.items():
        key_text = _clean(key)
        if key_text and key_text not in row_keys:
            row_keys.append(key_text)
        lower_key = key_text.lower()
        if isinstance(nested, (dict, list)):
            continue
        raw_text = _clean(nested)
        if not raw_text:
            continue
        if lower_key in explicit_keys and not _json_value_is_filename_only(raw_text):
            resolved = _json_resolve_explicit_value(raw_text, "")
            if resolved:
                evidence["has_explicit_url_or_path"] = True
                evidence["direct_url_value"] = raw_text
        if lower_key in blob_keys and raw_text:
            evidence["has_blob_name"] = True
            evidence["blob_name_value"] = raw_text
        if lower_key in filename_keys or _clean(key).lower() in {"filename", "file_name", "file name", "name", "file"}:
            if _json_value_looks_like_filename(raw_text):
                evidence["has_filename"] = True
                evidence["filename_value"] = raw_text
                if lower_key in {"downloadedfilename", "downloaded_file_name"}:
                    evidence["downloaded_file_name_value"] = raw_text
        if _json_value_looks_like_doc_id(key_text, nested):
            candidate_doc_ids.append(raw_text)
        if any(token in lower_key for token in doc_like_keys) and _json_value_looks_like_url(raw_text):
            evidence["has_explicit_url_or_path"] = True
            evidence["direct_url_value"] = raw_text
        if any(token in lower_key for token in ("filename", "file_name", "file name")) and _json_value_looks_like_filename(raw_text):
            evidence["has_filename"] = True
            evidence["filename_value"] = raw_text

    distinct_doc_ids = [doc_id for doc_id in candidate_doc_ids if doc_id and doc_id != tender_text]
    if distinct_doc_ids:
        evidence["has_distinct_document_id"] = True
        evidence["candidate_document_id"] = distinct_doc_ids[0]
    evidence["available_keys_limited"] = _unique_compact(row_keys, limit=30)
    evidence["row_keys"] = _unique_compact(row_keys, limit=30)
    return evidence


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


def _mine_tenderdetails_json(payload: Any, tender_id: Any = "") -> Dict[str, Any]:
    doc_key_pattern = re.compile(r"(document|documents|support|supporting|attachment|file|filename|filepath|path|blob|url|download|spec|sbd|boq|returnable)", re.I)
    summary: Dict[str, Any] = {
        "tenderdetails_json_rows_seen": 0,
        "tenderdetails_json_document_rows_rejected": 0,
        "tenderdetails_json_document_rows_accepted": 0,
        "tenderdetails_json_top_level_rows_rejected": 0,
        "json_top_level_keys": [],
        "document_like_key_paths": [],
        "filename_like_values_limited": [],
        "url_like_values_limited": [],
        "id_like_values_by_path": [],
        "document_row_candidates_count": 0,
        "document_row_candidate_keys": [],
        "tender_id_used": _clean(tender_id),
    }
    rows: List[Dict[str, Any]] = []
    rejections: List[Dict[str, Any]] = []
    document_like_key_paths: List[str] = []
    filename_values: List[str] = []
    url_values: List[str] = []
    id_values: List[Dict[str, str]] = []
    row_keys: List[str] = []
    seen_rows = set()
    tender_text = _clean(tender_id)

    def _add_row(path: str, value: Dict[str, Any], keys: List[str]) -> None:
        blob = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        row_key = (path, tuple(sorted(_clean(k) for k in keys)), blob[:160])
        if row_key in seen_rows:
            return
        seen_rows.add(row_key)
        summary["document_row_candidates_count"] += 1
        summary["tenderdetails_json_document_rows_accepted"] += 1
        rows.append({
            "source_json_path": path,
            "row_keys": _unique_compact(keys, limit=30),
            "tender_id": _clean(tender_id),
            "value": value,
        })
        for key in keys:
            text = _clean(key)
            if text and text not in row_keys:
                row_keys.append(text)

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if path == "$":
                summary["json_top_level_keys"] = _unique_compact(list(value.keys()), limit=80)
            summary["tenderdetails_json_rows_seen"] += 1
            keys_here: List[str] = []
            has_real_document_signals = False
            evidence = _json_extract_document_row_evidence(value, tender_id)
            for key, nested in value.items():
                key_text = _clean(key)
                child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                keys_here.append(key_text)
                if doc_key_pattern.search(key_text):
                    document_like_key_paths.append(child_path)
                lower_key = key_text.lower()
                if "tenderid" in lower_key or "tendersid" in lower_key or (lower_key == "id" and _clean(nested).isdigit()):
                    id_values.append({"path": child_path, "name": key_text, "value": _clean(nested)})
                if isinstance(nested, dict) or isinstance(nested, list):
                    _walk(nested, child_path)
                    continue
                if _json_value_looks_like_url(nested):
                    url_values.append(f"{child_path}={_snippet(nested)}")
                if _json_value_looks_like_filename(nested):
                    filename_values.append(f"{child_path}={_snippet(nested)}")
                if _json_value_looks_like_doc_id(key_text, nested):
                    id_values.append({"path": child_path, "name": key_text, "value": _clean(nested)})
            has_real_document_signals = bool(
                evidence.get("has_explicit_url_or_path")
                or evidence.get("has_blob_name")
                or evidence.get("has_filename")
                or evidence.get("has_distinct_document_id")
            )
            blob = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).lower()
            if has_real_document_signals:
                if path not in document_like_key_paths:
                    document_like_key_paths.append(path)
                _add_row(path, value, keys_here)
            elif path == "$":
                summary["tenderdetails_json_document_rows_rejected"] += 1
                summary["tenderdetails_json_top_level_rows_rejected"] += 1
                candidate_document_id = _clean(evidence.get("candidate_document_id") or _clean(tender_id))
                rejections.append({
                    "diagnostic_type": "tenderdetails_json_document_row_rejected",
                    "source_json_path": path,
                    "tender_id": _clean(tender_id),
                    "candidate_document_id": candidate_document_id,
                    "rejection_reason": "top_level_tender_row_not_document",
                    "available_keys_limited": _unique_compact(list(value.keys()), limit=40),
                })
        elif isinstance(value, list):
            list_keys: List[str] = []
            for index, nested in enumerate(value):
                child_path = f"{path}[{index}]"
                if isinstance(nested, dict):
                    nested_keys = [_clean(key) for key in nested.keys()]
                    list_keys.extend(nested_keys)
                    if path == "$":
                        nested_evidence = _json_extract_document_row_evidence(nested, tender_id)
                        nested_has_real_document_signals = bool(
                            nested_evidence.get("has_explicit_url_or_path")
                            or nested_evidence.get("has_blob_name")
                            or nested_evidence.get("has_filename")
                            or nested_evidence.get("has_distinct_document_id")
                        )
                        if not nested_has_real_document_signals:
                            summary["tenderdetails_json_document_rows_rejected"] += 1
                            summary["tenderdetails_json_top_level_rows_rejected"] += 1
                            candidate_document_id = _clean(nested_evidence.get("candidate_document_id") or _clean(tender_id))
                            rejections.append({
                                "diagnostic_type": "tenderdetails_json_document_row_rejected",
                                "source_json_path": child_path,
                                "tender_id": _clean(tender_id),
                                "candidate_document_id": candidate_document_id,
                                "rejection_reason": "top_level_tender_row_not_document",
                                "available_keys_limited": _unique_compact(list(nested.keys()), limit=40),
                            })
                    _walk(nested, child_path)
                else:
                    if _json_value_looks_like_url(nested):
                        url_values.append(f"{child_path}={_snippet(nested)}")
                    if _json_value_looks_like_filename(nested):
                        filename_values.append(f"{child_path}={_snippet(nested)}")
                    if _json_value_looks_like_doc_id("id", nested):
                        id_values.append({"path": child_path, "name": "id", "value": _clean(nested)})

    _walk(payload, "$")
    summary["document_like_key_paths"] = _unique_compact(document_like_key_paths, limit=100)
    summary["filename_like_values_limited"] = _unique_compact(filename_values, limit=80)
    summary["url_like_values_limited"] = _unique_compact(url_values, limit=80)
    summary["id_like_values_by_path"] = id_values[:100]
    summary["document_row_candidate_keys"] = _unique_compact(row_keys, limit=100)
    summary["tenderdetails_json_document_rows_rejected"] = len(rejections)
    return {"summary": summary, "document_rows": rows, "document_row_rejections": rejections}


def _row_to_document_record(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("value") if isinstance(row, dict) else {}
    if not isinstance(value, dict):
        value = {}
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    filename = _clean(
        value.get("fileName")
        or value.get("filename")
        or value.get("downloadedFileName")
        or value.get("DownloadedFileName")
        or value.get("downloaded_filename")
        or value.get("documentName")
        or value.get("supportDocumentName")
        or value.get("name")
    )
    support_document_id = _clean(
        value.get("supportDocumentID")
        or value.get("supportDocumentId")
        or value.get("documentID")
        or value.get("documentId")
        or value.get("id")
    )
    tender_id = _clean(value.get("tendersID") or value.get("tenderId") or value.get("tender_id") or row.get("tender_id"))
    url = _clean(
        value.get("url")
        or value.get("href")
        or value.get("downloadUrl")
        or value.get("fileUrl")
        or value.get("documentUrl")
        or value.get("attachmentUrl")
        or value.get("filePath")
        or value.get("path")
    )
    blob_name = _clean(value.get("blobName") or value.get("BlobName") or value.get("blobname"))
    downloaded_file_name = _clean(value.get("downloadedFileName") or value.get("DownloadedFileName") or value.get("downloaded_filename"))
    document_id = _clean(value.get("documentId") or value.get("documentID") or value.get("id"))
    guid = _extract_guid(blob)
    extension = _clean(value.get("extension") or Path(filename or url).suffix)
    support_document_id = support_document_id if support_document_id and support_document_id != tender_id else ""
    document_id = document_id if document_id and document_id != tender_id else ""
    return {
        "source_json_path": _clean(row.get("source_json_path")),
        "filename": filename,
        "downloaded_file_name": downloaded_file_name,
        "blob_name": blob_name,
        "safe_filename": _safe_filename(filename or f"{support_document_id or document_id}.pdf"),
        "support_document_id": support_document_id,
        "document_id": document_id,
        "tender_id": tender_id,
        "url": url,
        "path": _clean(value.get("path") or value.get("filePath")),
        "extension": extension,
        "guids": guid,
        "row_keys": _unique_compact(row.get("row_keys") if isinstance(row.get("row_keys"), list) else [], limit=30),
    }


def _extract_documents_from_details(data: Any) -> List[Dict[str, Any]]:
    mined = _mine_tenderdetails_json(data)
    return [_row_to_document_record(row) for row in mined.get("document_rows", []) if isinstance(row, dict)]


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


def _build_download_candidates(tender_id: Any, row: Dict[str, Any], doc: Dict[str, Any], detail_page_url: str = "") -> List[Dict[str, Any]]:
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
    downloaded_file_name = str(doc.get("downloaded_file_name") or "")
    blob_name = str(doc.get("blob_name") or "")
    support_id = str(doc.get("support_document_id") or "")
    document_id = str(doc.get("document_id") or doc.get("support_document_id") or "")
    doc_tender_id = str(doc.get("tender_id") or tender_id or "")
    guids = [str(g) for g in (doc.get("guids") or [])]
    source_json_path = str(doc.get("source_json_path") or row.get("source_json_path") or "")
    row_keys = doc.get("row_keys") if isinstance(doc.get("row_keys"), list) else []
    row_value = row.get("value") if isinstance(row, dict) else {}
    if not isinstance(row_value, dict):
        row_value = {}

    def add(
        path: str,
        params: Dict[str, Any],
        reason: str,
        *,
        route_pattern_name: str,
        parameter_names_used: Optional[List[str]] = None,
        tender_id_used: str = "",
        document_id_used: str = "",
        original_json_value: str = "",
        resolved_document_url: str = "",
        priority: int = 50,
    ) -> None:
        clean_params = {k: v for k, v in params.items() if v not in (None, "")}
        url = f"{ETENDERS_BASE}{path}?{urlencode(clean_params)}"
        if url not in seen:
            seen.add(url)
            effective_source_json_path = source_json_path if route_pattern_name != "tender_id_fallback" else "tender_id_fallback"
            out.append({
                "url": url,
                "reason": reason,
                "params": clean_params,
                "route_pattern_name": route_pattern_name,
                "source_json_path": effective_source_json_path,
                "parameter_names_used": _unique_compact(parameter_names_used or list(clean_params.keys()), limit=12),
                "tender_id_used": _clean(tender_id_used or doc_tender_id),
                "document_id_used": _clean(document_id_used),
                "document_url": resolved_document_url or url,
                "resolved_document_url": resolved_document_url or url,
                "source": "discovered_json",
                "source_hint": source_json_path,
                "candidate_source_json_keys": _unique_compact(row_keys, limit=30),
                "original_json_value": _clean(original_json_value),
                "candidate_priority": int(priority),
                "blobName": _clean(blob_name),
                "downloadedFileName": _clean(downloaded_file_name or filename),
            })

    explicit_keys = [
        "downloadUrl",
        "documentUrl",
        "attachmentUrl",
        "fileUrl",
        "url",
        "href",
        "downloadPath",
        "documentPath",
        "filePath",
        "path",
    ]

    explicit_added = False
    for key in explicit_keys:
        raw_value = row_value.get(key)
        raw_text = _clean(raw_value)
        if not raw_text or _json_value_is_filename_only(raw_text):
            continue
        resolved = _json_resolve_explicit_value(raw_text, detail_page_url)
        if not resolved:
            continue
        explicit_added = True
        param_names = [key]
        if raw_text.startswith(("http://", "https://")):
            param_names = ["url"]
        elif raw_text.startswith("/"):
            param_names = ["path"]
        out.append({
            "url": resolved,
            "document_url": resolved,
            "resolved_document_url": resolved,
            "reason": f"explicit_json:{key}",
            "route_pattern_name": "explicit_json_url_or_path",
            "source_json_path": source_json_path,
            "parameter_names_used": param_names,
            "tender_id_used": _clean(doc_tender_id),
            "document_id_used": _clean(document_id or support_id),
            "original_json_value": raw_text,
            "original_json_key": key,
            "candidate_classification": "direct_file",
            "candidate_score": 100,
            "candidate_should_attempt": True,
            "candidate_rejection_reason": "",
            "source": "discovered_json",
            "source_hint": source_json_path,
            "candidate_source_json_keys": _unique_compact(row_keys, limit=30),
            "candidate_priority": 0,
        })

    if blob_name:
        blob_downloaded_name = _clean(downloaded_file_name or filename)
        blob_params = {"blobName": blob_name}
        parameter_names_used = ["blobName"]
        if blob_downloaded_name:
            blob_params["downloadedFileName"] = blob_downloaded_name
            parameter_names_used = ["blobName", "downloadedFileName"]
        blob_url = f"{ETENDERS_BASE}/Home/Download/?{urlencode(blob_params)}"
        blob_ext = Path(blob_name).suffix.lower() or Path(blob_downloaded_name).suffix.lower()
        blob_classification = "direct_file" if blob_ext in {".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".csv"} else "likely_download_endpoint"
        out.append({
            "url": blob_url,
            "document_url": blob_url,
            "resolved_document_url": blob_url,
            "reason": "explicit_json:blobName",
            "route_pattern_name": "etenders_blob_download",
            "source_json_path": source_json_path,
            "parameter_names_used": parameter_names_used,
            "tender_id_used": _clean(doc_tender_id),
            "document_id_used": "",
            "original_json_value": blob_name,
            "original_json_key": "blobName",
            "candidate_classification": blob_classification,
            "candidate_score": 100 if blob_classification == "direct_file" else 88,
            "candidate_should_attempt": True,
            "candidate_rejection_reason": "",
            "source": "discovered_json",
            "source_hint": source_json_path,
            "candidate_source_json_keys": _unique_compact(row_keys, limit=30),
            "candidate_priority": 1,
            "blobName": blob_name,
            "downloadedFileName": blob_downloaded_name,
        })

    for endpoint in endpoints:
        if support_id:
            for key in ("supportDocumentID", "supportDocumentId", "documentId", "documentID", "id"):
                add(endpoint, {key: support_id, "source": "sharepoint"}, f"{endpoint}:{key}=support_id", route_pattern_name=f"{Path(endpoint).name}_{key}_support", parameter_names_used=[key, "source"], tender_id_used=doc_tender_id, document_id_used=support_id, original_json_value=support_id, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({key: support_id, 'source': 'sharepoint'})}", priority=3)

        for guid in guids:
            for key in ("supportDocumentID", "supportDocumentId", "documentGuid", "documentId", "id"):
                add(endpoint, {key: guid, "source": "sharepoint"}, f"{endpoint}:{key}=guid", route_pattern_name=f"{Path(endpoint).name}_{key}_guid", parameter_names_used=[key, "source"], tender_id_used=doc_tender_id, document_id_used=guid, original_json_value=guid, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({key: guid, 'source': 'sharepoint'})}", priority=3)

        if doc_tender_id and filename:
            add(endpoint, {"tenderId": doc_tender_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:tenderId+fileName", route_pattern_name=f"{Path(endpoint).name}_tenderId_fileName", parameter_names_used=["tenderId", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=document_id or support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'tenderId': doc_tender_id, 'fileName': filename, 'source': 'sharepoint'})}", priority=5)
            add(endpoint, {"tendersID": doc_tender_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:tendersID+fileName", route_pattern_name=f"{Path(endpoint).name}_tendersID_fileName", parameter_names_used=["tendersID", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=document_id or support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'tendersID': doc_tender_id, 'fileName': filename, 'source': 'sharepoint'})}", priority=5)
            add(endpoint, {"documentId": doc_tender_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:documentId+fileName", route_pattern_name=f"{Path(endpoint).name}_documentId_fileName", parameter_names_used=["documentId", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=document_id or support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'documentId': doc_tender_id, 'fileName': filename, 'source': 'sharepoint'})}", priority=2)

        if support_id and filename:
            add(endpoint, {"supportDocumentID": support_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:support_id+fileName", route_pattern_name=f"{Path(endpoint).name}_supportDocumentID_fileName", parameter_names_used=["supportDocumentID", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'supportDocumentID': support_id, 'fileName': filename, 'source': 'sharepoint'})}", priority=4)
            add(endpoint, {"documentId": support_id, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:document_id+fileName", route_pattern_name=f"{Path(endpoint).name}_documentId_fileName", parameter_names_used=["documentId", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'documentId': support_id, 'fileName': filename, 'source': 'sharepoint'})}", priority=2)

        for guid in guids:
            if filename:
                add(endpoint, {"supportDocumentID": guid, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:guid+fileName", route_pattern_name=f"{Path(endpoint).name}_supportDocumentID_fileName", parameter_names_used=["supportDocumentID", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=guid, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'supportDocumentID': guid, 'fileName': filename, 'source': 'sharepoint'})}", priority=4)
                add(endpoint, {"documentGuid": guid, "fileName": filename, "source": "sharepoint"}, f"{endpoint}:documentGuid+fileName", route_pattern_name=f"{Path(endpoint).name}_documentGuid_fileName", parameter_names_used=["documentGuid", "fileName", "source"], tender_id_used=doc_tender_id, document_id_used=guid, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'documentGuid': guid, 'fileName': filename, 'source': 'sharepoint'})}", priority=4)

    # Some ASP.NET actions use only fileName and tendersID.
    for endpoint in endpoints:
        if filename:
            add(endpoint, {"fileName": filename, "tendersID": doc_tender_id}, f"{endpoint}:fileName+tendersID", route_pattern_name=f"{Path(endpoint).name}_fileName_tendersID", parameter_names_used=["fileName", "tendersID"], tender_id_used=doc_tender_id, document_id_used=document_id or support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'fileName': filename, 'tendersID': doc_tender_id})}", priority=5)
            add(endpoint, {"fileName": filename, "tenderId": doc_tender_id}, f"{endpoint}:fileName+tenderId", route_pattern_name=f"{Path(endpoint).name}_fileName_tenderId", parameter_names_used=["fileName", "tenderId"], tender_id_used=doc_tender_id, document_id_used=document_id or support_id, original_json_value=filename, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'fileName': filename, 'tenderId': doc_tender_id})}", priority=5)

    if document_id and not filename:
        for endpoint in endpoints:
            add(endpoint, {"documentId": document_id}, f"{endpoint}:documentId", route_pattern_name=f"{Path(endpoint).name}_documentId", parameter_names_used=["documentId"], tender_id_used=doc_tender_id, document_id_used=document_id, original_json_value=document_id, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'documentId': document_id})}", priority=4)
            add(endpoint, {"supportDocumentID": document_id}, f"{endpoint}:supportDocumentID", route_pattern_name=f"{Path(endpoint).name}_supportDocumentID", parameter_names_used=["supportDocumentID"], tender_id_used=doc_tender_id, document_id_used=document_id, original_json_value=document_id, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'supportDocumentID': document_id})}", priority=4)

    if doc_tender_id and not support_id and not document_id and not explicit_added and not blob_name:
        for endpoint in endpoints:
            add(endpoint, {"tenderId": doc_tender_id}, f"{endpoint}:tenderId", route_pattern_name="tender_id_fallback", parameter_names_used=["tenderId"], tender_id_used=doc_tender_id, document_id_used="", original_json_value=doc_tender_id, resolved_document_url=f"{ETENDERS_BASE}{endpoint}?{urlencode({'tenderId': doc_tender_id})}", priority=5)

    out.sort(
        key=lambda item: (
            int(item.get("candidate_priority")) if item.get("candidate_priority") is not None else 50,
            -int(item.get("candidate_score") or 0),
        )
    )
    return out


def _download_candidate(url: str, output_path: Path, timeout: int = 35) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "url": url,
        "ok": False,
        "verified_download": False,
        "status_code": 0,
        "http_status": 0,
        "final_url": url,
        "content_type": "",
        "content_disposition": "",
        "content_length": 0,
        "saved_path": "",
        "error": "",
        "validation": {},
        "binary_signature_detected": False,
    }

    headers = _headers("application/pdf,application/zip,application/octet-stream,*/*")

    try:
        with requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True) as resp:
            result["status_code"] = resp.status_code
            result["http_status"] = resp.status_code
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
            result["binary_signature_detected"] = bool(
                result["validation"].get("byte_pdf")
                or result["validation"].get("byte_zip")
                or result["validation"].get("byte_doc")
            )

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
    mined = _mine_tenderdetails_json(fetched.get("data"), tender_id) if fetched.get("ok") else {"summary": {"tender_id_used": _clean(tender_id)}, "document_rows": []}
    docs = [_row_to_document_record(row) for row in mined.get("document_rows", [])]
    sanitized_attempts = []
    for attempt in fetched.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        sanitized_attempts.append({k: v for k, v in attempt.items() if k != "data"})

    return {
        "status": "ok" if fetched.get("ok") else "error",
        "service_version": SERVICE_VERSION,
        "inspected_at": _now(),
        "tender_id": tender_id,
        "details_ok": fetched.get("ok"),
        "details_url": fetched.get("winning_url"),
        "details_attempts": sanitized_attempts,
        "tenderdetails_json_rows_seen": mined.get("summary", {}).get("tenderdetails_json_rows_seen", 0),
        "tenderdetails_json_document_rows_rejected": mined.get("summary", {}).get("tenderdetails_json_document_rows_rejected", 0),
        "tenderdetails_json_document_rows_accepted": mined.get("summary", {}).get("tenderdetails_json_document_rows_accepted", 0),
        "tenderdetails_json_top_level_rows_rejected": mined.get("summary", {}).get("tenderdetails_json_top_level_rows_rejected", 0),
        "json_top_level_keys": mined.get("summary", {}).get("json_top_level_keys", []),
        "document_like_key_paths": mined.get("summary", {}).get("document_like_key_paths", []),
        "filename_like_values_limited": mined.get("summary", {}).get("filename_like_values_limited", []),
        "url_like_values_limited": mined.get("summary", {}).get("url_like_values_limited", []),
        "id_like_values_by_path": mined.get("summary", {}).get("id_like_values_by_path", []),
        "document_row_candidates_count": mined.get("summary", {}).get("document_row_candidates_count", 0),
        "document_row_candidate_keys": mined.get("summary", {}).get("document_row_candidate_keys", []),
        "tender_id_used": mined.get("summary", {}).get("tender_id_used", _clean(tender_id)),
        "document_rows": mined.get("document_rows", []),
        "document_row_rejections": mined.get("document_row_rejections", []),
        "document_count": len(docs),
        "documents": docs,
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

    rows = inspected.get("document_rows") or []
    rejected_rows = inspected.get("document_row_rejections") if isinstance(inspected.get("document_row_rejections"), list) else []
    doc_entries: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        doc_entries.append({
            "row": row,
            "doc": _row_to_document_record(row),
        })

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

    doc_entries.sort(key=lambda entry: doc_score(entry.get("doc") or {}), reverse=True)
    docs = [entry.get("doc") or {} for entry in doc_entries]

    attempts: List[Dict[str, Any]] = []
    candidate_queue: List[Dict[str, Any]] = []

    for rejection in rejected_rows:
        if isinstance(rejection, dict):
            attempts.append(rejection)

    for entry in doc_entries:
        row = entry.get("row") or {}
        doc = entry.get("doc") or {}
        safe_name = _safe_filename(doc.get("filename") or preferred_filename or f"tender_{tender_id}_document.pdf")
        output_path = output_dir / f"ETENDERS_{tender_id}__{safe_name}"
        candidates = _build_download_candidates(tender_id, row, doc, inspected.get("details_url") or "")
        for candidate in candidates:
            candidate_queue.append({
                **candidate,
                "output_path": str(output_path),
                "document": {
                    "filename": doc.get("filename"),
                    "support_document_id": doc.get("support_document_id"),
                    "document_id": doc.get("document_id"),
                    "tender_id": doc.get("tender_id"),
                    "guids": doc.get("guids"),
                    "source_json_path": doc.get("source_json_path"),
                },
            })

    if not candidate_queue and tender_id:
        fallback_candidates = []
        for endpoint in ("/Home/DownloadSpec", "/Home/DownloadDocument", "/Home/DownloadTenderDocument", "/Home/DownloadFile"):
            fallback_candidates.append({
                "url": f"{ETENDERS_BASE}{endpoint}?{urlencode({'tenderId': tender_id})}",
                "reason": f"tender_id_fallback:{endpoint}",
                "route_pattern_name": "tender_id_fallback",
                "source_json_path": "tender_id_fallback",
                "parameter_names_used": ["tenderId"],
                "tender_id_used": tender_id,
                "document_id_used": "",
                "original_json_value": tender_id,
                "resolved_document_url": f"{ETENDERS_BASE}{endpoint}?{urlencode({'tenderId': tender_id})}",
                "candidate_priority": 99,
                "document": {"tender_id": tender_id, "source_json_path": "tender_id_fallback"},
            })
        candidate_queue.extend(fallback_candidates)

    candidate_queue.sort(
        key=lambda item: (
            int(item.get("candidate_priority")) if item.get("candidate_priority") is not None else 50,
            -int(doc_score(item.get("document") or {}) or 0),
        )
    )

    for candidate in candidate_queue:
        output_path = Path(candidate.get("output_path") or output_dir)
        attempt = _download_candidate(candidate["url"], output_path)
        saved_path = _clean(attempt.get("saved_path") or "")
        artifact_exists = bool(saved_path and Path(saved_path).exists())
        artifact_size_bytes = int(Path(saved_path).stat().st_size) if artifact_exists else int(attempt.get("content_length") or 0)
        candidate_reason = _clean(candidate.get("reason"))
        failure_reason = _clean(attempt.get("error") or attempt.get("failure_reason"))
        if candidate_reason and failure_reason:
            failure_reason = f"{candidate_reason}:{failure_reason}"
        elif candidate_reason:
            failure_reason = candidate_reason
        attempt.update({
            "candidate_reason": candidate["reason"],
            "route_pattern_name": candidate.get("route_pattern_name"),
            "source_json_path": candidate.get("source_json_path"),
            "parameter_names_used": candidate.get("parameter_names_used") or [],
            "tender_id": candidate.get("tender_id_used") or tender_id,
            "document_id": candidate.get("document_id_used") or None,
            "blobName": candidate.get("blobName") or "",
            "downloadedFileName": candidate.get("downloadedFileName") or "",
            "document": candidate.get("document") or {},
            "resolved_document_url": candidate.get("resolved_document_url") or candidate.get("url"),
            "original_json_value": candidate.get("original_json_value") or "",
            "response_shape": "binary" if attempt.get("verified_download") else ("html" if "html" in _clean(attempt.get("content_type")).lower() else ("json" if "json" in _clean(attempt.get("content_type")).lower() else "unknown")),
            "failure_reason": failure_reason,
            "binary_signature_detected": bool(attempt.get("binary_signature_detected") or attempt.get("verified_download")),
            "artifact_path": saved_path,
            "artifact_exists": artifact_exists,
            "artifact_size_bytes": artifact_size_bytes,
            "content_length": int(attempt.get("content_length") or 0),
            "content_disposition": _clean(attempt.get("content_disposition") or ""),
        })
        attempts.append(attempt)

        if attempt.get("verified_download"):
            return {
                "status": "ok",
                "service_version": SERVICE_VERSION,
                "downloaded_at": _now(),
                "tender_id": tender_id,
                "selected_document": candidate.get("document"),
                "saved_path": attempt.get("saved_path"),
                "content_type": attempt.get("content_type"),
                "content_length": attempt.get("content_length"),
                "winning_url": attempt.get("url"),
                "winning_reason": candidate["reason"],
                "attempt_count": len(attempts),
                "attempts": attempts,
                "inspection": inspected,
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
        "inspection": inspected,
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
