from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, unquote
import hashlib
import json
import re
import zipfile

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


ENGINE_VERSION = "RFQ_DOCUMENT_ACQUISITION_ENGINE_V1"

RUNTIME_DIR = Path("runtime/rfq_document_acquisition")
DOWNLOAD_DIR = RUNTIME_DIR / "downloads"
REPORT_DIR = RUNTIME_DIR / "reports"

DEFAULT_TIMEOUT_SECONDS = 30
MAX_LINKS_PER_PAGE = 120
MAX_DOWNLOADS_PER_RFQ = 25
MAX_FILE_SIZE_BYTES = 80 * 1024 * 1024

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
}

REJECT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".mp4",
    ".mp3",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

PRIORITY_TERMS = [
    "pricing schedule",
    "bill of quantities",
    "boq",
    "pricing",
    "schedule",
    "annexure",
    "annex",
    "sbd",
    "specification",
    "specifications",
    "terms of reference",
    "tor",
    "scope of work",
    "returnable",
    "returnables",
    "quotation",
    "rfq",
    "bid document",
    "tender document",
]

BOQ_TERMS = [
    "boq",
    "bill of quantities",
    "pricing schedule",
    "price schedule",
    "schedule of prices",
    "quotation schedule",
]

PRICING_TERMS = [
    "pricing",
    "price schedule",
    "pricing schedule",
    "schedule of prices",
    "quotation schedule",
]

SBD_TERMS = [
    "sbd",
    "standard bidding document",
    "preference points",
    "declaration of interest",
]

SPEC_TERMS = [
    "specification",
    "specifications",
    "scope of work",
    "terms of reference",
    "tor",
    "technical",
]

REJECT_URL_TERMS = [
    "logo",
    "favicon",
    "facebook",
    "twitter",
    "linkedin",
    "instagram",
    "youtube",
    "wp-content/uploads/logo",
    "header",
    "footer",
    "banner",
    "icon",
    "image",
    "newsletter",
    "privacy-policy",
    "terms-and-conditions",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _slug(value: Any, limit: int = 100) -> str:
    text = _safe_str(value)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return (text[:limit].strip("-") or "rfq-document")


def _ensure_dirs() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        cleaned = _safe_str(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _extension_from_url(url: str) -> str:
    path = unquote(urlparse(url).path or "")
    suffix = Path(path).suffix.lower()
    return suffix


def _extension_from_content_type(content_type: str) -> str:
    ct = _safe_lower(content_type)
    if "pdf" in ct:
        return ".pdf"
    if "zip" in ct or "compressed" in ct:
        return ".zip"
    if "spreadsheet" in ct or "excel" in ct:
        return ".xlsx"
    if "wordprocessingml" in ct or "msword" in ct:
        return ".docx"
    if "csv" in ct:
        return ".csv"
    return ""


def _looks_like_rejected_asset(url: str, link_text: str = "") -> bool:
    blob = f"{url} {link_text}".lower()
    ext = _extension_from_url(url)

    if ext in REJECT_EXTENSIONS:
        return True

    if any(term in blob for term in REJECT_URL_TERMS):
        return True

    return False


def _looks_like_downloadable_document(url: str, link_text: str = "") -> bool:
    ext = _extension_from_url(url)
    blob = f"{url} {link_text}".lower()

    if ext in SUPPORTED_EXTENSIONS:
        return True

    if any(term in blob for term in PRIORITY_TERMS):
        return True

    if "download" in blob or "attachment" in blob or "document" in blob:
        return True

    return False


def _document_score(url: str, link_text: str = "", content_type: str = "") -> Tuple[float, List[str]]:
    blob = f"{unquote(url)} {link_text} {content_type}".lower()
    ext = _extension_from_url(url) or _extension_from_content_type(content_type)

    score = 0.0
    reasons: List[str] = []

    if ext in SUPPORTED_EXTENSIONS:
        score += 0.25
        reasons.append(f"supported_extension:{ext}")

    if ext in {".pdf", ".docx", ".xlsx", ".xls", ".zip"}:
        score += 0.10
        reasons.append("high_value_file_type")

    for term in PRIORITY_TERMS:
        if term in blob:
            score += 0.08
            reasons.append(f"priority_term:{term}")

    if any(term in blob for term in BOQ_TERMS):
        score += 0.20
        reasons.append("boq_candidate")

    if any(term in blob for term in PRICING_TERMS):
        score += 0.15
        reasons.append("pricing_candidate")

    if any(term in blob for term in SBD_TERMS):
        score += 0.12
        reasons.append("sbd_candidate")

    if any(term in blob for term in SPEC_TERMS):
        score += 0.12
        reasons.append("specification_candidate")

    if "download" in blob:
        score += 0.06
        reasons.append("download_signal")

    if "tender" in blob or "rfq" in blob or "bid" in blob:
        score += 0.06
        reasons.append("procurement_signal")

    if _looks_like_rejected_asset(url, link_text):
        score -= 0.60
        reasons.append("rejected_asset_signal")

    return round(max(0.0, min(score, 1.0)), 4), reasons


def _extract_seed_urls(item: Dict[str, Any]) -> List[str]:
    if not isinstance(item, dict):
        return []

    urls: List[str] = []
    for key in ("document_url", "source_url", "detail_url", "pdf_url", "download_url", "attachment_url", "tender_document_url"):
        value = item.get(key)
        if isinstance(value, list):
            urls.extend(_safe_str(v) for v in value)
        else:
            urls.append(_safe_str(value))

    for key in ("documents", "attachments", "links"):
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for inner_key in ("url", "href", "download_url", "document_url"):
                        urls.append(_safe_str(entry.get(inner_key)))
                else:
                    urls.append(_safe_str(entry))
        elif isinstance(value, dict):
            for inner_key in ("url", "href", "download_url", "document_url"):
                urls.append(_safe_str(value.get(inner_key)))

    return [u for u in _unique_preserve_order(urls) if _is_http_url(u)]


def _http_get(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Optional[Any]:
    if requests is None:
        return None

    headers = {
        "User-Agent": "LMCP-AutoQuote Document Acquisition/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf,application/zip,*/*;q=0.8",
    }

    try:
        return requests.get(url, timeout=timeout_seconds, headers=headers, allow_redirects=True, stream=False)
    except Exception:
        return None


def _extract_links_from_html(html: str, base_url: str) -> List[Dict[str, str]]:
    if not html:
        return []

    links: List[Dict[str, str]] = []

    # Anchor tags
    for match in re.finditer(r"<a\b([^>]*)>(.*?)</a>", html, flags=re.I | re.S):
        attrs = match.group(1) or ""
        body = match.group(2) or ""

        href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.I)
        if not href_match:
            continue

        href = href_match.group(1).strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:") or href.lower().startswith("mailto:"):
            continue

        text = re.sub(r"<[^>]+>", " ", body)
        text = re.sub(r"\s+", " ", text).strip()

        full_url = urljoin(base_url, href)
        if _is_http_url(full_url):
            links.append({"url": full_url, "text": text})

    # Direct file URLs embedded in page text
    file_pattern = r'https?://[^\s"\'<>]+(?:\.pdf|\.zip|\.docx?|\.xlsx?|\.csv)(?:\?[^\s"\'<>]*)?'
    for m in re.finditer(file_pattern, html, flags=re.I):
        full_url = m.group(0)
        if _is_http_url(full_url):
            links.append({"url": full_url, "text": ""})

    # Relative direct file links not inside anchors
    relative_pattern = r'["\']([^"\']+\.(?:pdf|zip|docx?|xlsx?|csv)(?:\?[^"\']*)?)["\']'
    for m in re.finditer(relative_pattern, html, flags=re.I):
        full_url = urljoin(base_url, m.group(1))
        if _is_http_url(full_url):
            links.append({"url": full_url, "text": ""})

    unique: List[Dict[str, str]] = []
    seen = set()
    for link in links:
        key = link["url"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(link)

    return unique[:MAX_LINKS_PER_PAGE]


def crawl_rfq_document_links(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    seeds = _extract_seed_urls(item)
    discovered: List[Dict[str, Any]] = []

    for seed in seeds:
        if _looks_like_rejected_asset(seed):
            continue

        ext = _extension_from_url(seed)
        seed_score, seed_reasons = _document_score(seed, "")

        if ext in SUPPORTED_EXTENSIONS:
            discovered.append({
                "url": seed,
                "source_page": seed,
                "link_text": "",
                "score": seed_score,
                "reasons": seed_reasons,
                "direct_seed_document": True,
            })
            continue

        response = _http_get(seed, timeout_seconds=timeout_seconds)
        if response is None:
            discovered.append({
                "url": seed,
                "source_page": seed,
                "link_text": "",
                "score": 0.0,
                "reasons": ["crawl_failed"],
                "crawl_status": "failed",
            })
            continue

        content_type = response.headers.get("content-type", "")
        ext_from_type = _extension_from_content_type(content_type)

        if ext_from_type in SUPPORTED_EXTENSIONS:
            score, reasons = _document_score(str(response.url or seed), "", content_type)
            discovered.append({
                "url": str(response.url or seed),
                "source_page": seed,
                "link_text": "",
                "score": score,
                "reasons": reasons,
                "direct_seed_document": True,
                "content_type": content_type,
            })
            continue

        html = ""
        try:
            html = response.text or ""
        except Exception:
            html = ""

        for link in _extract_links_from_html(html, str(response.url or seed)):
            url = link["url"]
            text = link.get("text", "")

            if _looks_like_rejected_asset(url, text):
                continue

            if not _looks_like_downloadable_document(url, text):
                continue

            score, reasons = _document_score(url, text)
            if score <= 0.05:
                continue

            discovered.append({
                "url": url,
                "source_page": seed,
                "link_text": text,
                "score": score,
                "reasons": reasons,
                "direct_seed_document": False,
            })

    # Dedupe and rank
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for entry in discovered:
        url = entry.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(entry)

    deduped.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)

    return {
        "seed_urls": seeds,
        "discovered_links": deduped,
        "discovered_count": len(deduped),
    }


def _safe_filename_from_url(url: str, content_type: str = "", title: str = "") -> str:
    parsed = urlparse(url)
    path_name = Path(unquote(parsed.path or "")).name
    path_name = re.sub(r"[^A-Za-z0-9._ -]+", "-", path_name).strip(" .-")

    ext = Path(path_name).suffix.lower()
    if not ext:
        ext = _extension_from_content_type(content_type) or ".bin"

    base = Path(path_name).stem if path_name else _slug(title or url)
    base = re.sub(r"[^A-Za-z0-9._ -]+", "-", base).strip(" .-") or _slug(title or url)

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{base[:80]}__{digest}{ext}"


def download_candidate_document(candidate: Dict[str, Any], title: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    _ensure_dirs()

    url = _safe_str(candidate.get("url"))
    if not _is_http_url(url):
        return {"status": "failed", "url": url, "error": "invalid_url"}

    if requests is None:
        return {"status": "failed", "url": url, "error": "requests_not_available"}

    headers = {
        "User-Agent": "LMCP-AutoQuote Document Acquisition/1.0",
        "Accept": "application/pdf,application/zip,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,*/*;q=0.8",
    }

    try:
        response = requests.get(url, timeout=timeout_seconds, headers=headers, allow_redirects=True, stream=True)
        status_code = int(response.status_code)
        content_type = response.headers.get("content-type", "")
        content_length = int(response.headers.get("content-length") or 0)

        if status_code >= 400:
            return {
                "status": "failed",
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "error": "http_error",
            }

        if content_length and content_length > MAX_FILE_SIZE_BYTES:
            return {
                "status": "failed",
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "size_bytes": content_length,
                "error": "file_too_large",
            }

        content = response.content
        if len(content) > MAX_FILE_SIZE_BYTES:
            return {
                "status": "failed",
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "size_bytes": len(content),
                "error": "file_too_large",
            }

        ext = _extension_from_url(str(response.url or url)) or _extension_from_content_type(content_type)
        if ext in REJECT_EXTENSIONS:
            return {
                "status": "rejected",
                "url": url,
                "content_type": content_type,
                "extension": ext,
                "error": "rejected_asset_extension",
            }

        filename = _safe_filename_from_url(str(response.url or url), content_type, title)
        path = DOWNLOAD_DIR / _slug(title)
        path.mkdir(parents=True, exist_ok=True)
        file_path = path / filename
        file_path.write_bytes(content)

        result = {
            "status": "downloaded",
            "url": url,
            "final_url": str(response.url),
            "path": str(file_path),
            "filename": filename,
            "extension": file_path.suffix.lower(),
            "content_type": content_type,
            "status_code": status_code,
            "size_bytes": len(content),
            "score": float(candidate.get("score") or 0.0),
            "reasons": candidate.get("reasons") if isinstance(candidate.get("reasons"), list) else [],
            "link_text": _safe_str(candidate.get("link_text")),
            "source_page": _safe_str(candidate.get("source_page")),
        }

        if file_path.suffix.lower() == ".zip":
            result["zip_members"] = _inspect_zip_members(file_path)

        return result

    except Exception as exc:
        return {
            "status": "failed",
            "url": url,
            "error": str(exc),
        }


def _inspect_zip_members(path: Path) -> List[Dict[str, Any]]:
    members: List[Dict[str, Any]] = []
    try:
        with zipfile.ZipFile(path, "r") as z:
            for info in z.infolist()[:100]:
                name = info.filename
                ext = Path(name).suffix.lower()
                if ext in REJECT_EXTENSIONS:
                    continue
                score, reasons = _document_score(name, name)
                members.append({
                    "filename": name,
                    "extension": ext,
                    "size_bytes": info.file_size,
                    "score": score,
                    "reasons": reasons,
                })
    except Exception:
        return []
    return members


def _categorise_download(download: Dict[str, Any]) -> Dict[str, bool]:
    blob = " ".join([
        _safe_lower(download.get("filename")),
        _safe_lower(download.get("url")),
        _safe_lower(download.get("link_text")),
        " ".join(_safe_lower(r) for r in (download.get("reasons") or [])),
    ])

    zip_members = download.get("zip_members") if isinstance(download.get("zip_members"), list) else []
    for member in zip_members:
        blob += " " + _safe_lower(member.get("filename"))
        blob += " " + " ".join(_safe_lower(r) for r in (member.get("reasons") or []))

    return {
        "boq_candidate": any(term in blob for term in BOQ_TERMS),
        "pricing_schedule": any(term in blob for term in PRICING_TERMS),
        "sbd": any(term in blob for term in SBD_TERMS),
        "specification": any(term in blob for term in SPEC_TERMS),
    }


def _filter_by_category(downloads: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for d in downloads:
        if d.get("status") != "downloaded":
            continue
        cats = _categorise_download(d)
        if cats.get(category):
            out.append(d)
    out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return out


def acquire_rfq_documents(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Main entry point for REAL BUYER DOCUMENT ACQUISITION ENGINE.

    It crawls only URLs already present on the RFQ item, discovers downloadable
    tender documents, downloads prioritized candidates, and classifies the files
    for downstream document intelligence and BOQ extraction.
    """
    _ensure_dirs()

    if not isinstance(item, dict):
        item = {}

    title = _safe_str(item.get("title") or item.get("buyer_rfq_number") or "rfq")

    crawl = crawl_rfq_document_links(item, timeout_seconds=timeout_seconds)
    candidates = crawl.get("discovered_links") if isinstance(crawl.get("discovered_links"), list) else []

    prioritized_candidates = [
        c for c in candidates
        if float(c.get("score") or 0.0) >= 0.12
    ][:MAX_DOWNLOADS_PER_RFQ]

    downloaded_files: List[Dict[str, Any]] = []
    for candidate in prioritized_candidates:
        downloaded_files.append(download_candidate_document(candidate, title, timeout_seconds=timeout_seconds))

    successful_downloads = [d for d in downloaded_files if d.get("status") == "downloaded"]

    prioritized_documents = sorted(
        successful_downloads,
        key=lambda x: float(x.get("score") or 0.0),
        reverse=True,
    )

    boq_candidate_files = _filter_by_category(successful_downloads, "boq_candidate")
    pricing_schedule_files = _filter_by_category(successful_downloads, "pricing_schedule")
    sbd_files = _filter_by_category(successful_downloads, "sbd")
    specification_files = _filter_by_category(successful_downloads, "specification")

    confidence = 0.0
    if successful_downloads:
        confidence += 0.35
    if boq_candidate_files:
        confidence += 0.25
    if pricing_schedule_files:
        confidence += 0.20
    if specification_files:
        confidence += 0.10
    if sbd_files:
        confidence += 0.05
    if len(successful_downloads) >= 2:
        confidence += 0.05

    confidence = round(min(confidence, 1.0), 4)

    result: Dict[str, Any] = {
        "status": "ok" if successful_downloads else "no_documents_downloaded",
        "engine_version": ENGINE_VERSION,
        "acquired_at": _now_iso(),
        "title": title,
        "buyer_name": _safe_str(item.get("buyer_name")),
        "buyer_rfq_number": _safe_str(item.get("buyer_rfq_number")),
        "confidence": confidence,
        "seed_urls": crawl.get("seed_urls", []),
        "discovered_count": crawl.get("discovered_count", 0),
        "download_attempt_count": len(downloaded_files),
        "downloaded_count": len(successful_downloads),
        "downloaded_files": downloaded_files,
        "prioritized_documents": prioritized_documents,
        "boq_candidate_files": boq_candidate_files,
        "pricing_schedule_files": pricing_schedule_files,
        "sbd_files": sbd_files,
        "specification_files": specification_files,
    }

    report_path = REPORT_DIR / f"{_slug(title)}__document_acquisition_report.json"
    report_path.write_text(json.dumps(result, indent=2, default=str))
    result["report_path"] = str(report_path)

    return result


def acquire_documents_for_rfq(item: Dict[str, Any], timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Alias for API compatibility.
    """
    return acquire_rfq_documents(item, timeout_seconds=timeout_seconds)


def get_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "runtime_dir": str(RUNTIME_DIR),
        "download_dir": str(DOWNLOAD_DIR),
        "report_dir": str(REPORT_DIR),
        "capabilities": [
            "crawl_rfq_seed_urls",
            "discover_pdf_zip_docx_xlsx_csv_links",
            "reject_navigation_assets_logos_media",
            "prioritize_boq_pricing_schedule_annexure_sbd_specification",
            "download_prioritized_documents",
            "inspect_zip_members",
            "classify_boq_candidate_files",
            "classify_pricing_schedule_files",
            "classify_sbd_files",
            "classify_specification_files",
            "confidence_scoring",
            "write_json_report",
        ],
    }
