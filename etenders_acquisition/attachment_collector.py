#!/usr/bin/env python3
import json
import re
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
QUOTE_PACK_INDEX_FILE = RUNTIME_DIR / "manual_production" / "quote_pack_index.json"
OUTPUT_FILE = RUNTIME_DIR / "manual_production" / "attachment_collection_summary.json"

DOWNLOAD_TIMEOUT = 45
REQUEST_DELAY_SECONDS = 0.5

VALID_DOC_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip"
}

URL_KEYS = [
    "url",
    "link",
    "href",
    "download_url",
    "document_url",
    "attachment_url",
    "file_url",
    "tender_url",
    "source_url",
]

DOC_HINTS = [
    "download",
    "document",
    "attachment",
    "pdf",
    "xlsx",
    "xls",
    "docx",
    "doc",
    "zip",
    "boq",
    "bill",
    "schedule",
    "bid document",
    "tender document",
]


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


def safe_name(value):
    value = str(value or "file")
    value = re.sub(r"[^\w\-.() ]+", "_", value)
    value = value.strip("._ ")
    return value or "file"


def file_hash(content):
    return hashlib.sha256(content).hexdigest()


def extension_from_url(url):
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix


def looks_like_document_url(url):
    lower = str(url).lower()

    if extension_from_url(url) in VALID_DOC_EXTENSIONS:
        return True

    return any(hint in lower for hint in DOC_HINTS)


def collect_urls(obj, found=None):
    if found is None:
        found = set()

    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = str(key).lower()

            if isinstance(value, str):
                value_strip = value.strip()

                if value_strip.startswith("http://") or value_strip.startswith("https://"):
                    if key_lower in URL_KEYS or looks_like_document_url(value_strip):
                        found.add(value_strip)

            collect_urls(value, found)

    elif isinstance(obj, list):
        for item in obj:
            collect_urls(item, found)

    elif isinstance(obj, str):
        for match in re.findall(r"https?://[^\s\"'<>]+", obj):
            if looks_like_document_url(match):
                found.add(match)

    return found


def guess_filename(url, response):
    parsed = urlparse(url)
    name = Path(parsed.path).name

    content_disposition = response.headers.get("content-disposition", "")

    match = re.search(r'filename="?([^"]+)"?', content_disposition, re.I)
    if match:
        name = match.group(1)

    if not name or "." not in name:
        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type:
            name = "document.pdf"
        elif "spreadsheet" in content_type or "excel" in content_type:
            name = "document.xlsx"
        elif "word" in content_type:
            name = "document.docx"
        elif "zip" in content_type:
            name = "documents.zip"
        else:
            name = "document.bin"

    return safe_name(name)


def download_file(url, target_dir):
    headers = {
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote attachment collector",
        "Accept": "*/*",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=DOWNLOAD_TIMEOUT,
            allow_redirects=True,
        )

        status = response.status_code
        content_type = response.headers.get("content-type", "")

        if status != 200:
            return {
                "url": url,
                "success": False,
                "status_code": status,
                "error": f"http_{status}",
            }

        content = response.content or b""

        if len(content) == 0:
            return {
                "url": url,
                "success": False,
                "status_code": status,
                "error": "empty_body",
            }

        digest = file_hash(content)
        filename = guess_filename(url, response)

        suffix = Path(filename).suffix.lower()
        if suffix not in VALID_DOC_EXTENSIONS:
            if "pdf" in content_type.lower():
                filename += ".pdf"
            elif "zip" in content_type.lower():
                filename += ".zip"

        final_path = target_dir / filename

        if final_path.exists():
            final_path = target_dir / f"{final_path.stem}_{digest[:8]}{final_path.suffix}"

        with final_path.open("wb") as f:
            f.write(content)

        return {
            "url": url,
            "success": True,
            "status_code": status,
            "content_type": content_type,
            "filename": final_path.name,
            "path": str(final_path),
            "size_bytes": len(content),
            "sha256": digest,
        }

    except Exception as e:
        return {
            "url": url,
            "success": False,
            "error": str(e),
        }


def main():
    index = load_json(QUOTE_PACK_INDEX_FILE, default={})
    packs = index.get("packs", [])

    total_urls_found = 0
    total_downloaded = 0
    total_failed = 0
    pack_results = []

    for pack in packs:
        tender_id = pack.get("tender_id", "UNKNOWN")
        pack_dir = Path(pack.get("pack_dir", ""))

        if not pack_dir:
            continue

        pack_dir.mkdir(parents=True, exist_ok=True)

        quote_summary_path = Path(pack.get("quote_summary_path", ""))
        quote_summary = load_json(quote_summary_path, default={})

        urls = set()
        urls.update(collect_urls(pack))
        urls.update(collect_urls(quote_summary))

        urls = sorted([u for u in urls if looks_like_document_url(u)])

        attachments_dir = pack_dir / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "tender_id": tender_id,
            "pack_dir": str(pack_dir),
            "attachment_urls_found": len(urls),
            "downloads": [],
        }

        for url in urls:
            result = download_file(url, attachments_dir)
            manifest["downloads"].append(result)

            total_urls_found += 1

            if result.get("success"):
                total_downloaded += 1
            else:
                total_failed += 1

            time.sleep(REQUEST_DELAY_SECONDS)

        manifest_path = pack_dir / "attachment_manifest.json"
        write_json(manifest_path, manifest)

        pack_results.append({
            "tender_id": tender_id,
            "pack_dir": str(pack_dir),
            "attachment_urls_found": len(urls),
            "downloaded": sum(1 for x in manifest["downloads"] if x.get("success")),
            "failed": sum(1 for x in manifest["downloads"] if not x.get("success")),
            "manifest_path": str(manifest_path),
        })

        if urls:
            print(
                f"{tender_id}: urls={len(urls)} "
                f"downloaded={pack_results[-1]['downloaded']} "
                f"failed={pack_results[-1]['failed']}"
            )

    summary = {
        "total_packs": len(packs),
        "total_urls_found": total_urls_found,
        "total_downloaded": total_downloaded,
        "total_failed": total_failed,
        "packs": pack_results,
    }

    write_json(OUTPUT_FILE, summary)

    print("\nAttachment collection complete")
    print(f"Total packs: {len(packs)}")
    print(f"URLs found: {total_urls_found}")
    print(f"Downloaded: {total_downloaded}")
    print(f"Failed: {total_failed}")
    print(f"Summary: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
