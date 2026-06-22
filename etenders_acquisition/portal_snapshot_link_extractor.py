#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
FETCH_DIR = RUNTIME_DIR / "portal_fetch"
SNAPSHOT_DIR = FETCH_DIR / "snapshots"
OUTPUT_FILE = FETCH_DIR / "logs" / "portal_snapshot_links.json"

LINK_RE = re.compile(
    r"""href=["']([^"']+)["']|src=["']([^"']+)["']""",
    re.IGNORECASE,
)

DOC_EXTENSIONS = [
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip"
]

DETAIL_HINTS = [
    "tender",
    "opportunity",
    "rfq",
    "bid",
    "quotation",
    "notice",
    "view",
    "details",
]

DOC_HINTS = [
    "download",
    "document",
    "attachment",
    "boq",
    "bill",
    "schedule",
    "pricing",
    "returnable",
    "bid document",
    "tender document",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def guess_base_url(snapshot_path):
    name = snapshot_path.name

    if name.startswith("www_etenders_gov_za"):
        return "https://www.etenders.gov.za"

    if name.startswith("www_nra_co_za"):
        return "https://www.nra.co.za"

    if name.startswith("data_etenders_gov_za"):
        return "https://data.etenders.gov.za"

    return ""


def classify_link(url):
    lower = url.lower()
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()

    if suffix in DOC_EXTENSIONS:
        return "document"

    if any(hint in lower for hint in DOC_HINTS):
        return "document_candidate"

    if any(hint in lower for hint in DETAIL_HINTS):
        return "detail_candidate"

    return "other"


def extract_links_from_html(path):
    html = path.read_text(encoding="utf-8", errors="ignore")
    base_url = guess_base_url(path)

    links = []

    for match in LINK_RE.finditer(html):
        raw = match.group(1) or match.group(2)

        if not raw:
            continue

        raw = raw.strip()

        if raw.startswith("#") or raw.startswith("javascript:") or raw.startswith("mailto:"):
            continue

        absolute = urljoin(base_url, raw) if base_url else raw

        links.append({
            "raw": raw,
            "url": absolute,
            "classification": classify_link(absolute),
        })

    # de-duplicate
    seen = set()
    unique = []

    for link in links:
        if link["url"] in seen:
            continue
        seen.add(link["url"])
        unique.append(link)

    return unique


def main():
    snapshots = sorted(SNAPSHOT_DIR.glob("*.html"))

    output_items = []
    totals = {
        "snapshots": len(snapshots),
        "links": 0,
        "document": 0,
        "document_candidate": 0,
        "detail_candidate": 0,
        "other": 0,
    }

    for snapshot in snapshots:
        links = extract_links_from_html(snapshot)

        counts = {
            "document": 0,
            "document_candidate": 0,
            "detail_candidate": 0,
            "other": 0,
        }

        for link in links:
            cls = link["classification"]
            counts[cls] = counts.get(cls, 0) + 1
            totals[cls] = totals.get(cls, 0) + 1

        totals["links"] += len(links)

        output_items.append({
            "snapshot": str(snapshot),
            "base_url": guess_base_url(snapshot),
            "link_count": len(links),
            "counts": counts,
            "links": links,
        })

    output = {
        "generated_at": now_iso(),
        "summary": totals,
        "snapshots": output_items,
    }

    write_json(OUTPUT_FILE, output)

    print(f"Portal snapshot link extraction written: {OUTPUT_FILE}")
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
