// LMCP AutoQuote Frontend
// Step 7 - ON/OFF System Control Service
//
// Drop-in path:
//   lmcp-frontend/src/services/systemControl.js
//
// Purpose:
//   Connects the ON/OFF dashboard controls to the real LMCP backend.
//
// Expected backend endpoints:
//   GET  /autonomous/status
//   POST /system/control/on
//   POST /system/control/off
//   POST /autonomous/run-once
//
// Safe fallbacks included for older endpoint variants.

const DEFAULT_API_BASE =
  import.meta?.env?.VITE_API_BASE ||
  import.meta?.env?.VITE_BACKEND_URL ||
  "http://127.0.0.1:8011";

export const API_BASE = DEFAULT_API_BASE.replace(/\/+$/, "");

async function requestJson(path, options = {}) {
  const url = `${API_BASE}${path}`;

  const response = await fetch(url, {
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
        message: error.message,
        status: error.status,
        path: error.path,
      });
    }
  }

  const finalError = new Error(errors.map((e) => `${e.path}: ${e.message}`).join(" | "));
  finalError.errors = errors;
  throw finalError;
}

export function normalizeSystemStatus(raw = {}) {
  const enabled =
    raw.enabled ??
    raw.system_on ??
    raw.autonomous_enabled ??
    raw.is_enabled ??
    raw.running ??
    false;

  const lastStatus =
    raw.last_status ||
    raw.status ||
    raw.engine_status ||
    raw.state ||
    "unknown";

  const lastResult = raw.last_result || raw.result || null;

  let processed = 0;
  if (lastResult && typeof lastResult === "object") {
    processed =
      lastResult.processed ??
      lastResult.total_processed ??
      lastResult.submitted ??
      lastResult.harvested ??
      lastResult.count ??
      0;
  }

  return {
    raw,
    enabled: Boolean(enabled),
    last_status: String(lastStatus || "unknown"),
    last_message: raw.last_message || raw.message || "No status message returned",
    last_run_at: raw.last_run_at || raw.last_run || raw.updated_at || null,
    updated_at: raw.updated_at || raw.checked_at || new Date().toISOString(),
    last_result: lastResult,
    processed,
    resolved_path: raw._resolved_path || raw.resolved_path || null,
  };
}

export async function getSystemStatus() {
  const data = await firstSuccessful([
    async () => {
      const result = await requestJson("/autonomous/status");
      return { ...result, _resolved_path: "/autonomous/status" };
    },
    async () => {
      const result = await requestJson("/system/control/status");
      return { ...result, _resolved_path: "/system/control/status" };
    },
    async () => {
      const result = await requestJson("/system/status");
      return { ...result, _resolved_path: "/system/status" };
    },
    async () => {
      const result = await requestJson("/health");
      return {
        enabled: true,
        last_status: result.status || "healthy",
        last_message: result.service || "Backend healthy",
        updated_at: new Date().toISOString(),
        _resolved_path: "/health",
        raw_health: result,
      };
    },
  ]);

  return normalizeSystemStatus(data);
}

export async function turnSystemOn() {
  const result = await firstSuccessful([
    async () => {
      const data = await requestJson("/system/control/on", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/system/control/on" };
    },
    async () => {
      const data = await requestJson("/autonomous/enable", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/autonomous/enable" };
    },
    async () => {
      const data = await requestJson("/autonomous/start", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/autonomous/start" };
    },
  ]);

  return result;
}

export async function turnSystemOff() {
  const result = await firstSuccessful([
    async () => {
      const data = await requestJson("/system/control/off", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/system/control/off" };
    },
    async () => {
      const data = await requestJson("/autonomous/disable", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/autonomous/disable" };
    },
    async () => {
      const data = await requestJson("/autonomous/stop", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/autonomous/stop" };
    },
  ]);

  return result;
}

export async function runOneAutonomousCycle() {
  const result = await firstSuccessful([
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

  return result;
}

export async function pauseHarvesting() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/system/control/pause-harvest", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/system/control/pause-harvest" };
    },
  ]);
}

export async function pauseSubmissions() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/system/control/pause-submissions", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/system/control/pause-submissions" };
    },
  ]);
}

export async function resumeAll() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/system/control/resume-all", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/system/control/resume-all" };
    },
  ]);
}

export async function emergencyStop() {
  return firstSuccessful([
    async () => {
      const data = await requestJson("/system/control/emergency-stop", { method: "POST", body: "{}" });
      return { ...data, _resolved_path: "/system/control/emergency-stop" };
    },
  ]);
}

export default {
  API_BASE,
  getSystemStatus,
  turnSystemOn,
  turnSystemOff,
  runOneAutonomousCycle,
  pauseHarvesting,
  pauseSubmissions,
  resumeAll,
  emergencyStop,
  normalizeSystemStatus,
};
