const API_BASE =
  (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

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

async function tryPaths(paths, options = {}) {
  const errors = [];

  for (const path of paths) {
    try {
      const data = await requestJson(path, options);
      return { ok: true, path, data };
    } catch (error) {
      errors.push(`${path}: ${error.message}`);
    }
  }

  throw new Error(errors.join(" | "));
}

export async function getAutonomousStatus() {
  return tryPaths(["/autonomous/status"], { method: "GET" });
}

export async function enableAutonomousSystem() {
  return tryPaths(
    ["/autonomous/enable", "/autonomous/start", "/system/enable"],
    { method: "POST" }
  );
}

export async function disableAutonomousSystem() {
  return tryPaths(
    ["/autonomous/disable", "/autonomous/stop", "/system/disable"],
    { method: "POST" }
  );
}

export async function runAutonomousCycleNow() {
  return tryPaths(
    ["/autonomous/run-once", "/autonomous/run_once"],
    { method: "POST" }
  );
}

export { API_BASE };

