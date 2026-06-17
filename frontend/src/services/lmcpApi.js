export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_BASE ||
  "http://127.0.0.1:8011";

export const WS_BASE = API_BASE.replace(/^http/i, "ws");

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    let body = "";
    try {
      body = await res.text();
    } catch {}
    throw new Error(`${path} failed: ${res.status} ${body}`);
  }

  return res.json();
}

export function buildFileUrl(path) {
  if (!path) return "";

  let clean = String(path).trim();

  if (clean.startsWith("http://") || clean.startsWith("https://")) {
    return clean;
  }

  clean = clean.replace(/^\/app\//, "");
  clean = clean.replace(/^\.\//, "");
  clean = clean.replace(/^\/+/, "");

  if (clean.startsWith("runtime/submission_proofs/")) {
    return `${API_BASE}/${clean}`;
  }

  if (clean.startsWith("monthly_quotes/")) {
    return `${API_BASE}/downloads/${clean.replace(/^monthly_quotes\//, "")}`;
  }

  return `${API_BASE}/${clean}`;
}

export function formatMoney(value) {
  const n = Number(value || 0);
  return `R ${n.toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("en-ZA", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(value);
  }
}

export function arr(value) {
  return Array.isArray(value) ? value : [];
}
