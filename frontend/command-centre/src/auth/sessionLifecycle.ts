const listeners = new Set();

function decodeBase64Url(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4 || 4)) % 4);
  if (typeof atob !== "function") {
    return "";
  }
  return atob(padded);
}

export function decodeTokenExpiry(token) {
  if (!token || typeof token !== "string" || !token.includes(".")) {
    return 0;
  }
  try {
    const payload = JSON.parse(decodeBase64Url(token.split(".")[1]));
    const expiry = Number(payload?.exp || 0);
    return Number.isFinite(expiry) ? expiry * 1000 : 0;
  } catch (error) {
    return 0;
  }
}

export function isTokenExpired(token, now = Date.now()) {
  const expiresAt = decodeTokenExpiry(token);
  return Boolean(expiresAt && expiresAt <= now);
}

export function subscribeToSessionExpired(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function notifySessionExpired(event = {}) {
  for (const listener of listeners) {
    try {
      listener({
        reason: event.reason || "Session expired",
        source: event.source || "runtime",
        at: event.at || new Date().toISOString(),
      });
    } catch (error) {
      // ignore listener failures
    }
  }
}
