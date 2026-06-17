import { useEffect, useMemo, useState } from "react";
import { API_BASE, createAuditEvent, getAuditSummary, getAuditTrail } from "../services/auditTrailApi";

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

function SeverityBadge({ severity }) {
  const normalized = String(severity || "info").toLowerCase();

  const palette =
    normalized === "critical"
      ? "bg-rose-500/20 text-rose-200 border-rose-500/30"
      : normalized === "warning"
      ? "bg-amber-500/20 text-amber-200 border-amber-500/30"
      : normalized === "success"
      ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
      : "bg-cyan-500/20 text-cyan-200 border-cyan-500/30";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold uppercase ${palette}`}>
      {severity || "info"}
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

export default function AuditTrailPanel() {
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  async function load() {
    setLoading(true);
    setError("");

    try {
      const [eventsData, summaryData] = await Promise.all([
        getAuditTrail(80),
        getAuditSummary(),
      ]);

      setEvents(eventsData?.items || []);
      setSummary(summaryData || {});
      setLastRefreshAt(new Date().toISOString());
    } catch (err) {
      setError(err.message || "Could not load audit trail.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    function handleLiveRefresh() {
      load();
    }

    window.addEventListener("lmcp-live-refresh", handleLiveRefresh);
    return () => window.removeEventListener("lmcp-live-refresh", handleLiveRefresh);
  }, []);

  useEffect(() => {
    function handleWsMessage(event) {
      const detail = event.detail || {};
      const payload = detail.payload || {};
      const type = payload?.type || payload?.payload?.type;

      if (!type) return;

      const auditEvent = {
        id: `live-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        event_type: String(type),
        source: payload?.source || "websocket",
        severity: "info",
        title: `Live event: ${type}`,
        message: "Received through websocket feed.",
        created_at: detail.receivedAt || new Date().toISOString(),
        payload: payload?.payload || payload,
      };

      setEvents((prev) => [auditEvent, ...prev].slice(0, 80));
    }

    window.addEventListener("lmcp-ws-message", handleWsMessage);
    return () => window.removeEventListener("lmcp-ws-message", handleWsMessage);
  }, []);

  async function handleCreateTestEvent() {
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const result = await createAuditEvent({
        event_type: "operator_test_audit",
        source: "dashboard",
        severity: "success",
        title: "Operator test audit event",
        message: "Audit trail manual test event created from dashboard.",
      });

      setMessage(result?.message || "Audit event created.");
      await load();
    } catch (err) {
      setError(err.message || "Could not create audit event.");
    } finally {
      setBusy(false);
    }
  }

  const stats = useMemo(() => {
    const s = summary?.summary || {};
    return {
      total: s.total_events || 0,
      critical: s.critical || 0,
      warning: s.warning || 0,
      success: s.success || 0,
      info: s.info || 0,
    };
  }, [summary]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-sky-300">
            Step 20
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Audit Trail / Activity Log</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Unified accountability layer for operator actions, decisions, alerts, quote events, submissions, portal health, and system control activity.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="rounded-full border border-sky-500/20 bg-sky-500/10 px-4 py-2 text-xs text-sky-200">
            Last Refresh: {formatDate(lastRefreshAt)}
          </div>

          <button
            onClick={load}
            disabled={loading}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10 disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh Audit"}
          </button>

          <button
            onClick={handleCreateTestEvent}
            disabled={busy}
            className="rounded-2xl bg-sky-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-90 disabled:opacity-60"
          >
            {busy ? "Creating..." : "Create Test Event"}
          </button>
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-500">
        Backend base URL: <span className="text-slate-300">{API_BASE}</span>
      </div>

      {message ? (
        <div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          {message}
        </div>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total Events" value={stats.total} hint="Persisted audit records" />
        <StatCard label="Critical" value={stats.critical} hint="Urgent events" />
        <StatCard label="Warnings" value={stats.warning} hint="Needs attention" />
        <StatCard label="Success" value={stats.success} hint="Completed events" />
        <StatCard label="Info" value={stats.info} hint="Informational events" />
      </div>

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Recent Activity</h3>
          <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Latest 80</span>
        </div>

        <div className="mt-4 space-y-3 max-h-[760px] overflow-y-auto pr-2">
          {events.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-400">
              No audit events recorded yet.
            </div>
          ) : (
            events.map((item, index) => (
              <article key={`${item.id || item.created_at || "audit"}-${index}`} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <SeverityBadge severity={item.severity || "info"} />
                  <span className="text-xs text-slate-400">{formatDate(item.created_at)}</span>
                  <span className="text-xs text-slate-500">{item.source || "unknown-source"}</span>
                </div>

                <h4 className="mt-3 text-base font-semibold text-white">
                  {item.title || item.event_type || "Audit event"}
                </h4>

                <p className="mt-2 text-sm text-slate-300">
                  {item.message || "No message provided."}
                </p>

                <div className="mt-3 grid gap-2 text-sm text-slate-400 md:grid-cols-3">
                  <div>Event: {item.event_type || "—"}</div>
                  <div>RFQ: {item.buyer_rfq_number || "—"}</div>
                  <div>Quote: {item.quote_number || "—"}</div>
                </div>
              </article>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
