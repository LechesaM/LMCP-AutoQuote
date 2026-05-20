import process from "node:process";

const url = process.env.LMCP_FRONTEND_URL || "http://127.0.0.1:4173/__debug/hit-test";

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch (error) {
  console.error("Playwright is not installed in this workspace.");
  console.error(`Open ${url} in a browser and inspect the Debug Hit Test page instead.`);
  process.exitCode = 1;
  process.exit(0);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
await page.goto(url, { waitUntil: "networkidle" });

const probe = await page.evaluate(() => {
  const samples = [
    [500, 300],
    [80, 260],
    [1450, 300],
  ];

  const pick = (element) => {
    if (!element) {
      return null;
    }
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      tag: element.tagName.toLowerCase(),
      id: element.id || "",
      className: typeof element.className === "string" ? element.className : "",
      pointerEvents: style.pointerEvents,
      position: style.position,
      zIndex: style.zIndex,
      opacity: style.opacity,
      rect: {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
    };
  };

  const overlays = Array.from(document.querySelectorAll("body *"))
    .filter((element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        rect.left <= 0 &&
        rect.top <= 0 &&
        rect.width >= window.innerWidth * 0.9 &&
        rect.height >= window.innerHeight * 0.9 &&
        (style.position === "fixed" || style.position === "absolute") &&
        style.pointerEvents !== "none" &&
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        Number.parseFloat(style.opacity || "1") > 0
      );
    })
    .map((element) => pick(element));

  return {
    hits: samples.map(([x, y]) => ({ x, y, element: pick(document.elementFromPoint(x, y)) })),
    overlays,
  };
});

console.log(JSON.stringify(probe, null, 2));
await browser.close();
