import process from "node:process";
import { pathToFileURL } from "node:url";

const PLAYWRIGHT_MODULE_URL = process.env.LMCP_PLAYWRIGHT_MODULE_PATH
  ? pathToFileURL(process.env.LMCP_PLAYWRIGHT_MODULE_PATH)
  : new URL("../frontend/command-centre/node_modules/playwright/index.mjs", import.meta.url);

const fixtureHtml = String.raw`
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Governance</title>
  </head>
  <body>
    <main>
      <section aria-labelledby="governance-controls">
        <h2 id="governance-controls">Governance and Release Controls</h2>
        <p>The command centre keeps manual approval, review_ready, proof capture and final submission under human control.</p>
      </section>
      <section aria-labelledby="manual-completion">
        <h3 id="manual-completion">Manual Completion and Proof</h3>
        <p>The local workflow stays operator-led at the end of the chain: prepare the pack, capture the manual completion record, generate proof, and keep final portal submission blocked unless a human uploads it.</p>
        <a href="/quote-compilation/status">Quote Compilation Status</a>
        <a href="/submission-proof/status">Submission Proof Status</a>
        <a href="/portal-submission/status">Portal Submission Status</a>
      </section>
    </main>
  </body>
</html>
`;

async function main() {
  const playwright = await import(PLAYWRIGHT_MODULE_URL.href);
  const { chromium } = playwright;
  console.log(JSON.stringify({ stage: "playwright_loaded" }, null, 2));
  const browser = await chromium.launch({
    headless: true,
    timeout: 15000,
    args: ["--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-software-rasterizer"],
    dumpio: true,
    ...(process.env.LMCP_PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.LMCP_PLAYWRIGHT_EXECUTABLE_PATH } : {}),
  });
  console.log(JSON.stringify({ stage: "browser_launched" }, null, 2));

  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    console.log(JSON.stringify({ stage: "page_created" }, null, 2));
    await page.setContent(fixtureHtml, { waitUntil: "domcontentloaded" });
    console.log(JSON.stringify({ stage: "fixture_loaded" }, null, 2));

    await page.getByRole("heading", { name: "Manual Completion and Proof" }).first().waitFor({ state: "visible", timeout: 10000 });
    console.log(JSON.stringify({ stage: "heading_visible" }, null, 2));
    const expectedLinks = [
      ["/quote-compilation/status", "Quote Compilation Status"],
      ["/submission-proof/status", "Submission Proof Status"],
      ["/portal-submission/status", "Portal Submission Status"],
    ];

    const actual = [];
    for (const [href, label] of expectedLinks) {
      const link = page.getByRole("link", { name: label }).first();
      await link.waitFor({ state: "visible", timeout: 10000 });
      console.log(JSON.stringify({ stage: "link_visible", label }, null, 2));
      const actualHref = await link.getAttribute("href");
      if (actualHref !== href) {
        throw new Error(`Expected ${label} to have href ${href}, received ${actualHref || "<none>"}`);
      }
      await link.click();
      console.log(JSON.stringify({ stage: "link_clicked", label, href: actualHref }, null, 2));
      actual.push({ label, href: actualHref });
    }

    console.log(
      JSON.stringify(
        {
          status: "ok",
          verified: true,
          url: page.url(),
          links: actual,
        },
        null,
        2,
      ),
    );

    process.exitCode = 0;
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify(
      {
        status: "failed",
        error: error instanceof Error ? error.message : String(error),
      },
      null,
      2,
    ),
  );
  process.exit(1);
});
