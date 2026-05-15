import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="runtime/playwright_profiles/etenders",
            headless=False,
            args=["--start-maximized"],
            viewport=None,
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.etenders.gov.za", wait_until="domcontentloaded")
        await page.bring_to_front()

        print("Browser is open. Log in manually.")
        print("After Supplier Login is complete, come back here and press ENTER.")
        input("Press ENTER only after login is complete...")

        await context.close()

asyncio.run(run())
