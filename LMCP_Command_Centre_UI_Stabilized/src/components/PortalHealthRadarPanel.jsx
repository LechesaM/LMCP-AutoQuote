import { useEffect, useMemo, useState } from "react";

function formatDate(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString("en-ZA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function HealthBadge({ status }) {
  const normalized = String(status || "unknown").toLowerCase();

  const palette =
    normalized === "healthy"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
      : normalized === "slow"
      ? "bg-amber-500/15 text-amber-300 border-amber-500/20"
      : normalized === "blocked"
      ? "bg-orange-500/15 text-orange-300 border-orange-500/20"
      : normalized === "broken" || normalized === "failed"
      ? "bg-rose-500/15 text-rose-300 border-rose-500/20"
      : normalized === "recovering"
      ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/20"
      : "bg-slate-500/15 text-slate-300 border-slate-500/20";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${palette}`}>
      {status || "unknown"}
    </span>
  );
}

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-400">{hint}</div> : null}
    </div>
  );
}

export default function PortalHealthRadarPanel() {
  const [events, setEvents] = useState([]);
  const [lastEventAt, setLastEventAt] = useState(null);

  useEffect(() => {
    function handleMessage(event) {
      const detail = event.detail || {};
      const payload = detail.payload || {};

      const resolvedType =
        payload?.type ||
        payload?.payload?.type ||
        detail?.payload?.type;

      const resolvedPayload =
        payload?.payload ||
        payload ||
        {};

      const allowed = new Set([
        "portal_health_update",
        "portal_blocked",
        "portal_broken",
        "portal_slow",
        "portal_recovered",
        "portal_isolated",
        "portal_retry_scheduled",
      ]);

      if (!allowed.has(resolvedType)) return;

      const item = {
        id:
          resolvedType +
          "-" +
          Date.now() +
          "-" +
          Math.random().toString(36).slice(2, 8),
        type: resolvedType,
        receivedAt: detail.receivedAt || new Date().toISOString(),
        source: payload?.source || "portal-radar",
        data: resolvedPayload,
      };

      setEvents((prev) => [item, ...prev].slice(0, 30));
      setLastEventAt(item.receivedAt);
    }

    window.addEventListener("lmcp-ws-message", handleMessage);
    return () => window.removeEventListener("lmcp-ws-message", handleMessage);
  }, []);

  const stats = useMemo(() => {
    const latestByPortal = new Map();

    for (const event of events) {
      const key =
        event.data?.source_name ||
        event.data?.portal_name ||
        event.data?.url ||
        event.id;

      if (!latestByPortal.has(key)) {
        latestByPortal.set(key, event);
      }
    }

    const latest = Array.from(latestByPortal.values());

    return {
      totalEvents: events.length,
      trackedPortals: latest.length,
      healthy: latest.filter((e) => String(e.data?.status || "").toLowerCase() === "healthy").length,
      slow: latest.filter((e) => String(e.data?.status || "").toLowerCase() === "slow").length,
      blocked: latest.filter((e) => String(e.data?.status || "").toLowerCase() === "blocked").length,
      broken: latest.filter((e) => {
        const status = String(e.data?.status || "").toLowerCase();
        return status === "broken" || status === "failed";
      }).length,
    };
  }, [events]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-orange-300">
            Step 16
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Portal Health Radar</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Tracks live portal health, blocked sources, slow scrapers, recovery events, and isolated portals from the websocket feed.
          </p>
        </div>

        <div className="rounded-full border border-orange-500/20 bg-orange-500/10 px-4 py-2 text-xs text-orange-200">
          Last Event: {formatDate(lastEventAt)}
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard label="Events" value={stats.totalEvents} hint="Recent radar events" />
        <StatCard label="Portals" value={stats.trackedPortals} hint="Tracked recent sources" />
        <StatCard label="Healthy" value={stats.healthy} hint="Latest known healthy" />
        <StatCard label="Slow" value={stats.slow} hint="Performance degraded" />
        <StatCard label="Blocked" value={stats.blocked} hint="Access blocked" />
        <StatCard label="Broken" value={stats.broken} hint="Parser/fetch failure" />
      </div>

      <div className="mt-6 space-y-3 max-h-[650px] overflow-y-auto pr-2">
        {events.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
            No portal health websocket events received yet.
          </div>
        ) : (
          events.map((item) => (
            <article key={item.id} className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <HealthBadge status={item.data?.status || item.type} />
                    <span className="text-xs text-slate-400">{formatDate(item.receivedAt)}</span>
                  </div>

                  <h3 className="mt-3 text-base font-semibold text-white">
                    {item.data?.source_name || item.data?.portal_name || "Unknown Portal"}
                  </h3>

                  <div className="mt-2 text-sm text-slate-300">
                    URL: {item.data?.url || "—"}
                  </div>

                  <div className="mt-1 text-sm text-slate-300">
                    Event: {item.type}
                  </div>

                  <div className="mt-1 text-sm text-slate-300">
                    Response Time: {item.data?.response_time_ms ?? "—"} ms
                  </div>

                  <div className="mt-1 text-sm text-slate-300">
                    Failure Count: {item.data?.failure_count ?? "—"}
                  </div>

                  <div className="mt-1 text-sm text-slate-300">
                    Retry In: {item.data?.retry_after_seconds ?? "—"} sec
                  </div>
                </div>
              </div>

              {item.data?.message ? (
                <div className="mt-3 rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                  {item.data.message}
                </div>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
