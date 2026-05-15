import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

STATE = "runtime/playwright_profiles/etenders_state.json"

async def run():
    Path("runtime/playwright_profiles").mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
        )
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.etenders.gov.za", wait_until="domcontentloaded")
        print("Login manually, solve CAPTCHA, then navigate to the SEDCOL submission page.")
        input("Press ENTER here only after the supplier page is open and logged in...")

        await context.storage_state(path=STATE)
        print(f"Saved state to {STATE}")

        await browser.close()

asyncio.run(run())
