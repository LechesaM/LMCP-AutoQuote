#!/usr/bin/env python3
import json
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
OUT_DIR = RUNTIME_DIR / "ajax_tender_feed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEED_FILE = OUT_DIR / "ajax_tender_feed.json"
SUPPLY_FILE = OUT_DIR / "supply_delivery_tenders.json"
SUMMARY_FILE = OUT_DIR / "ajax_tender_feed_summary.json"

BASE = "https://www.etenders.gov.za"
FEED_URL = f"{BASE}/Home/PaginatedTenderOpportunities"

PAGE_SIZE = 100
MAX_PAGES = 30
DELAY = 0.4

ACCEPT_KEYWORDS = [
    "supply and delivery", "supply & delivery", "supply, delivery",
    "supply", "deliver", "delivery", "stationery", "ppe",
    "protective clothing", "cleaning materials", "office furniture",
    "furniture", "equipment", "tools", "consumables", "chemicals",
    "spares", "cartridges", "toners", "paper", "uniforms",
    "materials", "first aid", "boardroom table",
]

REJECT_KEYWORDS = [
    "construction", "contractor", "contractors", "cidb",
    "civil works", "building works", "turnkey", "professional services",
    "consulting", "consultancy", "panel of contractors", "maintenance",
    "repairs", "installation", "alterations", "infrastructure",
    "security services", "training", "valuation", "medical services",
    "accommodation", "car rental", "software development",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean(value):
    value = str(value or "")
    value = value.replace("&amp;", "&").replace("&#x27;", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def contains_any(text, keywords):
    lower = text.lower()
    return [k for k in keywords if k in lower]


def classify_supply_delivery(row):
    description = clean(row.get("description"))
    category = clean(row.get("category"))
    tender_type = clean(row.get("type"))
    department = clean(row.get("department") or row.get("organ_of_State"))

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


def datatables_params(start, length):
    return {
        "draw": "1",
        "columns[0][data]": "",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "false",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",

        "columns[1][data]": "category",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",

        "columns[2][data]": "description",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "false",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",

        "columns[3][data]": "eSubmission",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",

        "columns[4][data]": "date_Published",
        "columns[4][name]": "",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "true",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",

        "columns[5][data]": "closing_Date",
        "columns[5][name]": "",
        "columns[5][searchable]": "true",
        "columns[5][orderable]": "true",
        "columns[5][search][value]": "",
        "columns[5][search][regex]": "false",

        "columns[6][data]": "actions",
        "columns[6][name]": "",
        "columns[6][searchable]": "true",
        "columns[6][orderable]": "true",
        "columns[6][search][value]": "",
        "columns[6][search][regex]": "false",

        "order[0][column]": "2",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "status": "1",
    }


def headers():
    return {
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote AJAX Harvester",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/Home/opportunities?id=1",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }


def normalize_row(row):
    support_docs = row.get("supportDocument") or []

    return {
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
        "delivery": row.get("delivery"),
        "e_submission": row.get("eSubmission"),
        "briefing_session": row.get("briefingSession"),
        "briefing_compulsory": row.get("briefingCompulsory"),
        "support_document_count": len(support_docs),
        "support_documents": support_docs,
        "classification": classify_supply_delivery(row),
        "raw": row,
    }


def main():
    session = requests.Session()
    session.get(
        f"{BASE}/Home/opportunities?id=1",
        headers={"User-Agent": headers()["User-Agent"]},
        timeout=60,
    )

    all_rows = []
    records_total = None

    for page in range(MAX_PAGES):
        start = page * PAGE_SIZE

        r = session.get(
            FEED_URL,
            params=datatables_params(start, PAGE_SIZE),
            headers=headers(),
            timeout=60,
        )

        if r.status_code != 200:
            print(f"FAILED page={page + 1} status={r.status_code}")
            break

        data = r.json()
        rows = data.get("data") or []
        records_total = data.get("recordsTotal")

        print(f"Page {page + 1}: fetched={len(rows)} start={start}")

        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE:
            break

        time.sleep(DELAY)

    normalized = [normalize_row(r) for r in all_rows]

    accepted = [
        r for r in normalized
        if r["classification"]["decision"] == "ACCEPT_SUPPLY_DELIVERY"
    ]

    review = [
        r for r in normalized
        if r["classification"]["decision"] == "REVIEW_MIXED"
    ]

    rejected = [
        r for r in normalized
        if r["classification"]["decision"] == "REJECT"
    ]

    feed = {
        "generated_at": now_iso(),
        "records_total": records_total,
        "rows_fetched": len(normalized),
        "tenders": normalized,
    }

    supply = {
        "generated_at": now_iso(),
        "records_total": records_total,
        "rows_fetched": len(normalized),
        "accepted_supply_delivery": len(accepted),
        "review_mixed": len(review),
        "rejected": len(rejected),
        "accepted": accepted,
        "review": review,
        "rejected_sample": rejected[:100],
    }

    summary = {
        "generated_at": now_iso(),
        "records_total": records_total,
        "rows_fetched": len(normalized),
        "accepted_supply_delivery": len(accepted),
        "review_mixed": len(review),
        "rejected": len(rejected),
        "support_documents_total": sum(r["support_document_count"] for r in normalized),
        "accepted_support_documents": sum(r["support_document_count"] for r in accepted),
    }

    write_json(FEED_FILE, feed)
    write_json(SUPPLY_FILE, supply)
    write_json(SUMMARY_FILE, summary)

    print("\nAJAX tender feed harvest complete")
    print(f"Rows fetched: {summary['rows_fetched']}")
    print(f"Accepted supply/delivery: {summary['accepted_supply_delivery']}")
    print(f"Review mixed: {summary['review_mixed']}")
    print(f"Accepted support docs: {summary['accepted_support_documents']}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
