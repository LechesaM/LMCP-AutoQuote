#!/usr/bin/env python3
import json
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")

OUTPUT_DIR = RUNTIME_DIR / "etenders_direct"
DOC_DIR = OUTPUT_DIR / "documents"
LOG_DIR = OUTPUT_DIR / "logs"

DOC_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

TENDER_FEED_FILE = LOG_DIR / "etenders_supply_delivery_feed.json"
DOWNLOAD_SUMMARY_FILE = LOG_DIR / "etenders_direct_document_download_summary.json"

BASE = "https://www.etenders.gov.za"

FEED_URL = f"{BASE}/Home/PaginatedTenderOpportunities"

# Candidate document routes. The script will test all and keep the working route.
DOCUMENT_ROUTES = [
    f"{BASE}/Home/DownloadTenderDocument",
    f"{BASE}/Home/DownloadSupportDocument",
    f"{BASE}/Home/DownloadDocument",
    f"{BASE}/Home/GetDocument",
    f"{BASE}/Home/GetSupportDocument",
    f"{BASE}/Home/DownloadFile",
]

ACCEPT_KEYWORDS = [
    "supply and delivery",
    "supply & delivery",
    "supply, delivery",
    "supply",
    "deliver",
    "delivery",
    "stationery",
    "pre-printed stationery",
    "ppe",
    "protective clothing",
    "cleaning materials",
    "cleaning material",
    "office furniture",
    "furniture",
    "equipment",
    "tools",
    "consumables",
    "chemicals",
    "spares",
    "cartridges",
    "toners",
    "paper",
    "uniform",
    "uniforms",
    "materials",
    "first aid",
    "boardroom table",
]

REJECT_KEYWORDS = [
    "construction",
    "contractor",
    "contractors",
    "cidb",
    "civil works",
    "building works",
    "turnkey",
    "professional services",
    "consulting",
    "consultancy",
    "panel of contractors",
    "maintenance",
    "repairs",
    "installation",
    "alterations",
    "infrastructure",
    "employer's representative",
    "employers representative",
    "cleaning contract",
    "security services",
    "training",
    "valuation",
    "valuer",
    "medical services",
    "flight",
    "accommodation",
    "car rental",
    "database management",
    "software development",
    "application management",
]

DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip"
}

MAX_PAGES = 10
PAGE_SIZE = 50
DELAY = 0.4


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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
    return value[:150] or "file"


def safe_slug(value):
    value = str(value or "unknown")
    value = re.sub(r"[^\w\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")[:100] or "unknown"


def clean(value):
    value = str(value or "")
    value = value.replace("&amp;", "&")
    value = value.replace("&#x27;", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def contains_any(text, keywords):
    lower = text.lower()
    return [k for k in keywords if k in lower]


def classify_supply_delivery(tender):
    description = clean(tender.get("description"))
    category = clean(tender.get("category"))
    tender_type = clean(tender.get("type"))
    department = clean(tender.get("department") or tender.get("organ_of_State"))

    blob = f"{description} {category} {tender_type} {department}".lower()

    accepts = contains_any(blob, ACCEPT_KEYWORDS)
    rejects = contains_any(blob, REJECT_KEYWORDS)

    score = len(accepts) * 10 - len(rejects) * 15

    if "supply and delivery" in blob:
        score += 40

    if "request for quotation" in blob:
        score += 20

    if "manufacture of furniture" in blob:
        score += 20

    if "services:" in category.lower() and "supply" not in blob:
        score -= 25

    hard_rejects = [
        "cidb",
        "construction",
        "panel of contractors",
        "turnkey contractor",
        "professional services",
    ]

    if any(x in blob for x in hard_rejects):
        decision = "REJECT"
    elif score >= 20 and accepts:
        decision = "ACCEPT_SUPPLY_DELIVERY"
    elif accepts and rejects:
        decision = "REVIEW_MIXED"
    else:
        decision = "REJECT"

    return {
        "decision": decision,
        "score": score,
        "accept_matches": accepts,
        "reject_matches": rejects,
    }


def datatables_params(start, length, status="1"):
    return {
        "draw": "1",
        "columns[0][data]": "department",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "true",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "description",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "closing_Date",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "true",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "order[0][column]": "2",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "status": status,
    }


def session_headers():
    return {
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote eTenders Direct Downloader",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/Home/opportunities?id=1",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }


def fetch_tender_feed(session):
    all_rows = []
    records_total = None

    warm_headers = {
        "User-Agent": session_headers()["User-Agent"],
        "Referer": f"{BASE}/Home/opportunities?id=1",
    }

    session.get(f"{BASE}/Home/opportunities?id=1", headers=warm_headers, timeout=60)

    for page in range(MAX_PAGES):
        start = page * PAGE_SIZE

        r = session.get(
            FEED_URL,
            params=datatables_params(start, PAGE_SIZE),
            headers=session_headers(),
            timeout=60,
        )

        if r.status_code != 200:
            print(f"Feed page failed start={start} status={r.status_code}")
            break

        data = r.json()

        records_total = data.get("recordsTotal")
        rows = data.get("data") or []

        print(f"Feed page {page + 1}: rows={len(rows)}")

        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE:
            break

        time.sleep(DELAY)

    accepted = []
    review = []
    rejected = []

    for row in all_rows:
        classification = classify_supply_delivery(row)

        enriched = {
            "tender_id": row.get("id"),
            "tender_no": row.get("tender_No"),
            "description": row.get("description"),
            "department": row.get("department") or row.get("organ_of_State"),
            "category": row.get("category"),
            "type": row.get("type"),
            "province": row.get("province"),
            "closing_date": row.get("closing_Date"),
            "date_published": row.get("date_Published"),
            "contact_person": row.get("contactPerson"),
            "email": row.get("email"),
            "telephone": row.get("telephone"),
            "support_documents": row.get("supportDocument") or [],
            "raw": row,
            "classification": classification,
        }

        if classification["decision"] == "ACCEPT_SUPPLY_DELIVERY":
            accepted.append(enriched)
        elif classification["decision"] == "REVIEW_MIXED":
            review.append(enriched)
        else:
            rejected.append(enriched)

    output = {
        "generated_at": now_iso(),
        "records_total": records_total,
        "rows_fetched": len(all_rows),
        "accepted_supply_delivery": len(accepted),
        "review_mixed": len(review),
        "rejected": len(rejected),
        "accepted": accepted,
        "review": review,
        "rejected_sample": rejected[:100],
    }

    write_json(TENDER_FEED_FILE, output)

    return output


def content_looks_like_document(response, body):
    content_type = (response.headers.get("content-type") or "").lower()

    if "application/pdf" in content_type:
        return True

    if "word" in content_type or "officedocument" in content_type:
        return True

    if "excel" in content_type or "spreadsheet" in content_type:
        return True

    if "zip" in content_type:
        return True

    if body.startswith(b"%PDF"):
        return True

    if body[:2] == b"PK":
        return True

    return False


def candidate_download_urls(doc, tender):
    doc_id = doc.get("supportDocumentID")
    tender_id = doc.get("tendersID") or tender.get("tender_id")
    filename = doc.get("fileName")

    candidates = []

    for route in DOCUMENT_ROUTES:
        candidates.extend([
            (route, {"id": doc_id}),
            (route, {"documentId": doc_id}),
            (route, {"supportDocumentID": doc_id}),
            (route, {"fileId": doc_id}),
            (route, {"tenderId": tender_id, "documentId": doc_id}),
            (route, {"tendersID": tender_id, "supportDocumentID": doc_id}),
            (route, {"fileName": filename, "tenderId": tender_id}),
        ])

    # Also test common direct pattern routes
    candidates.extend([
        (f"{BASE}/Home/DownloadSupportDocument/{doc_id}", {}),
        (f"{BASE}/Home/DownloadTenderDocument/{doc_id}", {}),
        (f"{BASE}/Home/DownloadDocument/{doc_id}", {}),
        (f"{BASE}/Home/GetDocument/{doc_id}", {}),
    ])

    return candidates


def download_one_document(session, tender, doc, target_dir):
    headers = {
        "User-Agent": session_headers()["User-Agent"],
        "Referer": f"{BASE}/Home/opportunities?id=1",
        "Accept": "*/*",
    }

    filename = safe_name(doc.get("fileName") or doc.get("supportDocumentID") or "document")
    suffix = Path(filename).suffix.lower()

    if suffix not in DOC_EXTENSIONS:
        ext = doc.get("extension") or ".bin"
        filename += ext

    for url, params in candidate_download_urls(doc, tender):
        try:
            r = session.get(url, params=params, headers=headers, timeout=60, allow_redirects=True)
            body = r.content or b""

            if r.status_code != 200:
                continue

            if not content_looks_like_document(r, body):
                continue

            digest = sha256_bytes(body)
            final_path = target_dir / filename

            if final_path.exists():
                final_path = target_dir / f"{final_path.stem}_{digest[:8]}{final_path.suffix}"

            with final_path.open("wb") as f:
                f.write(body)

            return {
                "success": True,
                "fileName": doc.get("fileName"),
                "supportDocumentID": doc.get("supportDocumentID"),
                "download_url": r.url,
                "path": str(final_path),
                "size_bytes": len(body),
                "sha256": digest,
                "content_type": r.headers.get("content-type"),
            }

        except Exception:
            continue

    return {
        "success": False,
        "fileName": doc.get("fileName"),
        "supportDocumentID": doc.get("supportDocumentID"),
        "error": "no_working_download_route_found",
    }


def download_documents(session, feed):
    results = []

    for tender in feed.get("accepted", []):
        tender_no = tender.get("tender_no") or str(tender.get("tender_id"))
        folder = DOC_DIR / safe_slug(tender_no)
        folder.mkdir(parents=True, exist_ok=True)

        docs = tender.get("support_documents") or []

        tender_result = {
            "tender_id": tender.get("tender_id"),
            "tender_no": tender_no,
            "description": tender.get("description"),
            "department": tender.get("department"),
            "support_document_count": len(docs),
            "downloaded": 0,
            "failed": 0,
            "folder": str(folder),
            "documents": [],
        }

        print(f"Downloading docs for {tender_no}: docs={len(docs)}")

        # Save tender metadata
        write_json(folder / "tender_metadata.json", tender)

        for doc in docs:
            result = download_one_document(session, tender, doc, folder)
            tender_result["documents"].append(result)

            if result.get("success"):
                tender_result["downloaded"] += 1
                print(f"  OK {doc.get('fileName')}")
            else:
                tender_result["failed"] += 1
                print(f"  FAIL {doc.get('fileName')}")

            time.sleep(DELAY)

        results.append(tender_result)

    summary = {
        "generated_at": now_iso(),
        "accepted_supply_delivery": len(feed.get("accepted", [])),
        "tenders_with_support_documents": sum(1 for r in results if r["support_document_count"] > 0),
        "tenders_with_downloads": sum(1 for r in results if r["downloaded"] > 0),
        "total_support_documents": sum(r["support_document_count"] for r in results),
        "total_downloaded": sum(r["downloaded"] for r in results),
        "total_failed": sum(r["failed"] for r in results),
        "results": results,
    }

    write_json(DOWNLOAD_SUMMARY_FILE, summary)

    return summary


def main():
    with requests.Session() as session:
        print("Fetching eTenders structured feed...")
        feed = fetch_tender_feed(session)

        print("\nFeed summary:")
        print(f"Rows fetched: {feed['rows_fetched']}")
        print(f"Accepted supply/delivery: {feed['accepted_supply_delivery']}")
        print(f"Review mixed: {feed['review_mixed']}")

        print("\nDownloading accepted support documents...")
        summary = download_documents(session, feed)

    print(f"\nDirect download summary: {DOWNLOAD_SUMMARY_FILE}")
    print(f"Accepted supply/delivery: {summary['accepted_supply_delivery']}")
    print(f"Tenders with support docs: {summary['tenders_with_support_documents']}")
    print(f"Tenders with downloads: {summary['tenders_with_downloads']}")
    print(f"Total support docs: {summary['total_support_documents']}")
    print(f"Downloaded: {summary['total_downloaded']}")
    print(f"Failed: {summary['total_failed']}")


if __name__ == "__main__":
    main()
