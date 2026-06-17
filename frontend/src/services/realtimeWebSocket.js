const DEFAULT_HTTP_BASE =
  import.meta?.env?.VITE_API_BASE ||
  import.meta?.env?.VITE_API_BASE_URL ||
  import.meta?.env?.VITE_BACKEND_URL ||
  "http://127.0.0.1:8011";

export const API_BASE = DEFAULT_HTTP_BASE.replace(/\/+$/, "");

function toWsBase(httpBase) {
  if (httpBase.startsWith("https://")) return httpBase.replace("https://", "wss://");
  if (httpBase.startsWith("http://")) return httpBase.replace("http://", "ws://");
  return `ws://${httpBase}`;
}

export const WS_BASE = (import.meta?.env?.VITE_WS_BASE || toWsBase(API_BASE)).replace(/\/+$/, "");
export const DEFAULT_WS_PATH = import.meta?.env?.VITE_WS_DASHBOARD_PATH || "/ws/dashboard";

const REFRESH_EVENT_TYPES = new Set([
  "tender_harvested",
  "tender_updated",
  "opportunity_created",
  "opportunity_updated",
  "pipeline_started",
  "pipeline_updated",
  "pipeline_completed",
  "quote_generated",
  "quote_ready",
  "submission_queued",
  "submission_dispatched",
  "submission_submitted",
  "submission_failed",
  "submission_retrying",
  "submission_manual_action_required",
  "dashboard_summary_updated",
  "audit_event",
  "alert_created",
]);

function parseMessage(raw) {
  if (!raw) return { type: "unknown", payload: raw };
  if (typeof raw !== "string") return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return { type: "text", payload: raw };
  }
}

function resolveMessageType(message) {
  return (
    message?.type ||
    message?.event_type ||
    message?.event ||
    message?.payload?.type ||
    message?.payload?.event_type ||
    message?.payload?.event ||
    "unknown"
  );
}

function shouldBroadcastRefresh(type) {
  return REFRESH_EVENT_TYPES.has(String(type || "").toLowerCase());
}

export class LMCPRealtimeWebSocket {
  constructor(options = {}) {
    this.path = options.path || DEFAULT_WS_PATH;
    this.url = options.url || `${WS_BASE}${this.path}`;
    this.maxReconnectDelayMs = options.maxReconnectDelayMs || 30000;
    this.initialReconnectDelayMs = options.initialReconnectDelayMs || 1000;
    this.heartbeatMs = options.heartbeatMs || 25000;
    this.socket = null;
    this.closedByUser = false;
    this.reconnectDelayMs = this.initialReconnectDelayMs;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.connectionId = 0;
  }

  connect() {
    this.closedByUser = false;
    this.connectionId += 1;
    const currentConnectionId = this.connectionId;

    this.cleanupSocketOnly();

    try {
      this.socket = new WebSocket(this.url);
    } catch (error) {
      this.dispatch("lmcp-ws-error", {
        url: this.url,
        error: error.message || String(error),
      });
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      if (currentConnectionId !== this.connectionId) return;
      this.reconnectDelayMs = this.initialReconnectDelayMs;
      this.dispatch("lmcp-ws-open", { url: this.url, connectedAt: new Date().toISOString() });
      this.startHeartbeat();
    };

    this.socket.onmessage = (event) => {
      if (currentConnectionId !== this.connectionId) return;
      const parsed = parseMessage(event.data);
      const type = resolveMessageType(parsed);
      const receivedAt = new Date().toISOString();

      const detail = { url: this.url, type, payload: parsed, raw: event.data, receivedAt };
      this.dispatch("lmcp-ws-message", detail);

      if (shouldBroadcastRefresh(type)) {
        this.dispatch("lmcp-refresh", {
          source: "LMCPRealtimeWebSocket",
          type,
          at: receivedAt,
          payload: parsed,
        });
      }
    };

    this.socket.onerror = () => {
      if (currentConnectionId !== this.connectionId) return;
      this.dispatch("lmcp-ws-error", { url: this.url, error: "WebSocket error", at: new Date().toISOString() });
    };

    this.socket.onclose = (event) => {
      if (currentConnectionId !== this.connectionId) return;
      this.stopHeartbeat();
      this.dispatch("lmcp-ws-close", {
        url: this.url,
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
        at: new Date().toISOString(),
      });

      if (!this.closedByUser) this.scheduleReconnect();
    };
  }

  disconnect() {
    this.closedByUser = true;
    this.clearReconnect();
    this.stopHeartbeat();

    if (this.socket) {
      try {
        this.socket.close(1000, "dashboard disconnect");
      } catch {
        // ignore
      }
    }

    this.cleanupSocketOnly();
  }

  send(payload) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;

    try {
      this.socket.send(typeof payload === "string" ? payload : JSON.stringify(payload));
      return true;
    } catch {
      return false;
    }
  }

  scheduleReconnect() {
    this.clearReconnect();

    const delay = this.reconnectDelayMs;
    this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, this.maxReconnectDelayMs);

    this.reconnectTimer = window.setTimeout(() => {
      if (!this.closedByUser) this.connect();
    }, delay);

    this.dispatch("lmcp-ws-reconnecting", { url: this.url, delayMs: delay, at: new Date().toISOString() });
  }

  clearReconnect() {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      this.send({ type: "dashboard_ping", at: new Date().toISOString() });
    }, this.heartbeatMs);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  cleanupSocketOnly() {
    if (!this.socket) return;
    this.socket.onopen = null;
    this.socket.onmessage = null;
    this.socket.onerror = null;
    this.socket.onclose = null;
    this.socket = null;
  }

  dispatch(eventName, detail) {
    window.dispatchEvent(new CustomEvent(eventName, { detail }));
  }
}

export function createRealtimeWebSocket(options = {}) {
  return new LMCPRealtimeWebSocket(options);
}

export default {
  API_BASE,
  WS_BASE,
  DEFAULT_WS_PATH,
  LMCPRealtimeWebSocket,
  createRealtimeWebSocket,
};
