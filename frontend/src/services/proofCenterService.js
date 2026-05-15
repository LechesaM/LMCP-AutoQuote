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

export async function getProofCenter(limit = 100, submittedOnly = false, q = "") {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (submittedOnly) params.set("submitted_only", "true");
  if (q) params.set("q", q);

  const response = await fetch(`${API_BASE}/proof-center?${params.toString()}`);
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Proof Center failed: ${response.status}`);
  }
  return readJson(response);
}

export async function scanProofCenter() {
  const response = await fetch(`${API_BASE}/proof-center/scan`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Proof scan failed: ${response.status}`);
  }
  return readJson(response);
}

export async function getProofRecord(recordId) {
  const response = await fetch(`${API_BASE}/proof-center/${encodeURIComponent(recordId)}`);
  if (!response.ok) {
    const error = await readJson(response);
    throw new Error(error?.detail?.message || error?.message || `Proof record failed: ${response.status}`);
  }
  return readJson(response);
}

export function proofDownloadUrl(recordId) {
  return `${API_BASE}/proof-center/${encodeURIComponent(recordId)}/download-proof`;
}

export function proofScreenshotUrl(recordId, screenshotIndex = 0) {
  return `${API_BASE}/proof-center/${encodeURIComponent(recordId)}/download-screenshot?screenshot_index=${screenshotIndex}`;
}

export function runtimeFileUrl(path) {
  if (!path) return "";
  const clean = String(path).replace(/^\/app\//, "").replace(/^runtime\//, "");
  if (String(path).startsWith("runtime/")) return `${API_BASE}/${path}`;
  return `${API_BASE}/runtime/${clean}`;
}
