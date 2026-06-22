#!/usr/bin/env python3
import json
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, quote_plus

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

SUPPLY_INDEX_FILE = (
    RUNTIME_DIR /
    "manual_production" /
    "supply_delivery_quote_packs" /
    "supply_delivery_quote_pack_index.json"
)

ACTIONABLE_PARSE_FILE = (
    RUNTIME_DIR /
    "portal_fetch" /
    "logs" /
    "actionable_snapshot_parse.json"
)

OUTPUT_FILE = (
    RUNTIME_DIR /
    "manual_production" /
    "supply_delivery_quote_packs" /
    "tender_detail_resolver_summary.json"
)

TIMEOUT = 45
DELAY = 0.8

LINK_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)

ASSET_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".woff", ".woff2", ".ttf", ".map"
}

DOC_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip"
}

BAD_LINK_HINTS = [
    "privacy",
    "paia",
    "scam-alert",
    "favicon",
    "logo",
    "facebook",
    "twitter",
    "linkedin",
    "contact",
    "about",
    "login",
    "identity/account",
    "css/",
    "js/",
    "images/",
]

DETAIL_HINTS = [
    "detail",
    "details",
    "view",
    "tender",
    "quotation",
    "rfq",
    "bid",
    "opportunity",
    "status",
]

DOCUMENT_HINTS = [
    "document",
    "download",
    "attachment",
    "bid",
    "tender",
    "quotation",
    "rfq",
    "boq",
    "bill",
    "pricing",
    "schedule",
    "returnable",
    "specification",
    "scope",
]


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
    return value[:140] or "file"


def normalize_text(value):
    value = str(value or "")
    value = value.replace("&#x27;", "'")
    value = value.replace("&amp;", "&")
    value = value.replace("&#xD;", " ")
    value = value.replace("&#xA;", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def tokenize(value):
    words = re.findall(r"[A-Za-z0-9]{4,}", normalize_text(value).lower())
    stop = {
        "with", "from", "that", "this", "there", "their",
        "period", "months", "contract", "provision", "supply",
        "delivery", "tender", "quotation"
    }
    return [w for w in words if w not in stop]


def is_asset_or_bad(url):
    lower = url.lower()
    suffix = Path(urlparse(url).path).suffix.lower()

    if suffix in ASSET_EXTENSIONS:
        return True

    return any(h in lower for h in BAD_LINK_HINTS)


def is_document_url(url):
    lower = url.lower()
    suffix = Path(urlparse(url).path).suffix.lower()

    return suffix in DOC_EXTENSIONS or any(h in lower for h in DOCUMENT_HINTS)


def is_detail_url(url):
    lower = url.lower()

    if is_asset_or_bad(url):
        return False

    if is_document_url(url):
        return False

    return any(h in lower for h in DETAIL_HINTS)


def extract_links(html, base_url):
    links = []

    for m in LINK_RE.finditer(html or ""):
        raw = m.group(1).strip()

        if not raw or raw.startswith("#") or raw.startswith("javascript:") or raw.startswith("mailto:"):
            continue

        url = urljoin(base_url, raw)

        if is_asset_or_bad(url):
            continue

        links.append(url)

    return sorted(set(links))


def fetch(session, url):
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        return r
    except Exception as e:
        return e


def score_link_for_pack(url, pack):
    desc = normalize_text(pack.get("description", "")).lower()
    dept = normalize_text(pack.get("department", "")).lower()
    blob = f"{url.lower()}"

    score = 0

    for token in tokenize(desc)[:12]:
        if token in blob:
            score += 10

    for token in tokenize(dept)[:6]:
        if token in blob:
            score += 5

    if is_detail_url(url):
        score += 15

    if "status" in blob:
        score += 5

    if "quotation" in blob or "rfq" in blob:
        score += 15

    if "tender" in blob:
        score += 10

    return score


def collect_seed_links_from_snapshots():
    data = load_json(ACTIONABLE_PARSE_FILE, default={})
    links = set()

    for snapshot in data.get("snapshots", []):
        base = snapshot.get("base_url") or ""

        for item in snapshot.get("document_links", []):
            url = item.get("url")
            if url:
                links.add(url)

        for row in snapshot.get("tender_rows", []):
            raw = row.get("text", "")
            if raw:
                pass

        # Re-read snapshot file to capture hrefs not preserved in table rows
        snap_path = snapshot.get("snapshot")
        if snap_path and Path(snap_path).exists():
            html = Path(snap_path).read_text(encoding="utf-8", errors="ignore")
            for url in extract_links(html, base):
                if is_detail_url(url) or is_document_url(url):
                    links.add(url)

    return sorted(links)


def build_search_urls(pack):
    desc = normalize_text(pack.get("description", ""))
    dept = normalize_text(pack.get("department", ""))

    terms = [
        desc,
        f"{dept} {desc}",
        " ".join(tokenize(desc)[:8]),
    ]

    urls = []

    for term in terms:
        if not term:
            continue

        q = quote_plus(term)

        urls.extend([
            f"https://www.etenders.gov.za/Home/opportunities?id=1&search={q}",
            f"https://www.nra.co.za/sanral-tenders/status?search={q}",
            f"https://www.nra.co.za/sanral-quotations/status?search={q}",
        ])

    return urls


def download_document(session, url, attachments_dir):
    result = fetch(session, url)

    if isinstance(result, Exception):
        return {
            "url": url,
            "success": False,
            "error": str(result),
        }

    r = result

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

    # reject HTML masquerading as document unless URL has real doc extension
    suffix = Path(urlparse(url).path).suffix.lower()
    if "text/html" in content_type and suffix not in DOC_EXTENSIONS:
        return {
            "url": url,
            "success": False,
            "status_code": r.status_code,
            "content_type": content_type,
            "error": "html_not_document",
        }

    filename = Path(urlparse(url).path).name or "document"

    if "." not in filename:
        if "pdf" in content_type:
            filename += ".pdf"
        elif "spreadsheet" in content_type or "excel" in content_type:
            filename += ".xlsx"
        elif "word" in content_type:
            filename += ".docx"
        elif "zip" in content_type:
            filename += ".zip"
        else:
            filename += ".bin"

    digest = sha256_bytes(body)
    final_path = attachments_dir / safe_name(filename)

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


def resolve_pack(session, pack, seed_links):
    pack_dir = Path(pack["pack_dir"])
    details_dir = pack_dir / "detail_pages"
    attachments_dir = pack_dir / "attachments_resolved"

    details_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir.mkdir(parents=True, exist_ok=True)

    scored = []

    for url in seed_links:
        scored.append({
            "url": url,
            "score": score_link_for_pack(url, pack),
        })

    scored = sorted(scored, key=lambda x: x["score"], reverse=True)
    candidate_detail_links = [x for x in scored if x["score"] >= 10 and is_detail_url(x["url"])][:20]
    candidate_doc_links = [x for x in scored if is_document_url(x["url"]) and x["score"] >= 5][:20]

    # Add search URLs as fallback detail pages
    for url in build_search_urls(pack):
        candidate_detail_links.append({
            "url": url,
            "score": 5,
        })

    fetched_details = []
    discovered_documents = set()

    for item in candidate_detail_links[:25]:
        url = item["url"]
        result = fetch(session, url)

        detail_record = {
            "url": url,
            "score": item["score"],
            "success": False,
            "status_code": None,
            "snapshot_path": None,
            "discovered_documents": [],
        }

        if not isinstance(result, Exception):
            detail_record["status_code"] = result.status_code

            if result.status_code == 200 and result.content:
                content_type = result.headers.get("content-type", "").lower()

                if "text/html" in content_type or "html" in content_type:
                    digest = sha256_bytes(result.content)
                    snap_name = safe_name(f"detail_{digest[:10]}.html")
                    snap_path = details_dir / snap_name

                    with snap_path.open("wb") as f:
                        f.write(result.content)

                    links = extract_links(result.text, url)
                    docs = [x for x in links if is_document_url(x) and not is_asset_or_bad(x)]

                    for d in docs:
                        discovered_documents.add(d)

                    detail_record["success"] = True
                    detail_record["snapshot_path"] = str(snap_path)
                    detail_record["discovered_documents"] = docs

        fetched_details.append(detail_record)
        time.sleep(DELAY)

    for item in candidate_doc_links:
        discovered_documents.add(item["url"])

    downloads = []

    for url in sorted(discovered_documents):
        if is_asset_or_bad(url):
            continue

        dl = download_document(session, url, attachments_dir)
        downloads.append(dl)
        time.sleep(DELAY)

    manifest = {
        "generated_at": now_iso(),
        "pack_id": pack.get("pack_id"),
        "rfq_id": pack.get("rfq_id"),
        "department": pack.get("department"),
        "description": pack.get("description"),
        "candidate_detail_links": candidate_detail_links[:25],
        "candidate_doc_links": candidate_doc_links,
        "fetched_details": fetched_details,
        "discovered_document_links": sorted(discovered_documents),
        "downloads": downloads,
        "download_count": sum(1 for x in downloads if x.get("success")),
        "failed_download_count": sum(1 for x in downloads if not x.get("success")),
    }

    manifest_path = pack_dir / "detail_resolver_manifest.json"
    write_json(manifest_path, manifest)

    return {
        "pack_id": pack.get("pack_id"),
        "rfq_id": pack.get("rfq_id"),
        "department": pack.get("department"),
        "description": pack.get("description"),
        "candidate_detail_links": len(candidate_detail_links),
        "detail_pages_fetched": sum(1 for x in fetched_details if x.get("success")),
        "discovered_document_links": len(discovered_documents),
        "downloaded": manifest["download_count"],
        "failed": manifest["failed_download_count"],
        "manifest_path": str(manifest_path),
    }


def main():
    supply_index = load_json(SUPPLY_INDEX_FILE, default={})
    packs = supply_index.get("packs", [])

    seed_links = collect_seed_links_from_snapshots()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote Tender Detail Resolver",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
    })

    results = []

    print(f"Seed links collected: {len(seed_links)}")

    for pack in packs:
        print(f"Resolving: {pack.get('department')} | {pack.get('description')[:80]}")
        result = resolve_pack(session, pack, seed_links)
        results.append(result)

        print(
            f"  details={result['detail_pages_fetched']} "
            f"docs={result['discovered_document_links']} "
            f"downloaded={result['downloaded']}"
        )

    output = {
        "generated_at": now_iso(),
        "seed_links": len(seed_links),
        "total_supply_packs": len(packs),
        "packs_with_detail_pages": sum(1 for r in results if r["detail_pages_fetched"] > 0),
        "packs_with_documents": sum(1 for r in results if r["downloaded"] > 0),
        "total_discovered_document_links": sum(r["discovered_document_links"] for r in results),
        "total_downloaded": sum(r["downloaded"] for r in results),
        "results": results,
    }

    write_json(OUTPUT_FILE, output)

    print(f"\nTender detail resolver complete: {OUTPUT_FILE}")
    print(f"Packs: {output['total_supply_packs']}")
    print(f"With details: {output['packs_with_detail_pages']}")
    print(f"With docs: {output['packs_with_documents']}")
    print(f"Downloaded: {output['total_downloaded']}")


if __name__ == "__main__":
    main()
