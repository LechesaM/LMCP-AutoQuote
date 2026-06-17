const WS_BASE =
  (import.meta.env.VITE_WS_BASE_URL || "ws://127.0.0.1:8011").replace(/\/$/, "");

const DEFAULT_PATHS = [
  "/ws/live",
  "/ws/dashboard",
  "/ws/tenders",
  "/ws",
];

let socket = null;
let reconnectTimer = null;
let manualClose = false;

function dispatchStatus(detail) {
  window.dispatchEvent(new CustomEvent("lmcp-ws-status", { detail }));
}

function dispatchMessage(detail) {
  window.dispatchEvent(new CustomEvent("lmcp-ws-message", { detail }));
  window.dispatchEvent(
    new CustomEvent("lmcp-live-refresh", {
      detail: {
        triggeredAt: new Date().toISOString(),
        source: "websocket",
        payload: detail,
      },
    })
  );
}

function connectWithPath(index = 0) {
  const path = DEFAULT_PATHS[index];
  const url = `${WS_BASE}${path}`;

  dispatchStatus({
    state: "connecting",
    url,
    path,
    connectedAt: null,
    message: `Connecting to ${path}`,
  });

  try {
    socket = new WebSocket(url);
  } catch (error) {
    attemptReconnect(`WebSocket construction failed for ${path}: ${error.message}`);
    return;
  }

  socket.onopen = () => {
    dispatchStatus({
      state: "open",
      url,
      path,
      connectedAt: new Date().toISOString(),
      message: `Connected to ${path}`,
    });
  };

  socket.onmessage = (event) => {
    let parsed;
    try {
      parsed = JSON.parse(event.data);
    } catch {
      parsed = { raw: event.data };
    }

    dispatchMessage({
      receivedAt: new Date().toISOString(),
      url,
      path,
      payload: parsed,
    });
  };

  socket.onerror = () => {
    dispatchStatus({
      state: "error",
      url,
      path,
      connectedAt: null,
      message: `Socket error on ${path}`,
    });
  };

  socket.onclose = () => {
    if (manualClose) {
      dispatchStatus({
        state: "closed",
        url,
        path,
        connectedAt: null,
        message: `Closed ${path}`,
      });
      return;
    }

    const nextIndex = index + 1 < DEFAULT_PATHS.length ? index + 1 : 0;
    attemptReconnect(`Socket closed on ${path}`, nextIndex);
  };
}

function attemptReconnect(message, nextIndex = 0) {
  dispatchStatus({
    state: "reconnecting",
    url: null,
    path: DEFAULT_PATHS[nextIndex],
    connectedAt: null,
    message,
  });

  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    connectWithPath(nextIndex);
  }, 3000);
}

export function startWebSocketFeed() {
  manualClose = false;
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  connectWithPath(0);
}

export function stopWebSocketFeed() {
  manualClose = true;
  clearTimeout(reconnectTimer);
  if (socket) {
    try {
      socket.close();
    } catch {
      // ignore close errors
    }
    socket = null;
  }
}

export function sendWebSocketMessage(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  try {
    socket.send(JSON.stringify(payload));
    return true;
  } catch {
    return false;
  }
}

export { WS_BASE, DEFAULT_PATHS };

