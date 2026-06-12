const API_BASE =
  (
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");

async function readJson(path, fallback) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("LMCP API error:", path, error);

    return {
      __lmcp_error: true,
      path,
      message: error?.message || "Request failed",
      fallback,
    };
  }
}

function unwrap(value, fallback) {
  if (value && value.__lmcp_error) {
    return fallback;
  }

  return value ?? fallback;
}

export { API_BASE };

export async function getHealth() {
  return unwrap(await readJson("/health", {}), {});
}

export async function getAutonomousStatus() {
  return unwrap(await readJson("/v48-autonomous/status", {}), {});
}

export async function getDashboardSummary() {
  return unwrap(await readJson("/dashboard/summary", {}), {});
}

export async function getOpportunities() {
  return unwrap(await readJson("/opportunities", []), []);
}

export async function getPortalHealth() {
  return unwrap(await readJson("/portal-health", {}), {});
}

export async function getRadarStatus() {
  return unwrap(await readJson("/radar/status", {}), {});
}

export async function getSubmissionHistory() {
  return unwrap(await readJson("/submission-history/recent", []), []);
}

export async function getSubmissionProfit() {
  return unwrap(await readJson("/submission-analytics/profit", {}), {});
}

export async function getSubmissionSummary() {
  return unwrap(await readJson("/submission-analytics/summary", {}), {});
}

export async function getPolicy() {
  return unwrap(await readJson("/v48-autonomous/policy", {}), {});
}

export async function getRfqLifecycleMissionControl() {
  return unwrap(await readJson("/rfq-lifecycle/mission-control", {}), {});
}

export async function getRfqLifecycleAnalytics() {
  return unwrap(await readJson("/rfq-lifecycle/analytics", {}), {});
}

export async function getRfqLifecycleTelemetry() {
  return unwrap(await readJson("/rfq-lifecycle/telemetry", {}), {});
}

export async function runAutonomousOnce() {
  const response = await fetch(`${API_BASE}/rfq-lifecycle/run-live-pilot`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      limit: 5,
      timeout_seconds: 15,
      max_concurrent_downloads: 4,
    }),
  });

  if (!response.ok) {
    throw new Error(`Run once failed: ${response.status}`);
  }

  return response.json();
}

export async function updatePolicy(payload = {}) {
  const current = await getPolicy();
  const policyPayload = {
    enabled: true,
    mode: "controlled",
    allow_email_send: false,
    allow_portal_upload: false,
    allow_portal_final_submit: false,
    require_confirmation_phrase: true,
    confirmation_phrase: "I CONFIRM FINAL SUBMISSION",
    minimum_profit_required: 30000,
    margin_percent: 25,
    apply_profit_floor: true,
    min_confidence: 0.35,
    zip_allowed_for_submission: false,
    captcha_bypass_allowed: false,
    ...current,
    ...payload,
  };

  const response = await fetch(`${API_BASE}/v48-autonomous/policy`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(policyPayload),
  });

  if (!response.ok) {
    throw new Error(`Policy update failed: ${response.status}`);
  }

  return response.json();
}
