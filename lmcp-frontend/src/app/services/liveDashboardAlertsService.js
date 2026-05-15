const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_BASE ||
  "http://localhost:8000";

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { status: "error", message: text || "Invalid JSON response" };
  }
}

export async function getPortalSubmissionStatus(limit = 25) {
  const response = await fetch(`${API_BASE}/portal-submission/status?limit=${limit}`);
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Portal status failed: ${response.status}`);
  }
  return readJson(response);
}

export async function getProofCenter(limit = 25) {
  const response = await fetch(`${API_BASE}/proof-center?limit=${limit}`);
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Proof Center failed: ${response.status}`);
  }
  return readJson(response);
}

export async function getProductionLockStatus(limit = 25) {
  const response = await fetch(`${API_BASE}/production-lock/status?limit=${limit}`);
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Production Lock failed: ${response.status}`);
  }
  return readJson(response);
}

export async function getHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Health failed: ${response.status}`);
  }
  return readJson(response);
}

export function requestBrowserNotifications() {
  if (!("Notification" in window)) return Promise.resolve("unsupported");
  if (Notification.permission === "granted") return Promise.resolve("granted");
  if (Notification.permission === "denied") return Promise.resolve("denied");
  return Notification.requestPermission();
}

export function notify(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  new Notification(title, {
    body,
    icon: "/favicon.ico",
  });
}

export function proofDownloadUrl(recordId) {
  return `${API_BASE}/proof-center/${encodeURIComponent(recordId)}/download-proof`;
}

export function proofScreenshotUrl(recordId, screenshotIndex = 0) {
  return `${API_BASE}/proof-center/${encodeURIComponent(recordId)}/download-screenshot?screenshot_index=${screenshotIndex}`;
}
