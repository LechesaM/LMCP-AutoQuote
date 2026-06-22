#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

RUNTIME_DIR = Path("/Users/cash/Documents/runtime")
OUT = RUNTIME_DIR / "browser_acquisition" / "browser_dom_probe.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

URL = "https://www.etenders.gov.za/Home/opportunities?id=1"


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            locale="en-ZA",
        )

        page = context.new_page()
        page.set_default_timeout(10000)

        print("Opening page...")
        page.goto(URL, wait_until="domcontentloaded", timeout=10000)
        page.wait_for_timeout(5000)

        title = page.title()
        html = page.content()

        anchors = []

        count = page.locator("a").count()

        for i in range(min(count, 300)):
            a = page.locator("a").nth(i)

            try:
                anchors.append({
                    "text": clean(a.inner_text(timeout=1000)),
                    "href": a.get_attribute("href"),
                })
            except Exception:
                pass

        buttons = []

        bcount = page.locator("button").count()

        for i in range(min(bcount, 100)):
            b = page.locator("button").nth(i)

            try:
                buttons.append({
                    "text": clean(b.inner_text(timeout=1000)),
                })
            except Exception:
                pass

        tables = []

        tcount = page.locator("table").count()

        for i in range(min(tcount, 20)):
            t = page.locator("table").nth(i)

            try:
                tables.append({
                    "text_preview": clean(t.inner_text(timeout=3000))[:3000],
                })
            except Exception:
                pass

        out = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "url": URL,
            "title": title,
            "anchor_count": count,
            "button_count": bcount,
            "table_count": tcount,
            "html_chars": len(html),
            "anchors": anchors,
            "buttons": buttons,
            "tables": tables,
        }

        write_json(OUT, out)

        print(f"DOM probe written: {OUT}")
        print(f"title={title}")
        print(f"anchors={count} buttons={bcount} tables={tcount} html_chars={len(html)}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
