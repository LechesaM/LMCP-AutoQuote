from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("Starting capture...")

    def on_request(request):
        if request.resource_type in ["xhr", "fetch"]:
            print("\n[REQUEST]")
            print(request.method, request.url)

    def on_response(response):
        url = response.url.lower()

        if "api" in url or "odata" in url or "search" in url:
            print("\n[RESPONSE]")
            print(response.url)

            try:
                body = response.text()
                if body.strip().startswith("{") or body.strip().startswith("["):
                    print(body[:500])
            except:
                pass

    page.on("request", on_request)
    page.on("response", on_response)

    page.goto("https://data.etenders.gov.za/")

    page.wait_for_timeout(30000)

    browser.close()
