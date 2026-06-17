const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

export async function getManualReviewQueue() {
  const res = await fetch(`${API_BASE}/dashboard/manual-review/queue`, {
    credentials: "include",
  });
  return res.json();
}

export async function getManualReviewPilotSummary() {
  const res = await fetch(`${API_BASE}/dashboard/manual-review/pilot-summary`, {
    credentials: "include",
  });
  return res.json();
}
