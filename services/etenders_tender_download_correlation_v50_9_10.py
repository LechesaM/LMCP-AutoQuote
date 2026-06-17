"""
LMCP V50.9.10.2 - Intelligent Tender-to-Download Correlation Engine

Purpose:
- Reads V50.9.9 runtime_intercept_log.json files.
- Extracts ONLY real eTenders PDF download candidates.
- Suppresses assets, images, fonts, browser background requests, ChatGPT assets, and unrelated static files.
- Scores captured PDF download routes against the target tender/RFQ.
- Copies or replays the best matched PDF into a clean RFQ acquisition workspace.

Routes:
    GET  /v50-9-10-tender-download-correlation/status
    POST /v50-9-10-tender-download-correlation/correlate
    POST /v50-9-10-tender-download-correlation/latest

File:
    app/services/etenders_tender_download_correlation_v50_9_10.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests


SERVICE_VERSION = "V50.9.10.2_TENDER_DOWNLOAD_CORRELATION_HARD_FILTER"

_RUNTIME_DIR = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve()
DEFAULT_INPUT_ROOT = str(_RUNTIME_DIR / "playwright" / "runtime_download_intercepts")
DEFAULT_OUTPUT_ROOT = str(_RUNTIME_DIR / "tender_document_acquisition")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    s = _clean(value).lower()
    s = s.replace("–", "-").replace("—", "-").replace("_", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _safe_filename(filename: str, fallback: str = "document.pdf") -> str:
    name = _clean(filename) or fallback
    name = name.replace("\\", "_").replace("/", "_").replace(":", "_")
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(". ")
    if not name:
        name = fallback

    if len(name) > 170:
        stem = Path(name).stem[:140]
        suffix = Path(name).suffix or ".pdf"
        name = f"{stem}{suffix}"

    return name


def _tokens(value: str) -> List[str]:
    raw = [x for x in _norm(value).split() if len(x) >= 3]
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "supply",
        "delivery",
        "tender",
        "document",
        "request",
        "quotation",
        "quote",
        "including",
        "printed",
        "copies",
        "service",
        "services",
        "appointment",
        "provider",
        "bid",
        "rfq",
    }
    return [x for x in raw if x not in stop]


def _url_filename(url: str) -> str:
    try:
        q = parse_qs(urlparse(url).query)
        if q.get("downloadedFileName"):
            return unquote(q["downloadedFileName"][0])
        return unquote(Path(urlparse(url).path).name)
    except Exception:
        return ""


def _blob_name(url: str) -> str:
    try:
        q = parse_qs(urlparse(url).query)
        return q.get("blobName", [""])[0]
    except Exception:
        return ""


def _headers_filename(headers: Dict[str, Any]) -> str:
    cdisp = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
    if not cdisp:
        return ""

    m = re.search(r"filename\*=UTF-8''([^;]+)", cdisp, re.I)
    if m:
        return unquote(m.group(1)).strip('" ')

    m = re.search(r'filename="?([^";]+)"?', cdisp, re.I)
    if m:
        return m.group(1).strip()

    return ""


def _is_real_etenders_pdf_download(url: str, headers: Optional[Dict[str, Any]] = None, filename: str = "") -> bool:
    """
    Hard early filter.

    This prevents the scorer from ever seeing:
    - PNG/SVG/ICO/WEBP assets
    - WOFF/WOFF2 fonts
    - CSS/JS
    - ChatGPT/Gstatic/Auth0/browser background requests
    - non-eTenders resources
    - non-PDF eTenders assets

    A valid candidate must be:
    - from www.etenders.gov.za
    - a /home/Download/ route
    - contain blobName=
    - be a PDF response or PDF filename
    """
    headers = headers or {}
    low_url = str(url or "").lower()
    low_filename = str(filename or "").lower()
    ctype = str(headers.get("content-type") or headers.get("Content-Type") or "").lower()
    cdisp = str(headers.get("content-disposition") or headers.get("Content-Disposition") or "").lower()

    if "www.etenders.gov.za" not in low_url and "etenders.gov.za" not in low_url:
        return False

    if "/download/" not in low_url:
        return False

    if "blobname=" not in low_url:
        return False

    blocked_exts = (
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".ico",
        ".css",
        ".js",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".map",
    )

    parsed_path = urlparse(str(url or "")).path.lower()
    if parsed_path.endswith(blocked_exts):
        return False

    if any(x in low_url for x in ["chatgpt.com", "gstatic.com", "googleusercontent.com", "auth0.com", "cdn.openai.com"]):
        return False

    has_pdf_ctype = "application/pdf" in ctype
    has_pdf_url = ".pdf" in low_url
    has_pdf_filename = ".pdf" in low_filename
    has_pdf_cdisp = ".pdf" in cdisp

    if not (has_pdf_ctype or has_pdf_url or has_pdf_filename or has_pdf_cdisp):
        return False

    return True


def _find_latest_logs(input_root: str, tender_id: str = "", limit: int = 10) -> List[Path]:
    root = Path(input_root)
    if not root.exists():
        return []

    logs = list(root.glob("**/runtime_intercept_log.json"))

    if tender_id:
        tid = str(tender_id)
        logs = [p for p in logs if tid in str(p)]

    logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[:limit]


def _load_log(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {
            "_load_error": str(exc),
            "_path": str(path),
        }


def _extract_download_candidates(log: Dict[str, Any], log_path: Path) -> List[Dict[str, Any]]:
    """
    Extract only real eTenders PDF download candidates.

    The original V50.9.10 admitted too many binary assets.
    V50.9.10.2 applies hard early filtering in every candidate source:
    - download_events
    - binary_saves
    - network_events
    """
    candidates: List[Dict[str, Any]] = []
    run_dir = Path(log.get("run_dir") or log_path.parent)

    # 1) Download events saved by Playwright
    for item in log.get("download_events") or []:
        url = item.get("url") or ""
        headers: Dict[str, Any] = {}
        filename = item.get("suggested_filename") or _url_filename(url)

        if not _is_real_etenders_pdf_download(url, headers, filename):
            continue

        candidates.append(
            {
                "source": "download_event",
                "url": url,
                "filename": filename,
                "blobName": _blob_name(url),
                "saved_path": item.get("saved_path") or "",
                "size": item.get("size") or 0,
                "headers": headers,
                "log_path": str(log_path),
                "run_dir": str(run_dir),
                "raw": item,
            }
        )

    # 2) Binary responses saved by V50.9.9
    for item in log.get("binary_saves") or []:
        url = item.get("url") or ""
        headers = item.get("headers") or {}
        filename = item.get("filename") or _headers_filename(headers) or _url_filename(url)

        if not _is_real_etenders_pdf_download(url, headers, filename):
            continue

        candidates.append(
            {
                "source": "binary_save",
                "url": url,
                "filename": filename,
                "blobName": _blob_name(url),
                "saved_path": item.get("saved_path") or "",
                "size": item.get("size") or item.get("saved_size") or 0,
                "headers": headers,
                "log_path": str(log_path),
                "run_dir": str(run_dir),
                "raw": item,
            }
        )

    # 3) Important network responses with content-disposition / PDF metadata
    for ev in log.get("network_events") or []:
        if ev.get("kind") != "response":
            continue

        headers = ev.get("headers") or {}
        url = ev.get("url") or ""
        filename = _headers_filename(headers) or _url_filename(url)

        if not _is_real_etenders_pdf_download(url, headers, filename):
            continue

        content_length = headers.get("content-length") or headers.get("Content-Length") or 0
        try:
            size = int(content_length)
        except Exception:
            size = 0

        candidates.append(
            {
                "source": "network_response",
                "url": url,
                "filename": filename,
                "blobName": _blob_name(url),
                "saved_path": "",
                "size": size,
                "headers": headers,
                "request_headers": ev.get("request_headers") or {},
                "log_path": str(log_path),
                "run_dir": str(run_dir),
                "raw": ev,
            }
        )

    # De-duplicate by URL, saved path, and filename
    out: List[Dict[str, Any]] = []
    seen = set()

    for candidate in candidates:
        key = (
            candidate.get("url", ""),
            candidate.get("saved_path", ""),
            candidate.get("filename", ""),
        )
        if key not in seen:
            seen.add(key)
            out.append(candidate)

    return out


def _score_candidate(candidate: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    tender_id = _clean(target.get("tender_id"))
    tender_no = _clean(target.get("tender_no"))
    title = _clean(target.get("title") or target.get("description"))
    buyer = _clean(target.get("buyer_name") or target.get("department") or "")
    support_document_id = _clean(target.get("supportDocumentID") or target.get("support_document_id") or "")

    filename = _clean(candidate.get("filename"))
    url = _clean(candidate.get("url"))
    blob_name = _clean(candidate.get("blobName"))

    blob = " ".join(
        [
            filename,
            url,
            blob_name,
            json.dumps(candidate.get("headers") or {}, ensure_ascii=False),
        ]
    )

    norm_blob = _norm(blob)
    norm_title = _norm(title)

    score = 0
    reasons: List[str] = []

    # Strong direct identifiers
    if tender_id and tender_id in blob:
        score += 40
        reasons.append("tender_id_found")

    if support_document_id and support_document_id.lower() in blob.lower():
        score += 90
        reasons.append("support_document_id_found")

    compact_no = re.sub(r"[^a-z0-9]+", "", _norm(tender_no))
    compact_blob = re.sub(r"[^a-z0-9]+", "", norm_blob)

    if compact_no and compact_no in compact_blob:
        score += 80
        reasons.append("exact_tender_no_found")
    else:
        no_hits = [x for x in _tokens(tender_no) if x in norm_blob]
        if no_hits:
            score += 15 * len(no_hits)
            reasons.append("tender_no_token_hits:" + ",".join(no_hits[:8]))

    title_hits = [x for x in _tokens(title) if x in norm_blob]
    if title_hits:
        score += min(60, 8 * len(title_hits))
        reasons.append("title_token_hits:" + ",".join(title_hits[:10]))

    buyer_hits = [x for x in _tokens(buyer) if x in norm_blob]
    if buyer_hits:
        score += min(30, 10 * len(buyer_hits))
        reasons.append("buyer_token_hits:" + ",".join(buyer_hits[:8]))

    # General target keywords for current JDA example and similar RFQs
    strong_terms = []
    for term in ["digital", "book", "jda", "anniversary", "jdamark", "rfq"]:
        if term in norm_blob:
            strong_terms.append(term)

    if strong_terms:
        score += 12 * len(strong_terms)
        reasons.append("strong_keyword_hits:" + ",".join(strong_terms))

    # Quality signals
    if filename.lower().endswith(".pdf") or ".pdf" in url.lower():
        score += 8
        reasons.append("pdf_document")

    if candidate.get("size", 0):
        score += min(12, int(candidate.get("size", 0)) // 250000)
        reasons.append("nonzero_size")

    if "/download/" in url.lower() and "blobname=" in url.lower():
        score += 15
        reasons.append("valid_etenders_blob_download_route")

    # False positive penalties
    penalties = []
    for bad in ["233q", "232g", "234q", "macassar", "earthmoving", "water treatment", "security", "sanral"]:
        if bad in norm_blob and bad not in norm_title:
            score -= 35
            penalties.append(bad)

    if penalties:
        reasons.append("unrelated_penalty:" + ",".join(penalties[:8]))

    target_hits = len(title_hits) + len(buyer_hits) + len(strong_terms)

    if compact_no and compact_no in compact_blob:
        target_hits += 5

    if support_document_id and support_document_id.lower() in blob.lower():
        target_hits += 5

    confidence = (
        "high"
        if score >= 80 and target_hits >= 2
        else "medium"
        if score >= 35 and target_hits >= 1
        else "low"
    )

    return {
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "target_hit_count": target_hits,
    }


def _copy_or_replay(candidate: Dict[str, Any], output_dir: Path, target: Dict[str, Any]) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    tender_id = _safe_filename(_clean(target.get("tender_id") or "UNKNOWN"), "UNKNOWN")
    filename = _safe_filename(candidate.get("filename") or "matched_tender_document.pdf")
    dest = output_dir / f"ETENDERS_{tender_id}__MATCHED__{filename}"

    saved_path = candidate.get("saved_path")

    if saved_path and Path(saved_path).exists():
        shutil.copy2(saved_path, dest)
        return {
            "method": "copied_existing_capture",
            "saved_path": str(dest),
            "saved_size": dest.stat().st_size,
            "source_path": saved_path,
        }

    url = candidate.get("url")

    if not url:
        return {
            "method": "none",
            "error": "No saved_path or URL available.",
        }

    headers = candidate.get("request_headers") or {}

    # Avoid brittle browser-only pseudo headers.
    safe_headers = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk.startswith(":") or lk in {"host", "content-length", "accept-encoding"}:
            continue
        safe_headers[k] = v

    if not safe_headers:
        safe_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.etenders.gov.za/Home/opportunities",
            "Accept": "*/*",
        }

    try:
        r = requests.get(url, headers=safe_headers, timeout=45, allow_redirects=True)

        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return {
                "method": "replayed_url",
                "saved_path": str(dest),
                "saved_size": dest.stat().st_size,
                "status_code": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "content_disposition": r.headers.get("content-disposition", ""),
            }

        return {
            "method": "replay_failed",
            "status_code": r.status_code,
            "text_preview": getattr(r, "text", "")[:300],
        }

    except Exception as exc:
        return {
            "method": "replay_error",
            "error": str(exc),
        }


def correlate_downloads(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}

    tender_id = _clean(payload.get("tender_id") or "155559")
    input_root = _clean(payload.get("input_root") or DEFAULT_INPUT_ROOT)
    output_root = Path(_clean(payload.get("output_root") or DEFAULT_OUTPUT_ROOT))
    min_score = int(payload.get("min_score") or 20)
    require_medium = bool(payload.get("require_medium_confidence", False))

    target = {
        "tender_id": tender_id,
        "tender_no": _clean(payload.get("tender_no") or "JDAMARK/DIGITALBOOK /05/2026"),
        "title": _clean(
            payload.get("title")
            or payload.get("description")
            or "RFQ – SUPPLY AND DELIVERY OF A DIGITAL BOOK (INCLUDING PRINTED COPIES) FOR THE JDA 25TH ANNIVERSARY"
        ),
        "buyer_name": _clean(payload.get("buyer_name") or payload.get("department") or "Johannesburg Development Agency"),
        "supportDocumentID": _clean(payload.get("supportDocumentID") or payload.get("document_guid") or ""),
    }

    explicit_log = _clean(payload.get("log_path") or "")

    if explicit_log:
        logs = [Path(explicit_log)]
    else:
        logs = _find_latest_logs(
            input_root,
            tender_id=tender_id,
            limit=int(payload.get("log_limit") or 10),
        )

        if not logs:
            # Fall back to newest logs when folder does not include tender_id.
            logs = _find_latest_logs(
                input_root,
                tender_id="",
                limit=int(payload.get("log_limit") or 10),
            )

    candidates: List[Dict[str, Any]] = []

    for log_path in logs:
        log = _load_log(log_path)

        for candidate in _extract_download_candidates(log, log_path):
            candidate.update(_score_candidate(candidate, target))
            candidates.append(candidate)

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for candidate in candidates:
        ok_score = candidate.get("score", 0) >= min_score
        ok_confidence = True

        if require_medium:
            ok_confidence = candidate.get("confidence") in {"medium", "high"}

        if ok_score and ok_confidence:
            accepted.append(candidate)
        else:
            rejected.append(candidate)

    workspace = output_root / f"ETENDERS_{_safe_filename(tender_id)}"
    best = accepted[0] if accepted else None
    acquisition = _copy_or_replay(best, workspace, target) if best else None

    result = {
        "status": (
            "matched_document_acquired"
            if acquisition and acquisition.get("saved_size", 0) > 0
            else "candidate_matched"
            if best
            else "no_confident_match"
        ),
        "service_version": SERVICE_VERSION,
        "correlated_at": _now(),
        "target": target,
        "input_root": input_root,
        "loaded_logs": [str(p) for p in logs],
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "best_match": best,
        "acquisition": acquisition,
        "accepted_candidates": accepted[:30],
        "rejected_candidates_preview": rejected[:30],
        "workspace": str(workspace),
        "safe_to_process": bool(acquisition and acquisition.get("saved_size", 0) > 0),
        "notes": [
            "V50.9.10.2 applies hard early filtering before scoring.",
            "Only real eTenders /Download/ PDF blobName routes are admitted.",
            "If no confident match is found, rerun V50.9.9 and manually click only the exact target tender document.",
            "The acquired PDF is the clean handoff point for RFQ parsing, pricing, and quote generation.",
        ],
    }

    try:
        workspace.mkdir(parents=True, exist_ok=True)

        report_path = workspace / "download_correlation_report.json"
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result["correlation_report"] = str(report_path)

        manifest_path = workspace / "acquisition_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "service_version": SERVICE_VERSION,
                    "created_at": _now(),
                    "target": target,
                    "best_match": best,
                    "acquisition": acquisition,
                    "safe_to_process": result["safe_to_process"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        result["acquisition_manifest"] = str(manifest_path)

    except Exception as exc:
        result["report_error"] = str(exc)

    return result


def correlate_latest(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    payload.setdefault("log_limit", 3)
    payload.setdefault("min_score", 20)
    payload.setdefault("require_medium_confidence", False)
    return correlate_downloads(payload)


def get_v50_9_10_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "default_input_root": DEFAULT_INPUT_ROOT,
        "default_output_root": DEFAULT_OUTPUT_ROOT,
        "capabilities": [
            "v50_9_9_runtime_log_reader",
            "hard_early_pdf_download_filter",
            "etenders_blobname_route_filter",
            "asset_noise_suppression",
            "download_event_extraction",
            "network_response_download_extraction",
            "blobname_and_filename_extraction",
            "tender_keyword_scoring",
            "unrelated_download_suppression",
            "best_match_acquisition",
            "clean_rfq_workspace_generation",
            "correlation_report_and_manifest",
        ],
    }
