// LMCP AutoQuote Frontend
// Step 8 - Autonomous Cycle Live Trigger + Dashboard Sync Service
//
// Drop-in path:
//   lmcp-frontend/src/services/autonomousCycle.js

const DEFAULT_API_BASE =
  import.meta?.env?.VITE_API_BASE ||
  import.meta?.env?.VITE_BACKEND_URL ||
  "http://127.0.0.1:8011";

export const API_BASE = DEFAULT_API_BASE.replace(/\/+$/, "");

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const text = await response.text();
  let data = {};

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!response.ok) {
    const message =
      data?.detail ||
      data?.message ||
      data?.error ||
      `${options.method || "GET"} ${path} failed with ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.path = path;
    error.payload = data;
    throw error;
  }

  return data;
}

async function firstSuccessful(calls) {
  const errors = [];

  for (const call of calls) {
    try {
      return await call();
    } catch (error) {
      errors.push({
        path: error.path,
        status: error.status,
        message: error.message,
      });
    }
  }

  const finalError = new Error(errors.map((e) => `${e.path}: ${e.message}`).join(" | "));
  finalError.errors = errors;
  throw finalError;
}

export async function getAutonomousStatus() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/autonomous/status");
      return { ...data, _resolved_path: "/autonomous/status" };
    },
    async () => {
      const data = await requestJson("/full-autonomous-cycle/status");
      return { ...data, _resolved_path: "/full-autonomous-cycle/status" };
    },
    async () => {
      const data = await requestJson("/system/control/status");
      return { ...data, _resolved_path: "/system/control/status" };
    },
  ]);
}

export async function runOneCycle() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/autonomous/run-once", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/autonomous/run-once" };
    },
    async () => {
      const data = await requestJson("/autonomous/run-sync", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/autonomous/run-sync" };
    },
    async () => {
      const data = await requestJson("/full-autonomous-cycle/run", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/full-autonomous-cycle/run" };
    },
  ]);
}

export async function getDashboardSummary() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/dashboard/summary");
      return { ...data, _resolved_path: "/dashboard/summary" };
    },
    async () => {
      const data = await requestJson("/health");
      return { ...data, _resolved_path: "/health" };
    },
  ]);
}

export async function getSubmissionSummary() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/submission-analytics/summary");
      return { ...data, _resolved_path: "/submission-analytics/summary" };
    },
    async () => {
      const data = await requestJson("/submission-history");
      return { ...data, _resolved_path: "/submission-history" };
    },
  ]);
}

export async function getProfitSummary() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/submission-analytics/profit");
      return { ...data, _resolved_path: "/submission-analytics/profit" };
    },
    async () => ({
      total_revenue: 0,
      total_profit: 0,
      _resolved_path: "fallback-zero-profit",
    }),
  ]);
}

export async function getPipelineSnapshot() {
  const [status, dashboard, submissions, profit] = await Promise.allSettled([
    getAutonomousStatus(),
    getDashboardSummary(),
    getSubmissionSummary(),
    getProfitSummary(),
  ]);

  return {
    status: status.status === "fulfilled" ? status.value : null,
    dashboard: dashboard.status === "fulfilled" ? dashboard.value : null,
    submissions: submissions.status === "fulfilled" ? submissions.value : null,
    profit: profit.status === "fulfilled" ? profit.value : null,
    errors: [status, dashboard, submissions, profit]
      .filter((item) => item.status === "rejected")
      .map((item) => item.reason?.message || String(item.reason)),
    refreshed_at: new Date().toISOString(),
  };
}

export function normalizeCycleResult(result = {}) {
  const lastResult = result?.last_result || result?.result || result;

  return {
    raw: result,
    resolved_path: result?._resolved_path || null,
    status: result?.status || result?.last_status || "ok",
    message: result?.message || result?.last_message || "Cycle completed",
    harvested:
      lastResult?.harvested ??
      lastResult?.total_harvested ??
      result?.harvested ??
      0,
    eligible:
      lastResult?.eligible ??
      lastResult?.total_eligible ??
      result?.eligible ??
      0,
    submitted:
      lastResult?.submitted ??
      lastResult?.total_submitted ??
      result?.submitted ??
      0,
    failed:
      lastResult?.failed ??
      lastResult?.total_failed ??
      result?.failed ??
      0,
    processed:
      lastResult?.processed ??
      lastResult?.total_processed ??
      result?.processed ??
      0,
    completed_at: new Date().toISOString(),
  };
}

export default {
  API_BASE,
  getAutonomousStatus,
  runOneCycle,
  getDashboardSummary,
  getSubmissionSummary,
  getProfitSummary,
  getPipelineSnapshot,
  normalizeCycleResult,
};
