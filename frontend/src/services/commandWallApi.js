const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

async function readJson(path, fallback) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return await response.json();
  } catch (error) {
    return {
      __lmcp_error: true,
      path,
      message: error?.message || "Request failed",
      fallback,
    };
  }
}

function unwrap(value, fallback) {
  if (value && value.__lmcp_error) return fallback;
  return value ?? fallback;
}

function collectErrors(results) {
  const errors = {};
  Object.entries(results).forEach(([key, value]) => {
    if (value && value.__lmcp_error) errors[key] = value.message;
  });
  return errors;
}

export async function fetchCommandWallData() {
  const results = {
    summary: await readJson("/dashboard/summary", {}),
    submissionSummary: await readJson("/submission-analytics/summary", {}),
    profitSummary: await readJson("/submission-analytics/profit", {}),
    opportunities: await readJson("/opportunities", []),
    autonomousStatus: await readJson("/autonomous/status", {}),
  };

  return {
    summary: unwrap(results.summary, {}),
    submissionSummary: unwrap(results.submissionSummary, {}),
    profitSummary: unwrap(results.profitSummary, {}),
    opportunities: unwrap(results.opportunities, []),
    autonomousStatus: unwrap(results.autonomousStatus, {}),
    errors: collectErrors(results),
  };
}

export async function runAutonomousOnce() {
  const response = await fetch(`${API_BASE}/autonomous/run-once`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) throw new Error(`Run once failed: ${response.status}`);
  return response.json();
}

export async function updateAutonomousPolicy(payload) {
  const current = await readJson("/v48-autonomous/policy", {});
  const existingPolicy = current?.policy || current || {};

  const nextPolicy = {
    enabled: true,
    mode: "controlled",
    allow_email_send: false,
    allow_portal_upload: true,
    allow_portal_final_submit: true,
    require_confirmation_phrase: true,
    confirmation_phrase: "I CONFIRM FINAL SUBMISSION",
    minimum_profit_required: 30000,
    margin_percent: 25,
    apply_profit_floor: true,
    min_confidence: 0.35,
    zip_allowed_for_submission: false,
    captcha_bypass_allowed: false,
    ...existingPolicy,
    ...payload,
  };

  const response = await fetch(`${API_BASE}/v48-autonomous/policy`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(nextPolicy),
  });

  if (!response.ok) throw new Error(`Policy update failed: ${response.status}`);
  return response.json();
}
