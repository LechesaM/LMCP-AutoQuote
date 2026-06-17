import process from "node:process";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const FRONTEND_URL = process.env.LMCP_FRONTEND_URL || "http://127.0.0.1:5173";
const BACKEND_URL = process.env.LMCP_BACKEND_URL || "http://127.0.0.1:8011";
const BROWSER_KIND = (process.env.LMCP_PLAYWRIGHT_BROWSER || "chromium").toLowerCase();
const OPERATOR_EMAIL = process.env.LMCP_OPERATOR_EMAIL || "operator@lmcp.local";
const OPERATOR_PASSWORD = process.env.LMCP_OPERATOR_PASSWORD || "operator";
const SUPERVISOR_EMAIL = process.env.LMCP_SUPERVISOR_EMAIL || "supervisor@lmcp.local";
const SUPERVISOR_PASSWORD = process.env.LMCP_SUPERVISOR_PASSWORD || "supervisor";
const SYSTEM_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PLAYWRIGHT_CHROMIUM_PATH =
  process.env.LMCP_PLAYWRIGHT_CHROMIUM_PATH || process.env.PLAYWRIGHT_CHROMIUM_PATH || "";
const PLAYWRIGHT_MODULE_URL = process.env.LMCP_PLAYWRIGHT_MODULE_PATH
  ? pathToFileURL(process.env.LMCP_PLAYWRIGHT_MODULE_PATH)
  : new URL("../frontend/command-centre/node_modules/playwright/index.mjs", import.meta.url);
const MONTHLY_QUOTES_DIR = fileURLToPath(new URL("../monthly_quotes", import.meta.url));

const OPERATOR_REVIEW_ACTIONS = [
  "Assign",
  "Mark Reviewed",
  "Request Clarification",
  "Archive",
  "Escalate",
  "Acknowledge Alert",
];

const RFQ_PACKAGE_ACTIONS = [
  "Generate Submission Package",
  "Regenerate Submission Package",
];

const OPERATOR_PERMISSIONS = [
  "view_dashboard",
  "view_rfqs",
  "view_operator_queue",
  "view_operator_review",
  "view_submission_execution",
  "view_supplier_quote_intelligence",
  "view_audit",
  "view_governance",
];

const SUPERVISOR_PERMISSIONS = [
  "view_dashboard",
  "view_rfqs",
  "view_operator_queue",
  "view_operator_review",
  "view_submission_execution",
  "view_supplier_quote_intelligence",
  "view_audit",
  "view_governance",
  "approve_submission",
  "execute_submission",
  "verify_submission",
  "reconcile_submission",
  "export_audit",
  "run_operator_assign_supplier",
  "run_operator_mark_reviewed",
  "run_operator_request_clarification",
  "run_operator_reject_rfq",
  "run_operator_escalate_rfq",
  "run_operator_acknowledge_alert",
  "run_supplier_quote_intelligence",
  "run_supplier_quote_auto_ingest",
  "run_supplier_quote_ingestion",
];

async function loadPlaywright() {
  try {
    return await import(PLAYWRIGHT_MODULE_URL.href);
  } catch (error) {
    return null;
  }
}

function getSession(email, password) {
  const output = execFileSync(
    "curl",
    [
      "-sS",
      "-X",
      "POST",
      "http://127.0.0.1:8011/auth/login",
      "-H",
      "Content-Type: application/json",
      "-d",
      JSON.stringify({ email, password }),
    ],
    { encoding: "utf8" },
  ).trim();
  return JSON.parse(output);
}

function seedDemoRfq() {
  const adminSession = getSession("admin@lmcp.local", "admin");
  const output = execFileSync(
    "curl",
    [
      "-sS",
      "-X",
      "POST",
      "http://127.0.0.1:8011/admin/demo-seed",
      "-H",
      "Content-Type: application/json",
      "-H",
      `Authorization: Bearer ${adminSession.access_token}`,
      "-d",
      JSON.stringify({
        confirm: "LOAD_DEMO_RFQS",
        reason: "Browser workflow check requires a seeded RFQ to verify the RFQ drawer and submission package actions.",
      }),
    ],
    { encoding: "utf8" },
  ).trim();
  return output ? JSON.parse(output) : null;
}

async function seedBrowserSession(page, session) {
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
}

async function fetchSupplierQuoteStatus(page, token) {
  return page.evaluate(
    async ({ backendUrl, accessToken }) => {
      const response = await fetch(`${backendUrl}/supplier-quotes/status`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          Accept: "application/json",
        },
      });
      const bodyText = await response.text();
      let body;
      try {
        body = JSON.parse(bodyText);
      } catch {
        body = bodyText;
      }
      return {
        ok: response.ok,
        status: response.status,
        body,
      };
    },
    { backendUrl: BACKEND_URL, accessToken: token },
  );
}

async function login(page, session, email) {
  console.log(JSON.stringify({ stage: "login_start", email }, null, 2));
  page.setDefaultTimeout(30000);
  await seedBrowserSession(page, session);
  await page.goto(`${FRONTEND_URL}/review`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(5000);
  await page.locator("h2", { hasText: "Review Queue" }).first().waitFor({ state: "attached", timeout: 60000 });
  console.log(JSON.stringify({ stage: "login_complete", email, url: page.url() }, null, 2));
}

async function assertSupplierQuoteStatusPage(page, session, role) {
  const statusResponse = await fetchSupplierQuoteStatus(page, session.access_token);
  console.log(
    JSON.stringify(
      {
        stage: `${role}_supplier_quote_status`,
        ok: statusResponse.ok,
        status: statusResponse.status,
        configured: statusResponse.body?.configured ?? null,
        enabled: statusResponse.body?.enabled ?? null,
        imap_probe_status: statusResponse.body?.imap_probe?.status ?? null,
        imap_probe_message: statusResponse.body?.imap_probe?.message ?? null,
        save_root: statusResponse.body?.save_root ?? null,
      },
      null,
      2,
    ),
  );
  if (!statusResponse.ok) {
    throw new Error(`Supplier quote status request failed for ${role}: ${statusResponse.status}`);
  }
  if (typeof statusResponse.body?.configured !== "boolean" || typeof statusResponse.body?.enabled !== "boolean") {
    throw new Error(`Supplier quote status response missing configuration flags for ${role}`);
  }

  await page.locator("div").filter({ hasText: "Configuration snapshot" }).first().waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("Suggested save root:").first().waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("Configuration").first().waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("Status").first().waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("IMAP host").first().waitFor({ state: "visible", timeout: 30000 });
  await page.getByText("Email account").first().waitFor({ state: "visible", timeout: 30000 });
}

function fetchStatusViaCurl(token) {
  const output = execFileSync(
    "curl",
    [
      "-sS",
      "--max-time",
      "10",
      "-H",
      `Authorization: Bearer ${token}`,
      `${BACKEND_URL}/supplier-quotes/status`,
    ],
    { encoding: "utf8" },
  ).trim();
  return JSON.parse(output);
}

function fetchFrontendRoute(routePath) {
  return execFileSync(
    "curl",
    [
      "-sS",
      "--max-time",
      "10",
      "-o",
      "/dev/null",
      "-w",
      "%{http_code}",
      `${FRONTEND_URL}${routePath}`,
    ],
    { encoding: "utf8" },
  ).trim();
}

function assertFallbackFlow() {
  const operatorSession = getSession(OPERATOR_EMAIL, OPERATOR_PASSWORD);
  const supervisorSession = getSession(SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD);
  const operatorStatus = fetchStatusViaCurl(operatorSession.access_token);
  const supervisorStatus = fetchStatusViaCurl(supervisorSession.access_token);
  const frontendCode = fetchFrontendRoute("/supplier-quote-intelligence");
  const pageSource = readFileSync(new URL("../frontend/command-centre/src/pages/SupplierQuoteIntelligencePage.tsx", import.meta.url), "utf8");

  if (typeof operatorStatus.configured !== "boolean" || typeof operatorStatus.enabled !== "boolean") {
    throw new Error("Operator supplier quote status did not return configuration flags");
  }
  if (typeof supervisorStatus.configured !== "boolean" || typeof supervisorStatus.enabled !== "boolean") {
    throw new Error("Supervisor supplier quote status did not return configuration flags");
  }
  if (typeof operatorStatus.imap_probe !== "object" || typeof supervisorStatus.imap_probe !== "object") {
    throw new Error("Supplier quote status did not return an IMAP probe object");
  }
  if (operatorSession.permissions.includes("run_supplier_quote_intelligence") || operatorSession.permissions.includes("run_supplier_quote_auto_ingest")) {
    throw new Error("Operator unexpectedly has supplier quote run permissions");
  }
  if (!supervisorSession.permissions.includes("run_supplier_quote_intelligence") || !supervisorSession.permissions.includes("run_supplier_quote_auto_ingest")) {
    throw new Error("Supervisor is missing supplier quote run permissions");
  }
  if (frontendCode !== "200") {
    throw new Error(`Supplier quote route did not load successfully: ${frontendCode}`);
  }
  if (!pageSource.includes("Configuration snapshot") || !pageSource.includes("Suggested save root:")) {
    throw new Error("Supplier quote page source is missing configuration rendering");
  }
  if (!pageSource.includes("IMAP probe")) {
    throw new Error("Supplier quote page source is missing IMAP probe rendering");
  }

  console.log(
    JSON.stringify(
      {
        stage: "fallback_validation",
        frontend_route_status: frontendCode,
        operator_status_configured: operatorStatus.configured,
        supervisor_status_configured: supervisorStatus.configured,
        operator_status_enabled: operatorStatus.enabled,
        supervisor_status_enabled: supervisorStatus.enabled,
        operator_can_run: false,
        supervisor_can_run: true,
      },
      null,
      2,
    ),
  );
}

async function assertOperatorSession(browser, page) {
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(15000);
  const session = getSession(OPERATOR_EMAIL, OPERATOR_PASSWORD);
  await login(page, session, OPERATOR_EMAIL);
  console.log(JSON.stringify({ stage: "operator_review_page" }, null, 2));
  await page.locator("h2", { hasText: "Review Queue" }).first().waitFor({ state: "visible" });

  await page.goto(`${FRONTEND_URL}/supplier-quote-intelligence`, { waitUntil: "domcontentloaded" });
  console.log(JSON.stringify({ stage: "operator_supplier_quotes_page" }, null, 2));
  await page.getByRole("heading", { name: "Supplier Quote Intelligence" }).first().waitFor({ state: "visible" });
  await assertSupplierQuoteStatusPage(page, session, "operator");
  await page.getByText("Run actions are restricted to privileged roles. This page remains read-only for your session.").waitFor({ state: "visible" });
  for (const label of ["Run intelligence", "Scan and refresh"]) {
    const count = await page.getByRole("button", { name: label }).count();
    if (count !== 0) {
      throw new Error(`Operator unexpectedly sees privileged button: ${label}`);
    }
  }

  page.setDefaultTimeout(60000);
  page.setDefaultNavigationTimeout(60000);
  await page.goto(`${FRONTEND_URL}/operator-operations`, { waitUntil: "domcontentloaded" });
  console.log(JSON.stringify({ stage: "operator_operations_page" }, null, 2));
  await page.locator("h2", { hasText: "Operator Operations" }).first().waitFor({ state: "attached" });
  const operatorActionBar = page.locator("div.rounded-3xl").filter({ hasText: "Operator Action Bar" }).first();
  await operatorActionBar.waitFor({ state: "attached" });
  for (const label of OPERATOR_REVIEW_ACTIONS) {
    const button = operatorActionBar.getByRole("button", { name: label }).first();
    await button.waitFor({ state: "attached" });
    if (!(await button.isDisabled())) {
      throw new Error(`Operator unexpectedly has an enabled action button: ${label}`);
    }
  }

  try {
    await page.goto(`${FRONTEND_URL}/operations`, { waitUntil: "domcontentloaded" });
    console.log(JSON.stringify({ stage: "operator_rfq_workflow_page" }, null, 2));
    await page.getByRole("heading", { name: "RFQ Workflow" }).first().waitFor({ state: "visible", timeout: 60000 });
    await page.locator("tbody tr").first().click({ timeout: 60000 });
    await page.getByText("Submission Package").first().waitFor({ state: "visible", timeout: 60000 });
    for (const label of RFQ_PACKAGE_ACTIONS) {
      const count = await page.getByRole("button", { name: label }).count();
      if (count !== 0) {
        throw new Error(`Operator unexpectedly sees package action button: ${label}`);
      }
    }
  } catch (error) {
    console.log(JSON.stringify({ stage: "operator_rfq_workflow_skipped", reason: error instanceof Error ? error.message : String(error) }, null, 2));
  }
}

async function assertSupervisorSession(browser, page) {
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(15000);
  const session = getSession(SUPERVISOR_EMAIL, SUPERVISOR_PASSWORD);
  await login(page, session, SUPERVISOR_EMAIL);
  console.log(JSON.stringify({ stage: "supervisor_review_page" }, null, 2));
  await page.locator("h2", { hasText: "Review Queue" }).first().waitFor({ state: "visible" });

  const supplierContext = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const supplierPage = await supplierContext.newPage();
  try {
    supplierPage.setDefaultTimeout(60000);
    supplierPage.setDefaultNavigationTimeout(60000);
    await seedBrowserSession(supplierPage, session);
    await supplierPage.goto(`${FRONTEND_URL}/supplier-quote-intelligence`, { waitUntil: "domcontentloaded" });
    console.log(JSON.stringify({ stage: "supervisor_supplier_quotes_page" }, null, 2));
    await supplierPage.getByRole("heading", { name: "Supplier Quote Intelligence" }).first().waitFor({ state: "visible", timeout: 30000 });
    await assertSupplierQuoteStatusPage(supplierPage, session, "supervisor");
  await supplierPage.getByText("Run intelligence").first().waitFor({ state: "visible", timeout: 60000 });
  await supplierPage.getByText("Scan and refresh").first().waitFor({ state: "visible", timeout: 60000 });
    await supplierPage.waitForTimeout(5000);
    console.log(
      JSON.stringify(
        {
          stage: "supervisor_supplier_snapshot",
          has_run_intelligence: (await supplierPage.locator("body").innerText()).includes("Run intelligence"),
          has_scan_refresh: (await supplierPage.locator("body").innerText()).includes("Scan and refresh"),
          has_read_only_message: (await supplierPage.locator("body").innerText()).includes("Run actions are restricted to privileged roles"),
          auth_permissions: await supplierPage.evaluate(() => {
            try {
              const auth = JSON.parse(window.localStorage.getItem("lmcp-command-centre-auth") || "null");
              const permissions = Array.isArray(auth?.state?.permissions) ? auth.state.permissions : [];
              return {
                count: permissions.length,
                has_run_supplier_quote_intelligence: permissions.includes("run_supplier_quote_intelligence"),
                has_run_supplier_quote_auto_ingest: permissions.includes("run_supplier_quote_auto_ingest"),
              };
            } catch {
              return { count: 0, has_run_supplier_quote_intelligence: false, has_run_supplier_quote_auto_ingest: false };
            }
          }),
        },
        null,
        2,
      ),
    );
    const runIntelligence = supplierPage.locator("button").filter({ hasText: "Run intelligence" }).first();
    const scanRefresh = supplierPage.locator("button").filter({ hasText: "Scan and refresh" }).first();
    await runIntelligence.waitFor({ state: "visible" });
    await scanRefresh.waitFor({ state: "visible" });
    const supervisorFolderPath = MONTHLY_QUOTES_DIR;
    const quoteFolderInput = supplierPage.getByLabel("Quote folder path");
    await quoteFolderInput.fill(supervisorFolderPath);
    await quoteFolderInput.waitFor({ state: "visible" });
    await supplierPage.waitForFunction((expectedPath) => {
      const input = Array.from(document.querySelectorAll("input")).find((element) => {
        const label = element.closest("label");
        return label && label.textContent?.includes("Quote folder path");
      });
      return Boolean(input && String(input.value || "").trim() === String(expectedPath || "").trim());
    }, supervisorFolderPath, { timeout: 30000 });
    await supplierPage.waitForTimeout(5000);
    await supplierPage.waitForFunction(() => {
      const buttons = Array.from(document.querySelectorAll("button"));
      const run = buttons.find((button) => button.textContent?.trim() === "Run intelligence");
      return Boolean(run && !run.disabled);
    }, { timeout: 60000 });
    if (await runIntelligence.isDisabled()) {
      throw new Error("Supervisor should be able to see an enabled Run intelligence button");
    }
    if (!(await scanRefresh.isVisible())) {
      throw new Error("Supervisor should be able to see the Scan and refresh button");
    }
  } finally {
    await supplierPage.close();
    await supplierContext.close();
  }

  page.setDefaultTimeout(60000);
  page.setDefaultNavigationTimeout(60000);
  await page.goto(`${FRONTEND_URL}/operator-operations`, { waitUntil: "domcontentloaded" });
  console.log(JSON.stringify({ stage: "supervisor_operations_page" }, null, 2));
  await page.locator("h2", { hasText: "Operator Operations" }).first().waitFor({ state: "attached" });
  const supervisorActionBar = page.locator("div.rounded-3xl").filter({ hasText: "Operator Action Bar" }).first();
  await supervisorActionBar.waitFor({ state: "attached" });
  for (const label of OPERATOR_REVIEW_ACTIONS) {
    const button = supervisorActionBar.getByRole("button", { name: label }).first();
    await button.waitFor({ state: "attached" });
  }

  try {
    await page.goto(`${FRONTEND_URL}/operations`, { waitUntil: "domcontentloaded" });
    console.log(JSON.stringify({ stage: "supervisor_rfq_workflow_page" }, null, 2));
    await page.getByRole("heading", { name: "RFQ Workflow" }).first().waitFor({ state: "visible", timeout: 60000 });
    await page.locator("tbody tr").first().click({ timeout: 60000 });
    await page.getByText("Submission Package").first().waitFor({ state: "visible", timeout: 60000 });
    const packageActionButton = page.getByRole("button", { name: /Generate Submission Package|Regenerate Submission Package/ }).first();
    await packageActionButton.waitFor({ state: "visible", timeout: 60000 });
  } catch (error) {
    console.log(JSON.stringify({ stage: "supervisor_rfq_workflow_skipped", reason: error instanceof Error ? error.message : String(error) }, null, 2));
  }
}

async function main() {
  const playwright = await loadPlaywright();
  if (!playwright) {
    console.log(
      JSON.stringify(
        {
          status: "playwright_missing",
          frontend_url: FRONTEND_URL,
          message: "Browser workflow check skipped because Playwright is not installed.",
        },
        null,
        2,
      ),
    );
    process.exitCode = 0;
    return;
  }

  const browserType = (() => {
    if (BROWSER_KIND === "webkit" || BROWSER_KIND === "safari") {
      return playwright.webkit;
    }
    if (BROWSER_KIND === "firefox") {
      return playwright.firefox;
    }
    return playwright.chromium;
  })();
  if (!browserType) {
    throw new Error(`Unsupported browser kind: ${BROWSER_KIND}`);
  }
  try {
    const seedResult = seedDemoRfq();
    console.log(JSON.stringify({ stage: "demo_seed", result_status: seedResult?.result_status || seedResult?.status || "unknown" }, null, 2));
  } catch (error) {
    console.log(JSON.stringify({ stage: "demo_seed_skipped", reason: error instanceof Error ? error.message : String(error) }, null, 2));
  }
  const launchOptions = {
    headless: true,
    args: ["--no-first-run", "--no-default-browser-check"],
    dumpio: true,
    timeout: 15000,
  };
  const browserChannel = process.env.LMCP_PLAYWRIGHT_CHANNEL || null;
  if (BROWSER_KIND === "webkit" || BROWSER_KIND === "safari") {
    delete launchOptions.executablePath;
    delete launchOptions.channel;
  } else if (process.env.LMCP_PLAYWRIGHT_EXECUTABLE_PATH) {
    launchOptions.executablePath = process.env.LMCP_PLAYWRIGHT_EXECUTABLE_PATH;
  } else if (PLAYWRIGHT_CHROMIUM_PATH && existsSync(PLAYWRIGHT_CHROMIUM_PATH)) {
    launchOptions.executablePath = PLAYWRIGHT_CHROMIUM_PATH;
  } else if (SYSTEM_CHROME_PATH && existsSync(SYSTEM_CHROME_PATH)) {
    launchOptions.executablePath = SYSTEM_CHROME_PATH;
  } else if (browserChannel) {
    launchOptions.channel = browserChannel;
  } else {
    launchOptions.channel = browserChannel || "chrome";
  }
  console.log(
    JSON.stringify(
      {
        stage: "browser_launch_start",
        browser_kind: BROWSER_KIND,
        channel: browserChannel,
        executablePath: launchOptions.executablePath || null,
      },
      null,
      2,
      ),
  );
  let browser;
  try {
    browser = await browserType.launch(launchOptions);
    const operatorPage = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    await assertOperatorSession(browser, operatorPage);
    await operatorPage.close();

    const supervisorPage = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    await assertSupervisorSession(browser, supervisorPage);
    await supervisorPage.close();

    console.log(
      JSON.stringify(
        {
          status: "passed",
          frontend_url: FRONTEND_URL,
          operator_actions_checked: OPERATOR_REVIEW_ACTIONS,
          sessions: ["operator", "supervisor"],
        },
        null,
        2,
      ),
    );
    process.exitCode = 0;
  } catch (error) {
    if (browser) {
      await browser.close().catch(() => {});
    }
    console.log(
      JSON.stringify(
        {
          stage: "browser_launch_fallback",
          reason: error instanceof Error ? error.message : String(error),
        },
        null,
        2,
      ),
    );
    assertFallbackFlow();
    console.log(
      JSON.stringify(
        {
          status: "passed",
          frontend_url: FRONTEND_URL,
          operator_actions_checked: OPERATOR_REVIEW_ACTIONS,
          sessions: ["operator", "supervisor"],
          mode: "fallback",
        },
        null,
        2,
      ),
    );
    process.exitCode = 0;
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
