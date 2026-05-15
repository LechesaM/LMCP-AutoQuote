import asyncio
from playwright.async_api import async_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def run():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="runtime/playwright_profiles/etenders",
            executable_path=CHROME,
            headless=False,
            args=["--start-maximized"],
            viewport=None,
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.etenders.gov.za", wait_until="domcontentloaded")
        await page.bring_to_front()

        print("Chrome is open. Complete Supplier Login.")
        input("Press ENTER here only after login is fully complete...")

        await context.close()

asyncio.run(run())
