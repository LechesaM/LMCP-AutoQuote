import process from "node:process";
import { pathToFileURL } from "node:url";

const FRONTEND_URL = process.env.LMCP_FRONTEND_URL || "http://127.0.0.1:5173";
const BACKEND_URL = process.env.LMCP_BACKEND_URL || "http://127.0.0.1:8011";
const OPERATOR_EMAIL = process.env.LMCP_SUPERVISOR_EMAIL || "supervisor@lmcp.local";
const OPERATOR_PASSWORD = process.env.LMCP_SUPERVISOR_PASSWORD || "supervisor";
const SEARCH_QUERY = process.env.LMCP_LIVE_RFQ_QUERY || "Stationary Extra";
const MAX_MESSAGES = Number(process.env.LMCP_LIVE_RFQ_MAX_MESSAGES || 25);

const PLAYWRIGHT_MODULE_URL = process.env.LMCP_PLAYWRIGHT_MODULE_PATH
  ? pathToFileURL(process.env.LMCP_PLAYWRIGHT_MODULE_PATH)
  : new URL("../frontend/command-centre/node_modules/playwright/index.mjs", import.meta.url);

async function loadPlaywright() {
  return import(PLAYWRIGHT_MODULE_URL.href);
}

async function loginViaBrowser(page) {
  const response = await page.evaluate(
    async ({ backendUrl, email, password }) => {
      const loginResponse = await fetch(`${backendUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const bodyText = await loginResponse.text();
      let body;
      try {
        body = JSON.parse(bodyText);
      } catch {
        body = bodyText;
      }
      return { ok: loginResponse.ok, status: loginResponse.status, body };
    },
    { backendUrl: BACKEND_URL, email: OPERATOR_EMAIL, password: OPERATOR_PASSWORD },
  );

  if (!response.ok) {
    throw new Error(`Login failed: ${response.status}`);
  }

  return response.body;
}

async function injectSession(page, session) {
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

async function fetchJson(page, url, options = {}) {
  return page.evaluate(
    async ({ targetUrl, requestOptions }) => {
      const response = await fetch(targetUrl, requestOptions);
      const bodyText = await response.text();
      let body;
      try {
        body = JSON.parse(bodyText);
      } catch {
        body = bodyText;
      }
      return { ok: response.ok, status: response.status, body };
    },
    { targetUrl: url, requestOptions: options },
  );
}

async function main() {
  const playwright = await loadPlaywright();
  const browser = await playwright.chromium.launch({
    headless: true,
    args: ["--no-first-run", "--no-default-browser-check"],
    dumpio: true,
    timeout: 15000,
  });

  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
    const session = await loginViaBrowser(page);
    await injectSession(page, session);

    await page.goto(`${FRONTEND_URL}/supplier-quote-intelligence`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    await page.getByText("Live mailbox ingest").first().waitFor({ state: "visible", timeout: 30000 });

    const statusResponse = await fetchJson(page, `${BACKEND_URL}/supplier-quotes/status`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        Accept: "application/json",
      },
    });

    const runResponse = await fetchJson(page, `${BACKEND_URL}/supplier-quotes/run-once`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        search_query: SEARCH_QUERY,
        max_messages: MAX_MESSAGES,
      }),
    });

    const result = runResponse.body || {};
    const rfqNumber = String(result.rfq_number || result.imap_search_query || SEARCH_QUERY || "").trim();

    const workflowResponse = rfqNumber
      ? await fetchJson(page, `${BACKEND_URL}/operations/rfqs/${encodeURIComponent(rfqNumber)}`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            Accept: "application/json",
          },
        })
      : { ok: false, status: 0, body: null };

    const packageResponse = rfqNumber
      ? await fetchJson(page, `${BACKEND_URL}/operations/rfqs/${encodeURIComponent(rfqNumber)}/submission-package`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            Accept: "application/json",
          },
        })
      : { ok: false, status: 0, body: null };

    const executionResponse = rfqNumber
      ? await fetchJson(page, `${BACKEND_URL}/operations/rfqs/${encodeURIComponent(rfqNumber)}/submission-execution`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            Accept: "application/json",
          },
        })
      : { ok: false, status: 0, body: null };

    const packageBody = packageResponse.body || {};
    const executionBody = executionResponse.body || {};
    const workflowBody = workflowResponse.body || {};

    const summary = {
      stage: "fresh_live_rfq_smoke_test",
      backend_status: statusResponse.body?.status || null,
      live_mailbox_source: statusResponse.body?.live_mailbox_source || null,
      search_query: SEARCH_QUERY,
      run_status: result.status || null,
      success: Boolean(result.success),
      processed: Number(result.processed || 0),
      submitted_rfq: rfqNumber,
      review_ready: Boolean(result.review_ready ?? workflowBody.review_ready ?? false),
      approval_ready: Boolean(result.approval_ready ?? workflowBody.approval_ready ?? packageBody.approval_ready ?? false),
      submission_ready: Boolean(result.submission_ready ?? packageBody.submission_ready ?? false),
      submissionLocked: Boolean(
        packageBody.submissionLocked ?? packageBody.submission_locked ?? workflowBody.submissionLocked ?? false,
      ),
      package_zip_downloadable: Boolean(
        packageBody.download_url || packageBody.zip_path || packageBody.package_zip_path || packageBody.downloadable,
      ),
      workflow_ok: Boolean(workflowResponse.ok),
      workflow_status: workflowBody.status || null,
      package_ok: Boolean(packageResponse.ok),
      package_status: packageBody.status || packageResponse.body?.status || null,
      execution_ok: Boolean(executionResponse.ok),
      execution_status: executionBody.status || null,
      execution_body: executionBody,
      run_body: result,
    };

    console.log(JSON.stringify(summary, null, 2));

    const pass =
      Boolean(result.success) &&
      Boolean(summary.review_ready) &&
      Boolean(summary.approval_ready) &&
      Boolean(summary.submission_ready) &&
      Boolean(summary.submissionLocked) &&
      Boolean(summary.package_zip_downloadable) &&
      Boolean(workflowResponse.ok) &&
      Boolean(packageResponse.ok) &&
      Boolean(executionResponse.ok) &&
      String(summary.execution_status || "").toLowerCase() === "ok";

    process.exitCode = pass ? 0 : 1;
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify(
      {
        stage: "fresh_live_rfq_smoke_test",
        status: "failed",
        error: error instanceof Error ? error.message : String(error),
      },
      null,
      2,
    ),
  );
  process.exit(1);
});
