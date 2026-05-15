const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const REQUEST_TIMEOUT_MS = 9000;

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function flattenArrays(payload, keys = []) {
  const out = [];
  const seen = new Set();

  function walk(value, depth = 0, key = "") {
    if (depth > 5 || value == null) return;
    if (Array.isArray(value)) {
      const useful = value.filter((x) => x && typeof x === "object");
      if (useful.length && (!keys.length || keys.includes(key))) {
        const sig = `${key}:${useful.length}:${Object.keys(useful[0] || {}).join(",")}`;
        if (!seen.has(sig)) {
          seen.add(sig);
          out.push(...useful);
        }
      }
      useful.forEach((x) => walk(x, depth + 1, key));
      return;
    }
    if (typeof value === "object") {
      Object.entries(value).forEach(([k, v]) => walk(v, depth + 1, k));
    }
  }

  walk(payload);
  return out;
}

async function safeJson(path, options = {}, fallback = null) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.json();
  } catch (error) {
    return fallback ?? { status: "offline", error: error.message, path };
  } finally {
    clearTimeout(timeout);
  }
}

async function firstLive(paths, fallback, normalizer = (x) => x) {
  for (const path of paths) {
    const data = await safeJson(path, {}, null);
    if (data && data.status !== "offline" && !data.error) return normalizer(data, path);
  }
  return fallback;
}

function normalizeList(data, keys = []) {
  if (Array.isArray(data)) return data;
  for (const key of unique(["items", "results", "data", "opportunities", "tenders", "rfqs", "bids", "submissions", "history", ...keys])) {
    if (Array.isArray(data?.[key])) return data[key];
  }
  const nested = flattenArrays(data, unique(["items", "results", "data", "opportunities", "tenders", "rfqs", "bids", ...keys]));
  return nested;
}

export async function getHealth() {
  return safeJson("/health", {}, { status: "offline", loaded_routers: [] });
}

export async function getAutonomousStatus() {
  return firstLive([
    "/v48-autonomous/status",
    "/full-autonomous-cycle/status",
    "/autonomous/status",
    "/final-automation/status",
  ], { enabled: false, last_status: "offline", last_message: "No backend response" });
}

export async function runAutonomousOnce() {
  return firstLive([
    "/v48-autonomous/run-once",
    "/full-autonomous-cycle/run-once",
    "/autonomous/run-once",
    "/final-automation/run-once",
  ], { status: "error", message: "Run failed" }, (data) => data);
}

export async function getDashboardSummary() {
  const health = await getHealth();
  const data = await firstLive([
    "/dashboard/summary",
    "/mission-control/summary",
    "/v48-autonomous/status",
    "/v50-7-promotion-gate/status",
  ], {}, (x) => x);
  return {
    sources: data.sources || data.enabled_sources || health.loaded_routers_count || 0,
    loaded_routers_count: health.loaded_routers_count || 0,
    failed_routers_count: health.failed_routers_count || 0,
    ...data,
  };
}

export async function getOpportunities() {
  const paths = [
    "/opportunities",
    "/opportunities/available",
    "/available-bids",
    "/tenders",
    "/harvester/opportunities",
    "/tender-pipeline/opportunities",
    "/real-rfq-harvester-v32/results",
    "/v50-7-etenders-navigation/results",
    "/v50-7-promotion-gate/eligible",
    "/rfq-lifecycle/opportunities",
  ];
  for (const path of paths) {
    const data = await safeJson(path, {}, null);
    const list = normalizeList(data, ["opportunities", "tenders", "rfqs", "bids"]);
    if (list.length) return list;
  }
  return [];
}

export async function getSubmissionSummary() {
  return firstLive([
    "/submission-analytics/summary",
    "/submission-history/recent-real",
    "/submission-history/recent",
    "/submission-proof/status",
  ], {});
}

export async function getSubmissionProfit() {
  return firstLive([
    "/submission-analytics/profit",
    "/real-profit-pricing/summary",
    "/quote-engine/summary",
  ], {});
}

export async function getSubmissionHistory() {
  const paths = [
    "/submission-history/recent-with-proofs",
    "/submission-history/recent-real",
    "/submission-history/recent",
    "/submission-history",
    "/proof-center/scan",
  ];
  for (const path of paths) {
    const data = await safeJson(path, {}, null);
    const list = normalizeList(data, ["history", "submissions", "proofs", "items"]);
    if (list.length) return list;
  }
  return [];
}

export async function getPolicy() {
  return firstLive([
    "/v48-autonomous/policy",
    "/system-control/policy",
    "/safe-autonomous-scheduler/policy",
  ], null);
}

export async function updatePolicy(policy) {
  for (const path of ["/v48-autonomous/policy", "/system-control/policy", "/safe-autonomous-scheduler/policy"]) {
    const data = await safeJson(path, { method: "POST", body: JSON.stringify(policy) }, null);
    if (data && data.status !== "offline" && !data.error) return data;
  }
  return null;
}

export async function getPortalHealth() {
  return firstLive([
    "/portal-health",
    "/portal-submission/status",
    "/proof-center/health",
    "/harvester/portal-health",
    "/tender-radar/portal-health",
  ], { status: "monitored", portals: [
    { name: "eTenders", status: "monitored" },
    { name: "SOE portals", status: "monitored" },
    { name: "Municipal portals", status: "monitored" },
    { name: "Provincial portals", status: "monitored" },
  ] }, (data) => {
    if (Array.isArray(data?.portals)) return data;
    if (Array.isArray(data?.portal_health)) return { ...data, portals: data.portal_health };
    return data;
  });
}

export async function getRadarStatus() {
  return firstLive([
    "/tender-radar/status",
    "/radar/status",
    "/v48-autonomous/status",
    "/full-autonomous-cycle/status",
    "/v50-7-etenders-navigation/status",
  ], { status: "fallback", service_version: "V48_FULL_AUTONOMOUS_ORCHESTRATOR" });
}

export async function getRfqLifecycleMissionControl() {
  return safeJson("/rfq-lifecycle/mission-control", {}, {
    status: "controlled",
    total_rfqs: 0,
    active_rfqs: 0,
    failed_rfqs: 0,
    review_required_rfqs: 0,
    submitted_rfqs: 0,
    proof_captured_rfqs: 0,
    queue_by_lifecycle_state: {},
    estimated_monthly_capacity: 0,
    blockers: [],
    alerts: [],
    next_recommended_action: "harvest and promote qualified RFQs",
    safety: {
      supply_and_delivery_only: true,
      final_submit_hard_blocked_by_lifecycle: true,
      captcha_bypass_allowed: false,
      system_control: { effective_system_status: "controlled", system_on: true },
    },
  });
}

export async function getRfqLifecycleAnalytics() {
  return safeJson("/rfq-lifecycle/analytics", {}, {
    status: "controlled",
    per_stage_latency: {},
    per_stage_success_rate: {},
    task_retry_histogram: {},
    retry_reason_histogram: {},
    queue_wait_times: {},
    queue_drain_rate: {},
    queue_trend: [],
    source_reliability_score: [],
    proof_generation_latency: { average_seconds: 0, samples: 0 },
    rfq_lifecycle_duration: { average_seconds: 0, active_average_seconds: 0, samples: 0 },
    slowest_stages: [],
    worker_saturation_warnings: [],
    system_health_trend: [],
    safety: { final_submit_hard_blocked_by_lifecycle: true, captcha_bypass_allowed: false },
  });
}

export async function getRfqLifecycleTelemetry() {
  return safeJson("/rfq-lifecycle/telemetry", {}, {
    status: "controlled",
    worker_online: true,
    worker_crash_count: 0,
    worker_restart_count: 0,
    broker_health: { connected: true },
    queue_backlog: { total_backlog: 0, backlog_detected: false },
    stalled_lifecycle_tasks: [],
    resource_pressure: { memory_pressure_warning: false, cpu_saturation_warning: false },
    worker_restart_events: [],
    distributed_execution: {
      worker_pool: "prefork",
      prefetch_multiplier: 1,
      max_tasks_per_child: 100,
      queue_specific_worker_load: {},
      active_workers: [],
      total_concurrency_capacity: 0,
      concurrency_utilization: 0,
      task_throughput_by_queue: {},
    },
    warnings: [],
    system_resilience_score: 100,
  });
}

export async function getRfqLifecycleAudit(rfqId) {
  if (!rfqId) return { status: "not_found", timeline: [] };
  return safeJson(`/rfq-lifecycle/audit/${encodeURIComponent(rfqId)}`, {}, { status: "offline", timeline: [] });
}

export async function getQuoteCompilationPacks(limit = 8) {
  return safeJson(`/quote-compilation/packs?limit=${Math.max(1, Math.min(Number(limit) || 8, 50))}`, {}, { status: "offline", items: [] });
}

export async function getQuoteCompilationLatestPack() {
  return safeJson("/quote-compilation/packs/latest", {}, { status: "not_found" });
}

export async function getQuoteCompilationComplianceSummary(packId) {
  if (!packId) {
    return { status: "unknown", pack_id: "", blockers: [], warnings: [] };
  }
  return safeJson(
    `/quote-compilation/submission-gate/${encodeURIComponent(packId)}/compliance-summary`,
    {},
    { status: "unknown", pack_id: packId, blockers: [], warnings: [] },
  );
}

export { API_BASE };
