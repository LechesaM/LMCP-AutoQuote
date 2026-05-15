from pathlib import Path
from playwright.sync_api import sync_playwright

STATE = Path("runtime/playwright_profiles/etenders_state.json")
STATE.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--no-sandbox"]
    )
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.etenders.gov.za", wait_until="domcontentloaded")

    print("\nLog in manually in the Chrome window if needed.")
    print("After login, navigate to Browse Opportunities / Currently Advertised.")
    input("Press ENTER here after login is complete... ")

    context.storage_state(path=str(STATE))
    print(f"Saved login state to: {STATE}")

    browser.close()
