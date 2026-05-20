const URL = process.env.LMCP_HIT_TEST_URL || "http://127.0.0.1:4173/__debug/hit-test";

const expected = [
  { x: 500, y: 300, expectAnchor: false },
  { x: 80, y: 260, expectAnchor: true },
  { x: 1450, y: 300, expectAnchor: false },
];

async function main() {
  let chromium;
  try {
    ({ chromium } = await import("playwright"));
  } catch (error) {
    console.log(JSON.stringify({
      status: "playwright_missing",
      url: URL,
      message: "Playwright is not installed in this environment. Open the debug page manually to inspect elementFromPoint hits.",
    }, null, 2));
    process.exitCode = 0;
    return;
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(250);

  const report = await page.evaluate((targets) => {
    const byPoint = targets.map(({ x, y }) => {
      const element = document.elementFromPoint(x, y);
      const style = element ? window.getComputedStyle(element) : null;
      const anchor = element instanceof HTMLAnchorElement ? element : element?.closest?.("a");
      return {
        x,
        y,
        tag: element?.tagName?.toLowerCase() || null,
        text: (element?.textContent || "").trim().slice(0, 120),
        href: anchor instanceof HTMLAnchorElement ? anchor.href : "",
        pointerEvents: style?.pointerEvents || null,
        position: style?.position || null,
        zIndex: style?.zIndex || null,
        opacity: style?.opacity || null,
        hasAnchor: Boolean(anchor),
      };
    });

    const overlays = Array.from(document.querySelectorAll("body *"))
      .map((element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          text: (element.textContent || "").trim().slice(0, 100),
          pointerEvents: style.pointerEvents,
          position: style.position,
          zIndex: style.zIndex,
          opacity: style.opacity,
          coversViewport: rect.left <= 0 && rect.top <= 0 && rect.width >= window.innerWidth * 0.9 && rect.height >= window.innerHeight * 0.9,
        };
      })
      .filter((item) => item.coversViewport && item.position !== "static");

    return { byPoint, overlays, viewport: { width: window.innerWidth, height: window.innerHeight } };
  }, expected);

  const summary = report.byPoint.map((entry) => {
    const expectedPoint = expected.find((item) => item.x === entry.x && item.y === entry.y);
    const pass = expectedPoint ? Boolean(entry.hasAnchor) === expectedPoint.expectAnchor : false;
    return {
      point: [entry.x, entry.y],
      tag: entry.tag,
      href: entry.href,
      pointerEvents: entry.pointerEvents,
      position: entry.position,
      zIndex: entry.zIndex,
      pass,
    };
  });

  const overallPass = summary.every((entry) => entry.pass);
  console.log(JSON.stringify({
    status: overallPass ? "passed" : "failed",
    url: URL,
    viewport: report.viewport,
    hits: summary,
    overlayCandidates: report.overlays,
  }, null, 2));

  await browser.close();
  process.exitCode = overallPass ? 0 : 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
