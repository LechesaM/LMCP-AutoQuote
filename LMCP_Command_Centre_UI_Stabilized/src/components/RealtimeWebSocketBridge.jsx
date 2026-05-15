import React, { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, Radio, RefreshCw, Wifi, WifiOff } from "lucide-react";
import useRealtimeWebSocket from "../hooks/useRealtimeWebSocket";

function formatTime(value) {
  if (!value) return "—";
  try {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return "—";
    return dt.toLocaleString("en-ZA", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "—";
  }
}

export default function RealtimeWebSocketBridge({ maxEvents = 20 }) {
  const ws = useRealtimeWebSocket({ path: "/ws/dashboard" });
  const [events, setEvents] = useState([]);

  useEffect(() => {
    function onMessage(event) {
      const detail = event.detail || {};
      const item = {
        id: `${detail.type || "unknown"}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: detail.type || "unknown",
        receivedAt: detail.receivedAt || new Date().toISOString(),
        payload: detail.payload || {},
      };

      setEvents((prev) => [item, ...prev].slice(0, maxEvents));
    }

    window.addEventListener("lmcp-ws-message", onMessage);

    return () => window.removeEventListener("lmcp-ws-message", onMessage);
  }, [maxEvents]);

  const statusTone = useMemo(() => {
    if (ws.connected) return "emerald";
    if (ws.reconnecting) return "amber";
    return "rose";
  }, [ws.connected, ws.reconnecting]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-cyan-300">
            Step 9
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Real-Time WebSocket Intelligence Layer</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Streams live backend events into the dashboard, then triggers lmcp-refresh so API panels stay synchronized.
          </p>
        </div>

        <div
          className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold ${
            statusTone === "emerald"
              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
              : statusTone === "amber"
              ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
              : "border-rose-500/20 bg-rose-500/10 text-rose-300"
          }`}
        >
          {ws.connected ? <Wifi size={15} /> : ws.reconnecting ? <RefreshCw size={15} /> : <WifiOff size={15} />}
          {ws.connected ? "CONNECTED" : ws.reconnecting ? "RECONNECTING" : "DISCONNECTED"}
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-5">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">URL</div>
          <div className="mt-2 break-all text-xs text-white">{ws.url}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Messages</div>
          <div className="mt-2 text-2xl font-semibold">{ws.messageCount}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Last Type</div>
          <div className="mt-2 break-all text-sm font-semibold">{ws.lastType || "—"}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Last Message</div>
          <div className="mt-2 text-sm font-semibold">{formatTime(ws.lastMessageAt)}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="text-xs uppercase text-slate-400">Errors</div>
          <div className="mt-2 text-2xl font-semibold">{ws.errorCount}</div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          onClick={ws.reconnect}
          className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
        >
          <Radio size={16} />
          Reconnect
        </button>

        <button
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent("lmcp-refresh", {
                detail: { source: "manual-step9", at: new Date().toISOString() },
              })
            )
          }
          className="inline-flex items-center gap-2 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/20"
        >
          <Activity size={16} />
          Broadcast Refresh
        </button>
      </div>

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5">
        <h3 className="text-lg font-semibold text-white">Live Event Feed</h3>

        {events.length === 0 ? (
          <div className="mt-4 flex items-center gap-2 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            <AlertTriangle size={16} />
            No WebSocket events received yet.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {events.map((item) => (
              <article key={item.id} className="rounded-2xl border border-white/10 bg-slate-950 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-200">
                    {item.type}
                  </div>
                  <div className="text-xs text-slate-400">{formatTime(item.receivedAt)}</div>
                </div>
                <pre className="mt-3 max-h-48 overflow-auto text-xs text-slate-300">
                  {JSON.stringify(item.payload, null, 2)}
                </pre>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
