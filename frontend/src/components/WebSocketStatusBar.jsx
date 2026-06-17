import { useEffect, useMemo, useState } from "react";
import { DEFAULT_PATHS, WS_BASE, startWebSocketFeed, stopWebSocketFeed } from "../services/websocketFeed";

function formatTime(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function WebSocketStatusBar() {
  const [status, setStatus] = useState({
    state: "idle",
    url: null,
    path: DEFAULT_PATHS[0],
    connectedAt: null,
    message: "Waiting to connect.",
  });
  const [lastMessageAt, setLastMessageAt] = useState(null);
  const [messageCount, setMessageCount] = useState(0);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    function handleStatus(event) {
      setStatus(event.detail || {});
    }

    function handleMessage(event) {
      setLastMessageAt(event.detail?.receivedAt || new Date().toISOString());
      setMessageCount((prev) => prev + 1);
    }

    window.addEventListener("lmcp-ws-status", handleStatus);
    window.addEventListener("lmcp-ws-message", handleMessage);

    startWebSocketFeed();

    return () => {
      window.removeEventListener("lmcp-ws-status", handleStatus);
      window.removeEventListener("lmcp-ws-message", handleMessage);
      stopWebSocketFeed();
    };
  }, []);

  const pillClass = useMemo(() => {
    switch (status.state) {
      case "open":
        return "border-emerald-500/20 bg-emerald-500/15 text-emerald-300";
      case "connecting":
      case "reconnecting":
        return "border-cyan-500/20 bg-cyan-500/15 text-cyan-300";
      case "error":
        return "border-rose-500/20 bg-rose-500/15 text-rose-300";
      default:
        return "border-slate-500/20 bg-slate-500/15 text-slate-300";
    }
  }, [status.state]);

  function toggleFeed() {
    if (enabled) {
      stopWebSocketFeed();
      setEnabled(false);
    } else {
      startWebSocketFeed();
      setEnabled(true);
    }
  }

  return (
    <section className="rounded-[24px] border border-emerald-500/20 bg-emerald-500/5 px-5 py-4 shadow-lg">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4">
          <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${pillClass}`}>
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                status.state === "open" ? "animate-pulse bg-emerald-300" : "bg-current"
              }`}
            />
            <span>WEBSOCKET {String(status.state || "idle").toUpperCase()}</span>
          </div>

          <div className="text-sm text-slate-300">
            Last message: <span className="text-white">{formatTime(lastMessageAt)}</span>
          </div>

          <div className="text-sm text-slate-300">
            Messages: <span className="text-white">{messageCount}</span>
          </div>

          <div className="text-sm text-slate-300">
            Path: <span className="text-white">{status.path || DEFAULT_PATHS[0]}</span>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            onClick={toggleFeed}
            className={`rounded-2xl px-5 py-3 text-sm font-semibold transition ${
              enabled
                ? "bg-rose-400 text-slate-950 hover:opacity-90"
                : "bg-emerald-400 text-slate-950 hover:opacity-90"
            }`}
          >
            {enabled ? "Disconnect Feed" : "Reconnect Feed"}
          </button>
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-400">
        WS base URL: <span className="text-slate-200">{WS_BASE}</span>
      </div>

      <div className="mt-2 text-xs text-slate-400">
        Status message: <span className="text-slate-200">{status.message || "—"}</span>
      </div>

      <div className="mt-2 text-xs text-slate-500">
        Fallback paths: <span className="text-slate-300">{DEFAULT_PATHS.join(", ")}</span>
      </div>
    </section>
  );
}

