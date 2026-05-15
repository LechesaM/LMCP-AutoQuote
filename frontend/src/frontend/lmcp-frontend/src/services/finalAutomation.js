const DEFAULT_API_BASE =
  import.meta?.env?.VITE_API_BASE ||
  import.meta?.env?.VITE_API_BASE_URL ||
  import.meta?.env?.VITE_BACKEND_URL ||
  "http://127.0.0.1:8000";

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
    const error = new Error(data?.detail || data?.message || `${path} failed`);
    error.payload = data;
    throw error;
  }

  return data;
}

export async function getFinalAutomationStatus() {
  return requestJson("/final-automation/status");
}

export async function runGoLiveCheck() {
  return requestJson("/final-automation/go-live-check");
}

export async function runFinalAutomationOnce(payload = {}) {
  return requestJson("/final-automation/run-once", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
