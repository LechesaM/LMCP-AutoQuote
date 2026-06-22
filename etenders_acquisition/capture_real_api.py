from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def log_response(response):
        url = response.url.lower()

        # ONLY real data signals
        if any(x in url for x in ["odata", "api", "search", "tender", "datatable"]):
            print("\n=== POSSIBLE DATA ENDPOINT ===")
            print("URL:", response.url)

            try:
                body = response.text()
                if body.strip().startswith("{") or body.strip().startswith("["):
                    print("JSON DETECTED:")
                    print(body[:1000])
            except:
                pass

    page.on("response", log_response)

    page.goto("https://data.etenders.gov.za/")

    # force DataTables to load
    page.wait_for_timeout(20000)

    browser.close()
