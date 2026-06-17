import { execFileSync } from "node:child_process";
import process from "node:process";
import { fileURLToPath } from "node:url";

const FRONTEND_URL = process.env.LMCP_FRONTEND_URL || "http://127.0.0.1:5173";
const PROJECT_ROOT = fileURLToPath(new URL("..", import.meta.url));
const PLAYWRIGHT_MODULE_URL = new URL("../frontend/command-centre/node_modules/playwright/index.mjs", import.meta.url);
const PLAYWRIGHT_EXECUTABLE_PATH =
  process.env.LMCP_PLAYWRIGHT_EXECUTABLE_PATH || process.env.LMCP_PLAYWRIGHT_CHROMIUM_PATH || process.env.PLAYWRIGHT_CHROMIUM_PATH || "";

function getSession(email, password) {
  const pythonScript = `import json, sys
sys.path.insert(0, ${JSON.stringify(PROJECT_ROOT)})
from app.auth.auth_service import authenticate_user
result = authenticate_user(${JSON.stringify(email)}, ${JSON.stringify(password)})
print(json.dumps(result))`;
  const output = execFileSync("python3", ["-c", pythonScript], { encoding: "utf8" }).trim();
  return JSON.parse(output);
}

async function main() {
  const playwright = await import(PLAYWRIGHT_MODULE_URL.href);
  const { chromium } = playwright;
  const session = getSession("operator@lmcp.local", "operator");
  const browser = await chromium.launch({
    headless: true,
    ...(PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: PLAYWRIGHT_EXECUTABLE_PATH } : {}),
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.addInitScript(
    ({ storageKey, sessionState }) => {
      window.localStorage.setItem(storageKey, JSON.stringify({ state: sessionState, version: 0 }));
    },
    {
      storageKey: "lmcp-command-centre-auth",
      sessionState: {
        token: session.access_token,
        user: session.user,
        permissions: session.permissions,
      },
    },
  );
  await page.goto(`${FRONTEND_URL}/review`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(15000);
  console.log("URL", page.url());
  console.log(await page.locator("body").innerText());
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
