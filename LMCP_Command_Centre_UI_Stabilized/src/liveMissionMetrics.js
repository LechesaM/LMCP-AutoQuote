// lmcp-frontend/src/services/liveMissionMetrics.js

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.REACT_APP_API_BASE_URL ||
  "http://localhost:8000";

async function getJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  const text = await response.text();

  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || `Request failed: ${response.status}`);
  }

  return data;
}

export async function fetchAutonomousStatus() {
  return getJson("/autonomous/status");
}

export async function fetchSubmissionProfit() {
  return getJson("/submission-analytics/profit");
}

export async function fetchSubmissionSummary() {
  return getJson("/submission-analytics/summary");
}

export async function fetchSubmissionHistory() {
  return getJson("/submission-history/recent");
}

export function detectSystemMode(statusPayload) {
  const policy = statusPayload?.policy || statusPayload?.last_result?.policy || null;

  if (policy) {
    if (policy.enabled === false) return "OFF";
    if (policy.mode === "full_autonomous") return "FULL";
    if (policy.mode === "controlled") return "SAFE";
  }

  if (statusPayload?.enabled === false) return "OFF";

  const text = JSON.stringify(statusPayload || {}).toLowerCase();
  if (text.includes("full_autonomous")) return "FULL";
  if (text.includes("controlled")) return "SAFE";
  if (text.includes("disabled") || text.includes("off")) return "OFF";

  return statusPayload?.enabled ? "SAFE" : "OFF";
}

export function formatRand(value) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0,
  }).format(amount);
}
