#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
FETCH_DIR = RUNTIME_DIR / "portal_fetch"
SNAPSHOT_DIR = FETCH_DIR / "actionable_snapshots"
OUTPUT_FILE = FETCH_DIR / "logs" / "actionable_snapshot_parse.json"

LINK_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)
TEXT_RE = re.compile(r"<[^>]+>")

TENDER_HINTS = [
    "tender",
    "quotation",
    "rfq",
    "bid",
    "contract",
    "closing",
    "download",
    "document",
    "briefing",
    "status",
]

DOC_HINTS = [
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip",
    "download", "document", "boq", "bill", "schedule", "returnable"
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def base_url_for(path):
    name = path.name.lower()

    if "etenders_gov_za" in name:
        return "https://www.etenders.gov.za"

    if "nra_co_za" in name:
        return "https://www.nra.co.za"

    return ""


def clean_text(html):
    text = TEXT_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def looks_tender_related(text):
    lower = text.lower()
    return any(h in lower for h in TENDER_HINTS)


def looks_document_link(url):
    lower = url.lower()
    return any(h in lower for h in DOC_HINTS)


def extract_links(html, base_url):
    links = []

    for m in LINK_RE.finditer(html):
        raw = m.group(1).strip()

        if not raw or raw.startswith("#") or raw.startswith("javascript:") or raw.startswith("mailto:"):
            continue

        url = urljoin(base_url, raw)

        links.append({
            "raw": raw,
            "url": url,
            "is_document_candidate": looks_document_link(url),
        })

    seen = set()
    out = []

    for item in links:
        if item["url"] in seen:
            continue

        seen.add(item["url"])
        out.append(item)

    return out


def extract_table_like_rows(html):
    rows = []

    tr_blocks = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S)

    for block in tr_blocks:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", block, re.I | re.S)

        cleaned = [clean_text(c) for c in cells]
        cleaned = [c for c in cleaned if c]

        if not cleaned:
            continue

        joined = " | ".join(cleaned)

        if looks_tender_related(joined):
            rows.append({
                "cells": cleaned,
                "text": joined,
            })

    return rows


def parse_snapshot(path):
    html = path.read_text(encoding="utf-8", errors="ignore")
    base_url = base_url_for(path)

    text = clean_text(html)
    links = extract_links(html, base_url)
    rows = extract_table_like_rows(html)

    document_links = [x for x in links if x["is_document_candidate"]]

    return {
        "snapshot": str(path),
        "base_url": base_url,
        "text_preview": text[:1500],
        "link_count": len(links),
        "document_link_count": len(document_links),
        "tender_row_count": len(rows),
        "document_links": document_links,
        "tender_rows": rows[:100],
    }


def main():
    snapshots = sorted(SNAPSHOT_DIR.glob("*"))

    parsed = []

    for path in snapshots:
        if path.suffix.lower() not in {".html", ".json"}:
            continue

        print(f"Parsing {path.name}")
        parsed.append(parse_snapshot(path))

    output = {
        "generated_at": now_iso(),
        "snapshot_count": len(parsed),
        "total_document_links": sum(x["document_link_count"] for x in parsed),
        "total_tender_rows": sum(x["tender_row_count"] for x in parsed),
        "snapshots": parsed,
    }

    write_json(OUTPUT_FILE, output)

    print(f"\nParsed snapshot output: {OUTPUT_FILE}")
    print(f"Snapshots parsed: {output['snapshot_count']}")
    print(f"Document links: {output['total_document_links']}")
    print(f"Tender rows: {output['total_tender_rows']}")


if __name__ == "__main__":
    main()
