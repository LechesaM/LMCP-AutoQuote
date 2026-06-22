#!/usr/bin/env python3
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
INPUT_FILE = RUNTIME_DIR / "portal_fetch" / "logs" / "portal_snapshot_links.json"
OUTPUT_FILE = RUNTIME_DIR / "portal_fetch" / "logs" / "portal_actionable_links.json"

ASSET_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".woff", ".woff2", ".ttf", ".map"
}

DOCUMENT_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip"
}

BAD_KEYWORDS = [
    "favicon",
    "logo",
    "header",
    "footer",
    "privacy",
    "paia",
    "contact",
    "about",
    "vision",
    "mission",
    "mandate",
    "login",
    "identity/account",
    "css/",
    "js/",
    "images/",
]

ETENDERS_ACTION_HINTS = [
    "/home/opportunities",
    "opportunities?id=",
    "tender",
    "bid",
    "rfq",
]

SANRAL_ACTION_HINTS = [
    "/sanral-tenders/status",
    "/sanral-quotations/status",
    "/sanral-downloads/detail",
    "/sanral-tenders",
    "/sanral-quotations",
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


def is_asset(url):
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()

    if suffix in ASSET_EXTENSIONS:
        return True

    lower = url.lower()

    return any(k in lower for k in BAD_KEYWORDS)


def is_document(url):
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix in DOCUMENT_EXTENSIONS


def classify_actionable(url):
    lower = url.lower()
    host = urlparse(url).netloc.lower()

    if is_asset(url):
        return None

    if is_document(url):
        return "document"

    if "etenders.gov.za" in host:
        if any(h in lower for h in ETENDERS_ACTION_HINTS):
            return "etenders_listing_or_detail"

    if "nra.co.za" in host:
        if any(h in lower for h in SANRAL_ACTION_HINTS):
            return "sanral_listing_or_detail"

    return None


def main():
    data = load_json(INPUT_FILE, default={})

    actionable = []
    counts = {}

    for snapshot in data.get("snapshots", []):
        for link in snapshot.get("links", []):
            url = link.get("url")

            if not url:
                continue

            classification = classify_actionable(url)

            if not classification:
                continue

            counts[classification] = counts.get(classification, 0) + 1

            actionable.append({
                "url": url,
                "classification": classification,
                "source_snapshot": snapshot.get("snapshot"),
                "base_url": snapshot.get("base_url"),
            })

    # deduplicate
    seen = set()
    deduped = []

    for item in actionable:
        if item["url"] in seen:
            continue

        seen.add(item["url"])
        deduped.append(item)

    output = {
        "generated_at": now_iso(),
        "total_actionable_links": len(deduped),
        "counts": counts,
        "links": deduped,
    }

    write_json(OUTPUT_FILE, output)

    print(f"Actionable link file written: {OUTPUT_FILE}")
    print(json.dumps({
        "total_actionable_links": len(deduped),
        "counts": counts,
    }, indent=2))


if __name__ == "__main__":
    main()
