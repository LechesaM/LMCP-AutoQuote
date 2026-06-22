#!/usr/bin/env python3
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
FETCH_DIR = RUNTIME_DIR / "portal_fetch"
INPUT_FILE = FETCH_DIR / "logs" / "portal_actionable_links.json"
SNAPSHOT_DIR = FETCH_DIR / "actionable_snapshots"
OUTPUT_FILE = FETCH_DIR / "logs" / "portal_actionable_fetch_report.json"

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 45
DELAY = 0.8


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


def safe_slug(value):
    return (
        value.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "_")
        .replace(":", "_")
        .replace(".", "_")
    )[:120]


def classify_failure(status_code, text):
    lower = (text or "").lower()

    if status_code == 403:
        return "http_403"

    if status_code == 404:
        return "http_404"

    if status_code and status_code >= 500:
        return "http_5xx"

    if "captcha" in lower or "cloudflare" in lower or "access denied" in lower:
        return "anti_bot"

    if status_code != 200:
        return "http_error"

    if not text:
        return "empty_body"

    return None


def fetch_url(session, item):
    url = item["url"]

    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        body = r.content or b""
        text = body[:5000].decode("utf-8", errors="ignore")
        failure = classify_failure(r.status_code, text)

        snapshot_path = None
        digest = None

        if r.status_code == 200 and not failure and body:
            digest = sha256_bytes(body)
            content_type = r.headers.get("content-type", "").lower()

            suffix = ".html"
            if "json" in content_type:
                suffix = ".json"
            elif "pdf" in content_type:
                suffix = ".pdf"

            filename = f"{safe_slug(url)}_{digest[:10]}{suffix}"
            snapshot_path = SNAPSHOT_DIR / filename

            with snapshot_path.open("wb") as f:
                f.write(body)

        return {
            "url": url,
            "classification": item.get("classification"),
            "success": snapshot_path is not None,
            "status_code": r.status_code,
            "content_type": r.headers.get("content-type"),
            "bytes": len(body),
            "failure": failure,
            "snapshot_path": str(snapshot_path) if snapshot_path else None,
            "sha256": digest,
        }

    except Exception as e:
        return {
            "url": url,
            "classification": item.get("classification"),
            "success": False,
            "status_code": None,
            "content_type": None,
            "bytes": 0,
            "failure": "exception",
            "error": str(e),
            "snapshot_path": None,
            "sha256": None,
        }


def main():
    data = load_json(INPUT_FILE, default={})
    links = data.get("links", [])

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 LMCP-AutoQuote Portal Action Fetcher",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-ZA,en;q=0.9",
    })

    results = []

    for item in links:
        print(f"Fetching actionable: {item['url']}")
        result = fetch_url(session, item)
        results.append(result)

        print(
            f"  success={result['success']} "
            f"status={result['status_code']} "
            f"failure={result['failure']}"
        )

        time.sleep(DELAY)

    output = {
        "generated_at": now_iso(),
        "total_links": len(links),
        "success_count": sum(1 for r in results if r["success"]),
        "failure_count": sum(1 for r in results if not r["success"]),
        "results": results,
    }

    write_json(OUTPUT_FILE, output)

    print(f"\nActionable fetch report written: {OUTPUT_FILE}")
    print(f"Success: {output['success_count']}")
    print(f"Failed: {output['failure_count']}")


if __name__ == "__main__":
    main()
