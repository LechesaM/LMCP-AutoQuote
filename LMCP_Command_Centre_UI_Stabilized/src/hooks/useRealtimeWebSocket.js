import { useEffect, useMemo, useRef, useState } from "react";
import { createRealtimeWebSocket, DEFAULT_WS_PATH, WS_BASE } from "../services/realtimeWebSocket";

export default function useRealtimeWebSocket(options = {}) {
  const wsRef = useRef(null);
  const [state, setState] = useState({
    connected: false,
    reconnecting: false,
    url: `${WS_BASE}${options.path || DEFAULT_WS_PATH}`,
    lastMessageAt: null,
    lastType: null,
    messageCount: 0,
    errorCount: 0,
    closeCount: 0,
  });

  const client = useMemo(() => {
    return createRealtimeWebSocket(options);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.path, options.url]);

  useEffect(() => {
    wsRef.current = client;

    function onOpen(event) {
      setState((prev) => ({
        ...prev,
        connected: true,
        reconnecting: false,
        url: event.detail?.url || prev.url,
      }));
    }

    function onClose(event) {
      setState((prev) => ({
        ...prev,
        connected: false,
        closeCount: prev.closeCount + 1,
        url: event.detail?.url || prev.url,
      }));
    }

    function onError(event) {
      setState((prev) => ({
        ...prev,
        connected: false,
        errorCount: prev.errorCount + 1,
        url: event.detail?.url || prev.url,
      }));
    }

    function onReconnect(event) {
      setState((prev) => ({
        ...prev,
        reconnecting: true,
        url: event.detail?.url || prev.url,
      }));
    }

    function onMessage(event) {
      setState((prev) => ({
        ...prev,
        lastMessageAt: event.detail?.receivedAt || new Date().toISOString(),
        lastType: event.detail?.type || "unknown",
        messageCount: prev.messageCount + 1,
        url: event.detail?.url || prev.url,
      }));
    }

    window.addEventListener("lmcp-ws-open", onOpen);
    window.addEventListener("lmcp-ws-close", onClose);
    window.addEventListener("lmcp-ws-error", onError);
    window.addEventListener("lmcp-ws-reconnecting", onReconnect);
    window.addEventListener("lmcp-ws-message", onMessage);

    client.connect();

    return () => {
      client.disconnect();
      window.removeEventListener("lmcp-ws-open", onOpen);
      window.removeEventListener("lmcp-ws-close", onClose);
      window.removeEventListener("lmcp-ws-error", onError);
      window.removeEventListener("lmcp-ws-reconnecting", onReconnect);
      window.removeEventListener("lmcp-ws-message", onMessage);
    };
  }, [client]);

  return {
    ...state,
    send: (payload) => wsRef.current?.send(payload) || false,
    reconnect: () => wsRef.current?.connect(),
    disconnect: () => wsRef.current?.disconnect(),
  };
}
