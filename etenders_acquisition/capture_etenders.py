from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def log_response(response):
        if "api" in response.url.lower() or "odata" in response.url.lower():
            print("\n=== API FOUND ===")
            print(response.url)
            try:
                print(response.text()[:1000])
            except:
                pass

    page.on("response", log_response)

    page.goto("https://data.etenders.gov.za/")

    page.wait_for_timeout(15000)

    browser.close()
