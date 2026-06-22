from playwright.sync_api import sync_playwright

TARGET_TENDER = "E1826TGSERI"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    def log_request(req):
        url = req.url
        if "Download" in url or "download" in url or "Spec" in url or "document" in url.lower():
            print("REQUEST:", req.method, url)

    def log_response(resp):
        url = resp.url
        if "Download" in url or "download" in url or "Spec" in url or "document" in url.lower():
            print("RESPONSE:", resp.status, url)

    page.on("request", log_request)
    page.on("response", log_response)

    page.goto("https://www.etenders.gov.za/Home/opportunities", wait_until="networkidle")

    print("\nPage loaded.")
    print("Search manually for tender:", TARGET_TENDER)
    print("Click its document/download link.")
    print("Network calls will print here.")
    print("Press Enter here after clicking the download link...")

    input()

    browser.close()
