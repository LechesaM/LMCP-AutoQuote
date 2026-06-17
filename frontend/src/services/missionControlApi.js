const API_BASE =
  (
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    "http://127.0.0.1:8011"
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

function collectErrors(results) {
  const errors = {};

  Object.entries(results).forEach(([key, value]) => {
    if (value && value.__lmcp_error) {
      errors[key] = value.message;
    }
  });

  return errors;
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeNumber(value, fallback = 0) {
  const n = Number(value);

  return Number.isFinite(n) ? n : fallback;
}

export async function fetchMissionControlData() {
  const [
    radar,
    portalHealth,
    missionControl,
    telemetry,
    analytics,
    autonomousStatus,
    opportunities,
    dashboardSummary,
    submissionSummary,
  ] = await Promise.all([
    readJson("/radar/status", {}),
    readJson("/portal-health", {}),
    readJson("/rfq-lifecycle/mission-control", {}),
    readJson("/rfq-lifecycle/telemetry", {}),
    readJson("/rfq-lifecycle/analytics", {}),
    readJson("/supply-command/status", {}),
    readJson("/opportunities", []),
    readJson("/dashboard/summary", {}),
    readJson("/submission-analytics/summary", {}),
  ]);

  const safeRadar = unwrap(radar, {});
  const safePortalHealth = unwrap(portalHealth, {});
  const safeMissionControl = unwrap(missionControl, {});
  const safeTelemetry = unwrap(telemetry, {});
  const safeAnalytics = unwrap(analytics, {});
  const safeAutonomousStatus = unwrap(autonomousStatus, {});
  const safeOpportunities = unwrap(opportunities, []);
  const safeDashboardSummary = unwrap(dashboardSummary, {});
  const safeSubmissionSummary = unwrap(submissionSummary, {});

  const radarData = safeRadar?.radar || {};

  const proofCaptured = safeNumber(
    radarData.proof_captured ||
      safeMissionControl?.proof_captured_rfqs ||
      safeMissionControl?.proof_captured ||
      0
  );

  const failedRfqs = safeNumber(
    radarData.failed_rfqs ||
      safeMissionControl?.failed_rfqs ||
      0
  );

  const reviewRequired = safeNumber(
    radarData.review_required ||
      safeMissionControl?.review_required_rfqs ||
      0
  );

  const estimatedMonthlyCapacity = safeNumber(
    radarData.estimated_monthly_capacity ||
      safeMissionControl?.estimated_monthly_capacity ||
      0
  );

  const totalRfqs = safeNumber(
    safeMissionControl?.total_rfqs ||
      safeDashboardSummary?.total_rfqs ||
      safeOpportunities?.length ||
      0
  );

  const queueBacklog = safeNumber(
    radarData.queue_backlog ||
      safeTelemetry?.queue_backlog ||
      0
  );

  const onlineWorkers = safeNumber(
    radarData.online_workers ||
      safeTelemetry?.online_workers ||
      0
  );

  const workerOnline =
    radarData.worker_online ??
    safeTelemetry?.worker_online ??
    false;

  const lifecycleHealthScore = safeNumber(
    radarData.lifecycle_health_score ||
      safeTelemetry?.lifecycle_health_score ||
      0
  );

  const resilienceScore = safeNumber(
    radarData.system_resilience_score ||
      safeTelemetry?.system_resilience_score ||
      0
  );

  return {
    summary: {
      total_rfqs: totalRfqs,
      proof_captured_rfqs: proofCaptured,
      failed_rfqs: failedRfqs,
      review_required_rfqs: reviewRequired,
      lifecycle_health_score: lifecycleHealthScore,
      estimated_monthly_capacity: estimatedMonthlyCapacity,
      queue_backlog: queueBacklog,
      worker_online: workerOnline,
      online_workers: onlineWorkers,
      system_resilience_score: resilienceScore,
    },

    radar: safeRadar,

    portalHealth: {
      ...safePortalHealth,
      portals: safeArray(safePortalHealth?.portals),
    },

    telemetry: safeTelemetry,

    analytics: safeAnalytics,

    submissionSummary: {
      submitted:
        safeNumber(
          safeSubmissionSummary?.submitted
        ) || proofCaptured,

      failed:
        safeNumber(
          safeSubmissionSummary?.failed
        ) || failedRfqs,

      review_required:
        safeNumber(
          safeSubmissionSummary?.review_required
        ) || reviewRequired,
    },

    profitSummary: {
      estimated_monthly_capacity: estimatedMonthlyCapacity,
    },

    submissionHistory: safeArray(
      safeAnalytics?.submission_history
    ),

    autonomousStatus: {
      enabled:
        safeAutonomousStatus?.enabled ?? true,

      mode:
        safeAutonomousStatus?.mode ||
        "controlled",

      safety_locked: true,

      no_final_submit: true,
      no_email_send: true,
      no_captcha_bypass: true,

      ...safeAutonomousStatus,
    },

    lifecycle: safeMissionControl,

    lifecycleTelemetry: safeTelemetry,

    lifecycleAnalytics: safeAnalytics,

    opportunities: safeArray(safeOpportunities),

    errors: collectErrors({
      radar,
      portalHealth,
      missionControl,
      telemetry,
      analytics,
      autonomousStatus,
      opportunities,
      dashboardSummary,
      submissionSummary,
    }),
  };
}

export async function runAutonomousOnce() {
  const response = await fetch(
    `${API_BASE}/rfq-lifecycle/run-live-pilot`,
    {
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
    }
  );

  if (!response.ok) {
    throw new Error(`Run once failed: ${response.status}`);
  }

  return response.json();
}

export async function updateAutonomousPolicy(payload = {}) {
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

    ...payload,
  };

  const response = await fetch(
    `${API_BASE}/v48-autonomous/policy`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(policyPayload),
    }
  );

  if (!response.ok) {
    throw new Error(
      `Policy update failed: ${response.status}`
    );
  }

  return response.json();
}
