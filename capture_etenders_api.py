from playwright.sync_api import sync_playwright

URL = "https://www.etenders.gov.za/Home/opportunities"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        requests_seen = []

        def log_request(request):
            if any(x in request.url.lower() for x in ["api", "ajax", "json", "datatable"]):
                requests_seen.append(request.url)

        page.on("request", log_request)

        page.goto(URL, wait_until="networkidle")

        print("\n--- POSSIBLE DATA ENDPOINTS ---")
        for r in set(requests_seen):
            print(r)

        browser.close()

run()
