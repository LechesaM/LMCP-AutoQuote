#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


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
    "browser_acquisition_summary.json"
)

BROWSER_RUNTIME_DIR = RUNTIME_DIR / "browser_acquisition"
BROWSER_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT_MS = 45000

PORTAL_URLS = [
    "https://www.etenders.gov.za/Home/opportunities?id=1",
    "https://www.nra.co.za/sanral-tenders/status",
    "https://www.nra.co.za/sanral-quotations/status",
]

DOCUMENT_HINTS = [
    "download",
    "document",
    "attachment",
    "rfq",
    "quotation",
    "tender",
    "bid",
    "boq",
    "bill",
    "pricing",
    "schedule",
    "returnable",
    "specification",
    "scope",
]

BAD_HINTS = [
    "privacy",
    "paia",
    "scam",
    "facebook",
    "twitter",
    "linkedin",
    "login",
    "logo",
    "favicon",
]

DOC_EXTENSIONS = [
    ".pdf",
    ".xlsx",
    ".xls",
    ".csv",
    ".docx",
    ".doc",
    ".zip",
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


def normalize(value):
    value = str(value or "")
    value = value.replace("&amp;", "&")
    value = value.replace("&#x27;", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def tokens(value):
    words = re.findall(r"[A-Za-z0-9]{4,}", normalize(value).lower())
    stop = {
        "with", "from", "that", "this", "there", "their",
        "period", "months", "contract", "provision",
        "supply", "delivery", "tender", "quotation",
        "services", "service"
    }
    return [w for w in words if w not in stop]


def looks_bad(url_or_text):
    lower = str(url_or_text or "").lower()
    return any(h in lower for h in BAD_HINTS)


def looks_document(url_or_text):
    lower = str(url_or_text or "").lower()

    if looks_bad(lower):
        return False

    if any(ext in lower for ext in DOC_EXTENSIONS):
        return True

    return any(h in lower for h in DOCUMENT_HINTS)


def score_for_pack(text, pack):
    blob = normalize(text).lower()
    score = 0

    for t in tokens(pack.get("description", ""))[:14]:
        if t in blob:
            score += 10

    for t in tokens(pack.get("department", ""))[:6]:
        if t in blob:
            score += 5

    if looks_document(blob):
        score += 20

    if "supply" in blob:
        score += 10

    if "delivery" in blob:
        score += 10

    return score


def save_html_snapshot(page, pack_dir, label):
    html = page.content()
    digest = sha256_bytes(html.encode("utf-8"))
    path = pack_dir / "browser_snapshots" / f"{label}_{digest[:10]}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def collect_dom_links(page, pack):
    links = []

    anchors = page.locator("a").all()

    for a in anchors:
        try:
            href = a.get_attribute("href") or ""
            text = normalize(a.inner_text(timeout=1000))
            combined = f"{text} {href}"

            if not href:
                continue

            if looks_bad(combined):
                continue

            score = score_for_pack(combined, pack)

            if score <= 0:
                continue

            links.append({
                "text": text,
                "href": href,
                "score": score,
                "is_document_candidate": looks_document(combined),
            })

        except Exception:
            continue

    links = sorted(links, key=lambda x: x["score"], reverse=True)

    seen = set()
    unique = []

    for link in links:
        key = link["href"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(link)

    return unique


def collect_buttons(page, pack):
    buttons = []

    selectors = [
        "button",
        "input[type=button]",
        "input[type=submit]",
        "[role=button]",
    ]

    for selector in selectors:
        locators = page.locator(selector).all()

        for b in locators:
            try:
                text = normalize(
                    b.inner_text(timeout=1000)
                    if selector != "input[type=button]" and selector != "input[type=submit]"
                    else b.get_attribute("value")
                )

                if not text:
                    continue

                if looks_bad(text):
                    continue

                score = score_for_pack(text, pack)

                if score <= 0:
                    continue

                buttons.append({
                    "selector": selector,
                    "text": text,
                    "score": score,
                    "is_document_candidate": looks_document(text),
                })

            except Exception:
                continue

    return sorted(buttons, key=lambda x: x["score"], reverse=True)


def save_download(download, target_dir):
    suggested = safe_name(download.suggested_filename or "download.bin")
    path = target_dir / suggested

    if path.exists():
        path = target_dir / f"{path.stem}_{datetime.now().strftime('%H%M%S')}{path.suffix}"

    download.save_as(str(path))

    data = path.read_bytes()

    return {
        "success": True,
        "filename": path.name,
        "path": str(path),
        "size_bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def browser_resolve_pack(context, pack):
    pack_dir = Path(pack["pack_dir"])
    attachments_dir = pack_dir / "browser_downloads"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    page = context.new_page()
    page.set_default_timeout(TIMEOUT_MS)

    result = {
        "pack_id": pack.get("pack_id"),
        "rfq_id": pack.get("rfq_id"),
        "department": pack.get("department"),
        "description": pack.get("description"),
        "visited_pages": [],
        "dom_links": [],
        "buttons": [],
        "downloads": [],
        "errors": [],
    }

    search_text = pack.get("description", "")

    for portal_url in PORTAL_URLS:
        try:
            page.goto(portal_url, wait_until="networkidle", timeout=TIMEOUT_MS)

            snapshot = save_html_snapshot(
                page,
                pack_dir,
                safe_name(urlparse(portal_url).netloc)
            )

            result["visited_pages"].append({
                "url": portal_url,
                "snapshot": snapshot,
                "title": page.title(),
            })

            # try search boxes
            search_inputs = page.locator(
                "input[type=search], input[name*=search], input[id*=search], input[placeholder*=Search], input[placeholder*=search]"
            )

            if search_inputs.count() > 0:
                try:
                    search_inputs.first.fill(search_text[:120])
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(3000)
                    page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
                except Exception:
                    pass

            links = collect_dom_links(page, pack)
            buttons = collect_buttons(page, pack)

            result["dom_links"].extend([
                {
                    **x,
                    "source_page": portal_url,
                }
                for x in links[:30]
            ])

            result["buttons"].extend([
                {
                    **x,
                    "source_page": portal_url,
                }
                for x in buttons[:20]
            ])

            # click strongest document-like links
            for link in links[:10]:
                if not link.get("is_document_candidate") and link.get("score", 0) < 40:
                    continue

                try:
                    with page.expect_download(timeout=8000) as download_info:
                        page.locator(f"a[href='{link['href']}']").first.click()

                    download = download_info.value
                    saved = save_download(download, attachments_dir)
                    saved["source_link"] = link
                    result["downloads"].append(saved)

                except Exception:
                    # some links navigate instead of downloading
                    try:
                        href = link["href"]
                        page.goto(href, wait_until="networkidle", timeout=TIMEOUT_MS)

                        snapshot = save_html_snapshot(
                            page,
                            pack_dir,
                            "navigated_detail"
                        )

                        result["visited_pages"].append({
                            "url": page.url,
                            "snapshot": snapshot,
                            "title": page.title(),
                        })

                        more_links = collect_dom_links(page, pack)

                        result["dom_links"].extend([
                            {
                                **x,
                                "source_page": page.url,
                            }
                            for x in more_links[:30]
                        ])

                    except Exception as e:
                        result["errors"].append({
                            "stage": "click_or_navigate_link",
                            "link": link,
                            "error": str(e),
                        })

            # click strongest buttons likely to trigger downloads
            for button in buttons[:5]:
                if not button.get("is_document_candidate") and button.get("score", 0) < 40:
                    continue

                try:
                    with page.expect_download(timeout=8000) as download_info:
                        page.get_by_text(button["text"], exact=False).first.click()

                    download = download_info.value
                    saved = save_download(download, attachments_dir)
                    saved["source_button"] = button
                    result["downloads"].append(saved)

                except Exception as e:
                    result["errors"].append({
                        "stage": "click_button",
                        "button": button,
                        "error": str(e),
                    })

        except Exception as e:
            result["errors"].append({
                "stage": "visit_portal",
                "url": portal_url,
                "error": str(e),
            })

    page.close()

    manifest_path = pack_dir / "browser_acquisition_manifest.json"

    result["download_count"] = len(result["downloads"])
    result["manifest_path"] = str(manifest_path)

    write_json(manifest_path, result)

    return {
        "pack_id": pack.get("pack_id"),
        "rfq_id": pack.get("rfq_id"),
        "department": pack.get("department"),
        "description": pack.get("description"),
        "visited_pages": len(result["visited_pages"]),
        "dom_links": len(result["dom_links"]),
        "buttons": len(result["buttons"]),
        "downloads": len(result["downloads"]),
        "errors": len(result["errors"]),
        "manifest_path": str(manifest_path),
    }


def main():
    supply_index = load_json(SUPPLY_INDEX_FILE, default={})
    packs = supply_index.get("packs", [])

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            locale="en-ZA",
        )

        for pack in packs:
            print(f"Browser resolving: {pack.get('department')} | {pack.get('description')[:80]}")

            resolved = browser_resolve_pack(context, pack)
            results.append(resolved)

            print(
                f"  pages={resolved['visited_pages']} "
                f"links={resolved['dom_links']} "
                f"buttons={resolved['buttons']} "
                f"downloads={resolved['downloads']} "
                f"errors={resolved['errors']}"
            )

        context.close()
        browser.close()

    summary = {
        "generated_at": now_iso(),
        "total_supply_packs": len(packs),
        "packs_with_downloads": sum(1 for r in results if r["downloads"] > 0),
        "total_downloads": sum(r["downloads"] for r in results),
        "total_dom_links": sum(r["dom_links"] for r in results),
        "total_buttons": sum(r["buttons"] for r in results),
        "results": results,
    }

    write_json(OUTPUT_FILE, summary)

    print(f"\nBrowser acquisition complete: {OUTPUT_FILE}")
    print(f"Packs: {summary['total_supply_packs']}")
    print(f"With downloads: {summary['packs_with_downloads']}")
    print(f"Total downloads: {summary['total_downloads']}")


if __name__ == "__main__":
    main()
