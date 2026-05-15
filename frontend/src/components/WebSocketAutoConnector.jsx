import { useEffect } from "react";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000";

export default function WebSocketAutoConnector() {
  useEffect(() => {
    let socket;
    let timer;
    let closed = false;

    function connect() {
      if (closed) return;

      try {
        socket = new WebSocket(`${WS_BASE.replace(/\/$/, "")}/ws/dashboard`);

        socket.onopen = () => {
          window.dispatchEvent(new CustomEvent("lmcp-ws-open", {
            detail: { url: socket.url, connectedAt: new Date().toISOString() }
          }));
        };

        socket.onmessage = (event) => {
          let payload;
          try {
            payload = JSON.parse(event.data);
          } catch {
            payload = { raw: event.data };
          }

          window.dispatchEvent(new CustomEvent("lmcp-ws-message", {
            detail: {
              url: socket.url,
              payload,
              type: payload.type || "unknown",
              receivedAt: new Date().toISOString()
            }
          }));
        };

        socket.onclose = () => {
          if (!closed) timer = setTimeout(connect, 3000);
        };

        socket.onerror = () => {
          window.dispatchEvent(new CustomEvent("lmcp-ws-error", {
            detail: { at: new Date().toISOString() }
          }));
        };
      } catch {
        timer = setTimeout(connect, 3000);
      }
    }

    connect();

    return () => {
      closed = true;
      clearTimeout(timer);
      try {
        socket?.close();
      } catch {}
    };
  }, []);

  return null;
}
