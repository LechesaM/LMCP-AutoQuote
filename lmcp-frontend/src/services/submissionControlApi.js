const API_BASE =
  (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const rawText = await response.text();
  let data = null;

  try {
    data = rawText ? JSON.parse(rawText) : null;
  } catch {
    data = rawText || null;
  }

  if (!response.ok) {
    const message =
      (data && typeof data === "object" && (data.detail || data.message || data.error)) ||
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return data;
}

export async function runSubmissionScheduler(limit = 10) {
  return apiRequest(`/submission-scheduler/run-now?limit=${encodeURIComponent(limit)}`, {
    method: "POST",
  });
}

export async function getSubmissionSummary() {
  return apiRequest("/submission-analytics/summary", {
    method: "GET",
  });
}

export async function getSubmissionProfit() {
  return apiRequest("/submission-analytics/profit", {
    method: "GET",
  });
}

export async function getSubmissionHistory(limit = 20) {
  return apiRequest(`/submission-history?limit=${encodeURIComponent(limit)}`, {
    method: "GET",
  });
}

export { API_BASE };
