from playwright.sync_api import sync_playwright

URL = "https://www.etenders.gov.za/Home/opportunities"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        seen = []

        def on_request(req):
            url = req.url.lower()

            # focus ONLY on datatables / ajax calls
            if any(x in url for x in [
                "datatable",
                "ajax",
                "api",
                "opportunity",
                "search",
                "load",
                "list"
            ]):
                seen.append(req.url)

        page.on("request", on_request)

        page.goto(URL, wait_until="networkidle")

        page.wait_for_timeout(8000)

        print("\n=== POSSIBLE RFQ DATA ENDPOINTS ===\n")
        for s in set(seen):
            print(s)

        browser.close()

run()
