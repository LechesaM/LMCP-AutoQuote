const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function safeJson(path, options = {}, fallback = null) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || 9000);
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

export async function getHealth() {
  return safeJson("/health", {}, { status: "offline", loaded_routers: [] });
}

export async function getAutonomousStatus() {
  return safeJson("/autonomous/status", {}, { enabled: false, last_status: "offline", last_message: "No backend response" });
}

export async function runAutonomousOnce() {
  return safeJson("/autonomous/run-once", { method: "POST", timeout: 30000 }, { status: "error", message: "Run failed" });
}

export async function getDashboardSummary() {
  return safeJson("/dashboard/summary", {}, {});
}

export async function getOpportunities() {
  const data = await safeJson("/opportunities", {}, []);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.opportunities)) return data.opportunities;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

export async function getSubmissionSummary() {
  return safeJson("/submission-analytics/summary", {}, {});
}

export async function getSubmissionProfit() {
  return safeJson("/submission-analytics/profit", {}, {});
}

export async function getSubmissionHistory() {
  const data = await safeJson("/submission-history", {}, []);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.history)) return data.history;
  if (Array.isArray(data?.submissions)) return data.submissions;
  return [];
}

export async function getPolicy() {
  return safeJson("/v48-autonomous/policy", {}, null);
}

export async function updatePolicy(policy) {
  return safeJson("/v48-autonomous/policy", { method: "POST", body: JSON.stringify(policy) }, null);
}

export async function getPortalHealth() {
  const paths = ["/portal-health", "/harvester/portal-health", "/tender-radar/portal-health"];
  for (const path of paths) {
    const data = await safeJson(path, {}, null);
    if (data && data.status !== "offline") return data;
  }
  return { status: "unknown", portals: [] };
}

export async function getRadarStatus() {
  const paths = ["/tender-radar/status", "/radar/status", "/v48-autonomous/status"];
  for (const path of paths) {
    const data = await safeJson(path, {}, null);
    if (data && data.status !== "offline") return data;
  }
  return { status: "unknown" };
}

export async function getRfqLifecycleMissionControl() {
  return safeJson("/rfq-lifecycle/mission-control", {}, {
    status: "offline",
    total_rfqs: 0,
    active_rfqs: 0,
    failed_rfqs: 0,
    review_required_rfqs: 0,
    submitted_rfqs: 0,
    proof_captured_rfqs: 0,
    queue_by_lifecycle_state: {},
    estimated_monthly_capacity: 0,
    blockers: ["RFQ lifecycle endpoint offline"],
    alerts: [],
    next_recommended_action: "verify backend connectivity",
    safety: {
      supply_and_delivery_only: true,
      final_submit_hard_blocked_by_lifecycle: true,
      captcha_bypass_allowed: false,
    },
  });
}

export async function getRfqLifecycleAnalytics() {
  return safeJson("/rfq-lifecycle/analytics", {}, {
    status: "offline",
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
    worker_saturation_warnings: ["RFQ lifecycle analytics endpoint offline"],
    system_health_trend: [],
    safety: {
      final_submit_hard_blocked_by_lifecycle: true,
      captcha_bypass_allowed: false,
    },
  });
}

export async function getRfqLifecycleTelemetry() {
  return safeJson("/rfq-lifecycle/telemetry", {}, {
    status: "offline",
    worker_online: false,
    worker_crash_count: 0,
    worker_restart_count: 0,
    broker_health: { connected: false },
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
    warnings: ["RFQ lifecycle telemetry endpoint offline"],
    system_resilience_score: 0,
  });
}

export async function getRfqLifecycleAudit(rfqId) {
  if (!rfqId) return { status: "not_found", timeline: [] };
  return safeJson(`/rfq-lifecycle/audit/${encodeURIComponent(rfqId)}`, {}, { status: "offline", timeline: [] });
}

export { API_BASE };
