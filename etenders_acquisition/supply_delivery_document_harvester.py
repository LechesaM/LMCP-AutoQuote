#!/usr/bin/env python3
import json
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SUPPLY_INDEX_FILE = (
    RUNTIME_DIR /
    "manual_production" /
    "supply_delivery_quote_packs" /
    "supply_delivery_quote_pack_index.json"
)

OUTPUT_FILE = (
    RUNTIME_DIR /
    "manual_production" /
    "supply_delivery_quote_packs" /
    "supply_delivery_document_harvest_summary.json"
)

TIMEOUT = 45
DELAY = 1.0

SEARCH_ENDPOINTS = [
    "https://www.etenders.gov.za/Home/opportunities?id=1",
    "https://www.nra.co.za/sanral-tenders/status",
    "https://www.nra.co.za/sanral-quotations/status",
]

DOC_HINTS = [
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip",
    "download", "document", "boq", "bill", "schedule", "returnable",
    "tender document", "bid document", "quotation"
]

LINK_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(value):
    value = str(value or "file")
    value = re.sub(r"[^\w\-.() ]+", "_", value)
    value = value.strip("._ ")
    return value[:120] or "file"


def looks_document_url(url):
    lower = url.lower()
    return any(h in lower for h in DOC_HINTS)


def build_search_terms(pack):
    description = pack.get("description", "")
    department = pack.get("department", "")

    words = re.findall(r"[A-Za-z0-9]{4,}", description)
    strong_words = words[:8]

    return [
        description,
        f"{department} {description}",
        " ".join(strong_words),
    ]


def fetch(session, url):
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        return r
    except Exception:
        return None


def extract_document_links(html, base_url):
    found = []

    for m in LINK_RE.finditer(html or ""):
        raw = m.group(1).strip()

        if not raw or raw.startswith("#") or raw.startswith("javascript:"):
            continue

        if raw.startswith("http"):
            url = raw
        elif raw.startswith("/"):
            root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
            url = root + raw
        else:
            url = base_url.rstrip("/") + "/" + raw.lstrip("/")

        if looks_document_url(url):
            found.append(url)

    return sorted(set(found))


def download_document(session, url, attachments_dir):
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)

        if r.status_code != 200:
            return {
                "url": url,
                "success": False,
                "status_code": r.status_code,
                "error": f"http_{r.status_code}",
            }

        body = r.content or b""

        if not body:
            return {
                "url": url,
                "success": False,
                "status_code": r.status_code,
                "error": "empty_body",
            }

        content_type = r.headers.get("content-type", "").lower()

        parsed_name = Path(urlparse(url).path).name
        filename = safe_name(parsed_name)

        if "." not in filename:
            if "pdf" in content_type:
                filename += ".pdf"
            elif "zip" in content_type:
                filename += ".zip"
            elif "excel" in content_type or "spreadsheet" in content_type:
                filename += ".xlsx"
            else:
                filename += ".bin"

        digest = sha256_bytes(body)
        final_path = attachments_dir / filename

        if final_path.exists():
            final_path = attachments_dir / f"{final_path.stem}_{digest[:8]}{final_path.suffix}"

        with final_path.open("wb") as f:
            f.write(body)

        return {
            "url": url,
            "success": True,
            "status_code": r.status_code,
            "content_type": content_type,
            "path": str(final_path),
            "filename": final_path.name,
            "size_bytes": len(body),
            "sha256": digest,
        }

    except Exception as e:
        return {
            "url": url,
            "success": False,
            "error": str(e),
        }


def harvest_for_pack(session, pack):
    pack_dir = Path(pack["pack_dir"])
    attachments_dir = pack_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    search_terms = build_search_terms(pack)

    candidate_links = set()
    fetch_attempts = []

    for endpoint in SEARCH_ENDPOINTS:
        for term in search_terms:
            # conservative query variations
            urls_to_try = [
                endpoint,
                f"{endpoint}?search={quote_plus(term)}",
                f"{endpoint}&search={quote_plus(term)}" if "?" in endpoint else f"{endpoint}?search={quote_plus(term)}",
            ]

            for url in urls_to_try:
                r = fetch(session, url)

                attempt = {
                    "url": url,
                    "status_code": r.status_code if r is not None else None,
                    "bytes": len(r.content or b"") if r is not None else 0,
                }

                fetch_attempts.append(attempt)

                if r is not None and r.status_code == 200:
                    html = r.text
                    links = extract_document_links(html, url)

                    for link in links:
                        candidate_links.add(link)

                time.sleep(DELAY)

    downloads = []

    for link in sorted(candidate_links):
        result = download_document(session, link, attachments_dir)
        downloads.append(result)
        time.sleep(DELAY)

    manifest = {
        "generated_at": now_iso(),
        "pack_id": pack.get("pack_id"),
        "rfq_id": pack.get("rfq_id"),
        "department": pack.get("department"),
        "description": pack.get("description"),
        "candidate_document_links": sorted(candidate_links),
        "download_count": sum(1 for d in downloads if d.get("success")),
        "failed_download_count": sum(1 for d in downloads if not d.get("success")),
        "downloads": downloads,
        "fetch_attempts": fetch_attempts[:50],
    }

    manifest_path = pack_dir / "attachment_manifest.json"
    write_json(manifest_path, manifest)

    return {
        "pack_id": pack.get("pack_id"),
        "rfq_id": pack.get("rfq_id"),
        "department": pack.get("department"),
        "description": pack.get("description"),
        "pack_dir": str(pack_dir),
        "candidate_document_links": len(candidate_links),
        "downloaded": manifest["download_count"],
        "failed": manifest["failed_download_count"],
        "manifest_path": str(manifest_path),
    }


def main():
    index = load_json(SUPPLY_INDEX_FILE, default={})
    packs = index.get("packs", [])

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote Supply Document Harvester",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
    })

    results = []

    for pack in packs:
        print(f"Harvesting docs: {pack.get('department')} | {pack.get('description')[:80]}")
        result = harvest_for_pack(session, pack)
        results.append(result)

        print(
            f"  candidates={result['candidate_document_links']} "
            f"downloaded={result['downloaded']} "
            f"failed={result['failed']}"
        )

    summary = {
        "generated_at": now_iso(),
        "total_supply_packs": len(packs),
        "packs_with_document_candidates": sum(1 for r in results if r["candidate_document_links"] > 0),
        "packs_with_downloads": sum(1 for r in results if r["downloaded"] > 0),
        "total_document_candidates": sum(r["candidate_document_links"] for r in results),
        "total_downloaded": sum(r["downloaded"] for r in results),
        "total_failed": sum(r["failed"] for r in results),
        "results": results,
    }

    write_json(OUTPUT_FILE, summary)

    print(f"\nSupply document harvest complete: {OUTPUT_FILE}")
    print(f"Packs: {summary['total_supply_packs']}")
    print(f"With candidates: {summary['packs_with_document_candidates']}")
    print(f"With downloads: {summary['packs_with_downloads']}")
    print(f"Downloaded: {summary['total_downloaded']}")


if __name__ == "__main__":
    main()
