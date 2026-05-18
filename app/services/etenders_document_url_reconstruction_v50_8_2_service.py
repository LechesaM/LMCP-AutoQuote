"""
LMCP V50.8.2 - eTenders Document URL Reconstruction Engine

Purpose:
- Build on V50.8.1 Ajax/DataTables row discovery.
- Extract tender IDs, document GUIDs, filenames, emails, buyer fields from matched rows.
- Reconstruct likely eTenders document download URLs safely.
- Probe candidate URLs lightly and promote only verified downloadable documents.

Drop-in:
    app/services/etenders_document_url_reconstruction_v50_8_2_service.py
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode

import requests

try:
    from app.services.etenders_ajax_datatables_resolver_v50_8_1_service import (
        resolve_etenders_ajax_datatables,
    )
except Exception:  # pragma: no cover
    resolve_etenders_ajax_datatables = None


SERVICE_VERSION = "V50.8.2_ETENDERS_DOCUMENT_URL_RECONSTRUCTION"

ETENDERS_BASE = "https://www.etenders.gov.za"
DOWNLOAD_PATTERNS = [
    "/Home/DownloadSpec?documentId={tender_id}&source=sharepoint",
    "/Home/DownloadSpec?documentId={document_id}&source=sharepoint",
    "/Home/DownloadTenderDocument?documentId={tender_id}&source=sharepoint",
    "/Home/DownloadTenderDocument?documentId={document_id}&source=sharepoint",
    "/Home/DownloadFile?documentId={tender_id}&source=sharepoint",
    "/Home/DownloadFile?documentId={document_id}&source=sharepoint",
    "/Home/DownloadDocument?documentId={tender_id}&source=sharepoint",
    "/Home/DownloadDocument?documentId={document_id}&source=sharepoint",
    "/Home/DownloadSpec?documentGuid={guid}&source=sharepoint",
    "/Home/DownloadTenderDocument?documentGuid={guid}&source=sharepoint",
    "/Home/DownloadFile?documentGuid={guid}&source=sharepoint",
    "/Home/DownloadDocument?documentGuid={guid}&source=sharepoint",
    "/Home/DownloadSpec?documentId={guid}&source=sharepoint",
]

GOOD_CONTENT_HINTS = (
    "application/pdf",
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats",
    "application/vnd.ms-excel",
    "octet-stream",
)

BAD_CONTENT_HINTS = (
    "text/html",
    "application/json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_lower(value: Any) -> str:
    return _clean(value).lower()


def _row_blob(row: Any) -> str:
    if isinstance(row, (dict, list)):
        try:
            return json.dumps(row, ensure_ascii=False)
        except Exception:
            return str(row)
    return str(row or "")


def _extract_guids(text: str) -> List[str]:
    pattern = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    out: List[str] = []
    for g in re.findall(pattern, text):
        g = g.lower()
        if g not in out:
            out.append(g)
    return out


def _extract_pdf_names(text: str) -> List[str]:
    out: List[str] = []
    # keep broad but practical
    for match in re.findall(r"([A-Za-z0-9 _+\-–—(),.&/]+?\.(?:pdf|docx?|xlsx?|zip))", text, flags=re.I):
        name = _clean(match).strip(" ,;:'\"")
        if len(name) >= 8 and name not in out:
            out.append(name)
    return out


def _extract_ids(text: str) -> List[str]:
    ids: List[str] = []

    # eTenders row starts often include a numeric tender/opportunity id.
    for match in re.findall(r"\b(\d{5,8})\b", text):
        if match not in ids:
            ids.append(match)

    # documentId explicit
    for match in re.findall(r"documentId\s*[=:]\s*['\"]?(\d+)", text, flags=re.I):
        if match not in ids:
            ids.append(match)

    return ids


def _extract_row_fields(row_text: str) -> Dict[str, Any]:
    return {
        "guids": _extract_guids(row_text),
        "ids": _extract_ids(row_text),
        "filenames": _extract_pdf_names(row_text),
        "emails": sorted(set(re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", row_text))),
    }


def _build_candidate_urls(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    ids = fields.get("ids") or []
    guids = fields.get("guids") or []
    filenames = fields.get("filenames") or []

    candidates: List[Dict[str, Any]] = []
    seen = set()

    for tender_id in ids:
        for document_id in ids:
            for guid in guids or [""]:
                for pattern in DOWNLOAD_PATTERNS:
                    if "{guid}" in pattern and not guid:
                        continue
                    try:
                        path = pattern.format(
                            tender_id=tender_id,
                            document_id=document_id,
                            guid=guid,
                        )
                    except Exception:
                        continue
                    url = f"{ETENDERS_BASE}{path}"
                    if url not in seen:
                        seen.add(url)
                        candidates.append({
                            "url": url,
                            "method": "known_download_pattern",
                            "tender_id": tender_id,
                            "document_id": document_id,
                            "guid": guid,
                            "filename_hint": filenames[0] if filenames else "",
                        })

    # Filename query variants, lower confidence but useful if endpoint uses names.
    for tender_id in ids:
        for filename in filenames:
            for endpoint in [
                "/Home/DownloadSpec",
                "/Home/DownloadTenderDocument",
                "/Home/DownloadFile",
                "/Home/DownloadDocument",
            ]:
                qs = urlencode({
                    "documentId": tender_id,
                    "fileName": filename,
                    "source": "sharepoint",
                })
                url = f"{ETENDERS_BASE}{endpoint}?{qs}"
                if url not in seen:
                    seen.add(url)
                    candidates.append({
                        "url": url,
                        "method": "filename_query_variant",
                        "tender_id": tender_id,
                        "document_id": tender_id,
                        "guid": "",
                        "filename_hint": filename,
                    })

    return candidates


def _probe_url(url: str, timeout: int = 12) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146 Safari/537.36"
        ),
        "Accept": "application/pdf,application/zip,application/octet-stream,*/*",
    }

    result = {
        "url": url,
        "ok": False,
        "status_code": 0,
        "final_url": url,
        "content_type": "",
        "content_length": 0,
        "content_disposition": "",
        "verified_download": False,
        "reason": "",
    }

    try:
        # GET with stream instead of HEAD because many ASP.NET endpoints reject HEAD.
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        result["status_code"] = r.status_code
        result["final_url"] = r.url
        result["content_type"] = r.headers.get("content-type", "")
        result["content_disposition"] = r.headers.get("content-disposition", "")
        try:
            result["content_length"] = int(r.headers.get("content-length") or 0)
        except Exception:
            result["content_length"] = 0

        ctype = _safe_lower(result["content_type"])
        cdisp = _safe_lower(result["content_disposition"])

        first_bytes = b""
        try:
            first_bytes = next(r.iter_content(chunk_size=512), b"")
        except StopIteration:
            first_bytes = b""
        except Exception:
            first_bytes = b""

        byte_hint = (
            first_bytes.startswith(b"%PDF")
            or first_bytes.startswith(b"PK")
            or first_bytes.startswith(b"\xd0\xcf\x11\xe0")
        )

        good_content = any(h in ctype for h in GOOD_CONTENT_HINTS)
        bad_content = any(h in ctype for h in BAD_CONTENT_HINTS)
        attachment_hint = "attachment" in cdisp or "filename" in cdisp

        if 200 <= r.status_code < 400 and (byte_hint or attachment_hint or (good_content and not bad_content)):
            result["ok"] = True
            result["verified_download"] = True
            result["reason"] = "download_verified"
        else:
            result["reason"] = f"not_verified_content_type:{result['content_type']}"

        try:
            r.close()
        except Exception:
            pass

        return result

    except Exception as exc:
        result["reason"] = f"probe_exception:{exc}"
        return result


@dataclass
class VerifiedCandidate:
    url: str
    score: float
    reasons: List[str]
    tender_id: str
    document_id: str
    guid: str
    filename_hint: str
    probe: Dict[str, Any]


def reconstruct_etenders_document_urls(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    title = _clean(
        payload.get("title")
        or payload.get("description")
        or payload.get("buyer_rfq_number")
        or payload.get("rfq_number")
        or ""
    )

    ajax_result = payload.get("v50_8_1_ajax_resolution_result")
    if not isinstance(ajax_result, dict):
        if resolve_etenders_ajax_datatables is None:
            return {
                "status": "skipped",
                "service_version": SERVICE_VERSION,
                "resolved_at": _now(),
                "reason": "v50_8_1_resolver_unavailable",
            }
        ajax_result = resolve_etenders_ajax_datatables(payload)

    matched_rows = ajax_result.get("matched_rows") if isinstance(ajax_result.get("matched_rows"), list) else []

    reconstructed_rows: List[Dict[str, Any]] = []
    all_candidates: List[Dict[str, Any]] = []

    for row in matched_rows:
        if not isinstance(row, dict):
            continue
        score = float(row.get("match_score") or 0.0)
        if score < 0.45:
            continue

        row_text = _clean(row.get("text_preview") or "")
        if not row_text:
            row_text = _row_blob(row)

        fields = _extract_row_fields(row_text)

        # If no IDs came from preview, inspect whole row object.
        if not fields["ids"] or not fields["guids"] or not fields["filenames"]:
            full_blob = _row_blob(row)
            full_fields = _extract_row_fields(full_blob)
            fields = {
                "ids": fields["ids"] or full_fields["ids"],
                "guids": fields["guids"] or full_fields["guids"],
                "filenames": fields["filenames"] or full_fields["filenames"],
                "emails": fields["emails"] or full_fields["emails"],
            }

        candidates = _build_candidate_urls(fields)
        for c in candidates:
            c["row_match_score"] = score
            c["row_source"] = row.get("source")
            all_candidates.append(c)

        reconstructed_rows.append({
            "row_source": row.get("source"),
            "match_score": score,
            "match_hits": row.get("match_hits") or [],
            "fields": fields,
            "candidate_url_count": len(candidates),
            "text_preview": row_text[:700],
        })

    # Probe the top candidates. Put numeric id + DownloadSpec first.
    def rank_candidate(c: Dict[str, Any]) -> Tuple[int, int, int]:
        url = _safe_lower(c.get("url"))
        return (
            0 if "downloadspec" in url else 1,
            0 if c.get("method") == "known_download_pattern" else 1,
            0 if c.get("guid") else 1,
        )

    all_candidates = sorted(all_candidates, key=rank_candidate)

    verified: List[VerifiedCandidate] = []
    probed: List[Dict[str, Any]] = []

    for c in all_candidates[:25]:
        url = c["url"]
        probe = _probe_url(url)
        probed.append({**c, "probe": probe})

        if not probe.get("verified_download"):
            continue

        score = float(c.get("row_match_score") or 0.0)
        reasons = ["row_match", "download_probe_verified"]

        if c.get("guid"):
            score += 0.15
            reasons.append("guid_present")
        if c.get("filename_hint"):
            score += 0.1
            reasons.append("filename_hint_present")
        if "downloadspec" in _safe_lower(url):
            score += 0.1
            reasons.append("downloadspec_pattern")

        verified.append(VerifiedCandidate(
            url=url,
            score=round(min(score, 1.0), 4),
            reasons=reasons,
            tender_id=str(c.get("tender_id") or ""),
            document_id=str(c.get("document_id") or ""),
            guid=str(c.get("guid") or ""),
            filename_hint=str(c.get("filename_hint") or ""),
            probe=probe,
        ))

    verified = sorted(verified, key=lambda x: x.score, reverse=True)

    if verified:
        action = "promote_verified_reconstructed_document"
    elif all_candidates:
        action = "candidate_urls_reconstructed_but_not_verified"
    elif reconstructed_rows:
        action = "matched_rows_but_no_document_identifiers"
    else:
        action = "no_reconstructable_rows"

    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "resolved_at": _now(),
        "title": title,
        "ajax_status": ajax_result.get("status"),
        "ajax_recommended_action": ajax_result.get("recommended_action"),
        "matched_row_count": len(matched_rows),
        "reconstructed_row_count": len(reconstructed_rows),
        "candidate_url_count": len(all_candidates),
        "probed_candidate_count": len(probed),
        "verified_document_count": len(verified),
        "recommended_action": action,
        "safe_to_download": bool(verified),
        "recommended_document_links": [asdict(v) for v in verified[:10]],
        "reconstructed_rows": reconstructed_rows[:20],
        "probed_candidates": probed[:25],
        "notes": [
            "Only candidates from matched Ajax rows are reconstructed.",
            "A document is promoted only if the probe verifies downloadable content.",
            "If all reconstructed URLs fail, inspect probed_candidates to discover the correct eTenders endpoint pattern.",
        ],
    }


def get_v50_8_2_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "capabilities": [
            "matched_ajax_row_identifier_extraction",
            "tender_id_extraction",
            "guid_extraction",
            "filename_hint_extraction",
            "download_url_pattern_reconstruction",
            "safe_download_probe_verification",
        ],
    }
