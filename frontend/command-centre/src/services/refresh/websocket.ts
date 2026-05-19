export function createWebSocketRefreshTransport({ url, onMessage, onOpen, onClose, onError }) {
  let socket = null;

  const connect = () => {
    if (!url || typeof WebSocket === "undefined") {
      return null;
    }
    socket = new WebSocket(url);
    socket.onopen = (event) => onOpen?.(event);
    socket.onmessage = (event) => onMessage?.(event);
    socket.onclose = (event) => onClose?.(event);
    socket.onerror = (event) => onError?.(event);
    return socket;
  };

  const disconnect = () => {
    if (socket) {
      socket.close();
      socket = null;
    }
  };

  const send = (payload) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    }
  };

  return {
    connect,
    disconnect,
    send,
    get socket() {
      return socket;
    },
  };
}
