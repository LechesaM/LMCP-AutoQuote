const API_BASE =
  (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8011").replace(/\/$/, "");

async function requestJson(path, options = {}) {
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

export async function getOperatorActionSummary() {
  return requestJson("/operator-actions/summary", { method: "GET" });
}

export async function runOperatorAction(action, payload) {
  return requestJson(`/operator-actions/${action}`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export { API_BASE };
