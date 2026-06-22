from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # IMPORTANT: visible browser
    page = browser.new_page()

    def log_request(req):
        if req.resource_type in ["xhr", "fetch"]:
            print("[REQUEST]", req.method, req.url)

    def log_response(res):
        url = res.url.lower()
        if any(x in url for x in ["api", "odata", "search", "tender"]):
            print("\n[RESPONSE]", res.url)
            try:
                print(res.text()[:300])
            except:
                pass

    page.on("request", log_request)
    page.on("response", log_response)

    page.goto("https://data.etenders.gov.za/")

    page.wait_for_timeout(5000)

    input("Browser opened. Navigate manually to 'Tenders' then press ENTER here...")

    page.wait_for_timeout(15000)

    browser.close()
