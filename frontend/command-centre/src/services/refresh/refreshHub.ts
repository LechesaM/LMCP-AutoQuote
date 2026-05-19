import { createPollingController } from "./polling";
import { createWebSocketRefreshTransport } from "./websocket";

export function createRefreshHub(fetcher, options = {}) {
  const polling = createPollingController(fetcher, options.intervalMs || 30000);
  const websocket = createWebSocketRefreshTransport({
    url: options.websocketUrl || "",
    onMessage: options.onMessage,
    onOpen: options.onOpen,
    onClose: options.onClose,
    onError: options.onError,
  });

  return {
    polling,
    websocket,
    start() {
      polling.start();
      if (options.enableWebSocket) {
        websocket.connect();
      }
    },
    stop() {
      polling.stop();
      websocket.disconnect();
    },
    refresh() {
      return polling.refresh();
    },
  };
}
