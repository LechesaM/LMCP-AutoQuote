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

function SeverityBadge({ severity }) {
  const normalized = String(severity || "info").toLowerCase();

  const palette =
    normalized === "critical"
      ? "bg-rose-500/20 text-rose-200 border-rose-500/30"
      : normalized === "high"
      ? "bg-orange-500/20 text-orange-200 border-orange-500/30"
      : normalized === "medium"
      ? "bg-amber-500/20 text-amber-200 border-amber-500/30"
      : normalized === "success"
      ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/30"
      : "bg-cyan-500/20 text-cyan-200 border-cyan-500/30";

  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase ${palette}`}>
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

export default function AlertsNotificationPanel() {
  const [alerts, setAlerts] = useState([]);
  const [lastAlertAt, setLastAlertAt] = useState(null);

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
        "alert",
        "critical_alert",
        "high_value_tender_alert",
        "failed_submission_alert",
        "portal_blocked_alert",
        "system_stopped_alert",
        "quote_failure_alert",
        "profit_alert",
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
        data: resolvedPayload,
      };

      setAlerts((prev) => [item, ...prev].slice(0, 30));
      setLastAlertAt(item.receivedAt);
    }

    window.addEventListener("lmcp-ws-message", handleMessage);
    return () => window.removeEventListener("lmcp-ws-message", handleMessage);
  }, []);

  function clearAlerts() {
    setAlerts([]);
    setLastAlertAt(null);
  }

  const stats = useMemo(() => {
    return {
      total: alerts.length,
      critical: alerts.filter((a) => String(a.data?.severity || "").toLowerCase() === "critical").length,
      high: alerts.filter((a) => String(a.data?.severity || "").toLowerCase() === "high").length,
      failed: alerts.filter((a) => a.type === "failed_submission_alert" || a.type === "quote_failure_alert").length,
    };
  }, [alerts]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-rose-300">
            Step 17
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Alerts & Notifications</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Receives urgent system alerts, failed submissions, blocked portals, quote failures, and high-value tender notifications in real time.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="rounded-full border border-rose-500/20 bg-rose-500/10 px-4 py-2 text-xs text-rose-200">
            Last Alert: {formatDate(lastAlertAt)}
          </div>

          <button
            onClick={clearAlerts}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            Clear Alerts
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <StatCard label="Total Alerts" value={stats.total} hint="Recent live alerts" />
        <StatCard label="Critical" value={stats.critical} hint="Immediate attention" />
        <StatCard label="High" value={stats.high} hint="High priority" />
        <StatCard label="Failures" value={stats.failed} hint="Submission / quote failures" />
      </div>

      <div className="mt-6 space-y-3 max-h-[650px] overflow-y-auto pr-2">
        {alerts.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
            No live alerts received yet.
          </div>
        ) : (
          alerts.map((alert) => (
            <article key={alert.id} className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <SeverityBadge severity={alert.data?.severity || "info"} />
                    <span className="text-xs text-slate-400">{formatDate(alert.receivedAt)}</span>
                    <span className="text-xs text-slate-500">{alert.type}</span>
                  </div>

                  <h3 className="mt-3 text-base font-semibold text-white">
                    {alert.data?.title || alert.data?.message || "LMCP Alert"}
                  </h3>

                  <p className="mt-2 text-sm text-slate-300">
                    {alert.data?.message || "No additional message provided."}
                  </p>

                  <div className="mt-3 grid gap-2 text-sm text-slate-400 md:grid-cols-2">
                    <div>RFQ: {alert.data?.buyer_rfq_number || "—"}</div>
                    <div>Quote: {alert.data?.quote_number || "—"}</div>
                    <div>Source: {alert.data?.source_name || alert.data?.portal_name || "—"}</div>
                    <div>Action: {alert.data?.recommended_action || "Review dashboard"}</div>
                  </div>
                </div>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
