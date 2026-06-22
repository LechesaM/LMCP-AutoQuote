from playwright.sync_api import sync_playwright
from pathlib import Path
import json

OUT = Path("/Users/cash/Documents/runtime/etenders_row_action_probe.json")
TARGET_TEXT = "Table 01"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    requests_seen = []

    def on_request(req):
        if "download" in req.url.lower() or "paginated" in req.url.lower():
            requests_seen.append({
                "url": req.url,
                "method": req.method,
                "post_data": req.post_data,
                "headers": dict(req.headers),
            })

    page.on("request", on_request)

    page.goto("https://www.etenders.gov.za/Home/opportunities?id=1", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    page.evaluate("""
        () => {
            if (window.$ && $.fn.dataTable.isDataTable('#tendeList')) {
                $('#tendeList').DataTable().search('Table 01').draw();
            }
        }
    """)

    page.wait_for_timeout(6000)

    html = page.content()

    rows = []
    for i in range(page.locator("tr").count()):
        row = page.locator("tr").nth(i)
        try:
            txt = row.inner_text(timeout=1000)
            if TARGET_TEXT.lower() in txt.lower():
                rows.append({
                    "row_index": i,
                    "text": txt,
                    "html": row.evaluate("el => el.outerHTML"),
                })
        except Exception:
            pass

    actions = []
    for i in range(page.locator("button, a, input, i").count()):
        el = page.locator("button, a, input, i").nth(i)
        try:
            outer = el.evaluate("el => el.outerHTML")
            text = ""
            try:
                text = el.inner_text(timeout=500)
            except Exception:
                text = el.get_attribute("value") or ""

            if (
                "download" in outer.lower()
                or "view" in outer.lower()
                or "fa-" in outer.lower()
                or "onclick" in outer.lower()
                or TARGET_TEXT.lower() in outer.lower()
            ):
                actions.append({
                    "index": i,
                    "text": text,
                    "outerHTML": outer,
                    "onclick": el.get_attribute("onclick"),
                    "href": el.get_attribute("href"),
                    "class": el.get_attribute("class"),
                    "id": el.get_attribute("id"),
                })
        except Exception:
            pass

    OUT.write_text(json.dumps({
        "target": TARGET_TEXT,
        "rows": rows,
        "actions": actions,
        "requests_seen": requests_seen,
        "html_contains_target": TARGET_TEXT in html,
    }, indent=2))

    print(f"Saved {OUT}")
    print(f"rows={len(rows)} actions={len(actions)} requests={len(requests_seen)} html_contains={TARGET_TEXT in html}")

    browser.close()
