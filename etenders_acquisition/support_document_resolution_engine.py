#!/usr/bin/env python3
import json
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

INPUT_FILE = RUNTIME_DIR / "ajax_tender_feed" / "supply_delivery_tenders.json"
OUT_DIR = RUNTIME_DIR / "support_document_resolution"
DOC_DIR = OUT_DIR / "documents"
LOG_FILE = OUT_DIR / "support_document_resolution_summary.json"

BASE = "https://www.etenders.gov.za"
DOWNLOAD_URL = f"{BASE}/home/Download/"

DELAY = 0.2
MAX_TENDERS = None

DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip", ".msg"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_slug(value):
    value = str(value or "unknown")
    value = re.sub(r"[^\w\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")[:120] or "unknown"


def safe_name(value):
    value = str(value or "document")
    value = re.sub(r"[^\w\-.() ]+", "_", value)
    value = value.strip("._ ")
    return value[:180] or "document"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def ensure_extension(filename, extension):
    filename = str(filename or "document")
    extension = str(extension or "").strip()

    if not extension.startswith(".") and extension:
        extension = "." + extension

    if Path(filename).suffix:
        return filename

    return filename + (extension or ".bin")


def looks_like_document(response, body):
    ct = (response.headers.get("content-type") or "").lower()

    if response.status_code != 200 or not body:
        return False

    if body.startswith(b"%PDF"):
        return True

    if body[:2] == b"PK":
        return True

    if body[:8].startswith(b"\xd0\xcf\x11\xe0"):
        return True

    if any(
        x in ct
        for x in [
            "application/pdf",
            "application/msword",
            "officedocument",
            "spreadsheet",
            "excel",
            "zip",
            "octet-stream",
        ]
    ):
        return True

    return False


def build_download_url(doc):
    support_id = doc.get("supportDocumentID")
    extension = doc.get("extension") or Path(doc.get("fileName") or "").suffix
    filename = ensure_extension(doc.get("fileName"), extension)

    if not support_id:
        return None

    if extension and not extension.startswith("."):
        extension = "." + extension

    blob_name = f"{support_id}{extension}"

    query = urlencode(
        {
            "blobName": blob_name,
            "downloadedFileName": filename,
        }
    )

    return f"{DOWNLOAD_URL}?{query}"


def download_one_document(session, tender, doc, target_dir):
    filename = ensure_extension(doc.get("fileName"), doc.get("extension"))
    filename = safe_name(filename)

    url = build_download_url(doc)

    if not url:
        return {
            "success": False,
            "fileName": doc.get("fileName"),
            "supportDocumentID": doc.get("supportDocumentID"),
            "error": "missing_supportDocumentID",
        }

    headers = {
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote Support Document Downloader",
        "Referer": f"{BASE}/Home/opportunities?id=1",
        "Accept": "*/*",
    }

    try:
        r = session.get(url, headers=headers, timeout=90, allow_redirects=True)
        body = r.content or b""

        if not looks_like_document(r, body):
            return {
                "success": False,
                "fileName": doc.get("fileName"),
                "supportDocumentID": doc.get("supportDocumentID"),
                "status": r.status_code,
                "content_type": r.headers.get("content-type"),
                "content_length": len(body),
                "url": r.url,
                "signature_hex": body[:16].hex(),
                "error_preview": (r.text[:500] if body else ""),
            }

        digest = sha256_bytes(body)
        out_path = target_dir / filename

        if out_path.exists():
            out_path = target_dir / f"{out_path.stem}_{digest[:8]}{out_path.suffix}"

        with out_path.open("wb") as f:
            f.write(body)

        return {
            "success": True,
            "fileName": doc.get("fileName"),
            "supportDocumentID": doc.get("supportDocumentID"),
            "download_url": r.url,
            "path": str(out_path),
            "size_bytes": len(body),
            "sha256": digest,
            "content_type": r.headers.get("content-type"),
            "content_disposition": r.headers.get("content-disposition"),
        }

    except Exception as e:
        return {
            "success": False,
            "fileName": doc.get("fileName"),
            "supportDocumentID": doc.get("supportDocumentID"),
            "url": url,
            "error": str(e),
        }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    data = load_json(INPUT_FILE, default={})
    tenders = data.get("accepted", [])

    if MAX_TENDERS:
        tenders = tenders[:MAX_TENDERS]

    session = requests.Session()
    session.get(
        f"{BASE}/Home/opportunities?id=1",
        headers={"User-Agent": "Mozilla/5.0 LMCP-AutoQuote Support Document Downloader"},
        timeout=60,
    )

    results = []

    for tender in tenders:
        tender_no = tender.get("tender_no") or str(tender.get("tender_id"))
        tender_dir = DOC_DIR / safe_slug(tender_no)
        tender_dir.mkdir(parents=True, exist_ok=True)

        docs = tender.get("support_documents") or []

        print(f"Downloading {tender_no}: docs={len(docs)}")

        tender_result = {
            "tender_id": tender.get("tender_id"),
            "tender_no": tender_no,
            "description": tender.get("description"),
            "department": tender.get("department"),
            "support_document_count": len(docs),
            "downloaded": 0,
            "failed": 0,
            "folder": str(tender_dir),
            "documents": [],
        }

        write_json(tender_dir / "tender_metadata.json", tender)

        for doc in docs:
            res = download_one_document(session, tender, doc, tender_dir)
            tender_result["documents"].append(res)

            if res.get("success"):
                tender_result["downloaded"] += 1
                print(f"  OK   {doc.get('fileName')}")
            else:
                tender_result["failed"] += 1
                print(f"  FAIL {doc.get('fileName')}")

            time.sleep(DELAY)

        results.append(tender_result)

    summary = {
        "generated_at": now_iso(),
        "mode": "direct_blobname_download",
        "tenders_processed": len(results),
        "tenders_with_downloads": sum(1 for r in results if r["downloaded"] > 0),
        "total_support_documents": sum(r["support_document_count"] for r in results),
        "total_downloaded": sum(r["downloaded"] for r in results),
        "total_failed": sum(r["failed"] for r in results),
        "results": results,
    }

    write_json(LOG_FILE, summary)

    print(f"\nSupport document download summary: {LOG_FILE}")
    print(f"Tenders processed: {summary['tenders_processed']}")
    print(f"Tenders with downloads: {summary['tenders_with_downloads']}")
    print(f"Support docs: {summary['total_support_documents']}")
    print(f"Downloaded: {summary['total_downloaded']}")
    print(f"Failed: {summary['total_failed']}")


if __name__ == "__main__":
    main()
