import { useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  getAutonomousStatus,
  getDashboardSummary,
  getSubmissionProfit,
  getSystemHealth,
} from "../services/missionControlApi";

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-400">{hint}</div> : null}
    </div>
  );
}

function formatMoney(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 2,
  }).format(Number.isFinite(number) ? number : 0);
}

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
  });
}

function StatusPill({ enabled, healthStatus }) {
  const active = Boolean(enabled);
  const palette = active
    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
    : "bg-rose-500/15 text-rose-300 border-rose-500/20";

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${palette}`}>
      <span>{active ? "SYSTEM ON" : "SYSTEM OFF"}</span>
      <span className="opacity-70">•</span>
      <span>{String(healthStatus || "unknown").toUpperCase()}</span>
    </div>
  );
}

export default function MissionControlHeader() {
  const [summary, setSummary] = useState({});
  const [health, setHealth] = useState({});
  const [autonomous, setAutonomous] = useState({});
  const [profit, setProfit] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  async function load() {
    setLoading(true);
    setError("");

    try {
      const results = await Promise.allSettled([
        getDashboardSummary(),
        getSystemHealth(),
        getAutonomousStatus(),
        getSubmissionProfit(),
      ]);

      const [summaryRes, healthRes, autonomousRes, profitRes] = results;

      setSummary(summaryRes.status === "fulfilled" ? (summaryRes.value || {}) : {});
      setHealth(healthRes.status === "fulfilled" ? (healthRes.value || {}) : {});
      setAutonomous(autonomousRes.status === "fulfilled" ? (autonomousRes.value || {}) : {});
      setProfit(profitRes.status === "fulfilled" ? (profitRes.value || {}) : {});
      setLastRefreshAt(new Date().toISOString());

      const failedCount = results.filter((r) => r.status !== "fulfilled").length;
      if (failedCount === results.length) {
        setError("Could not load mission control header data from the backend.");
      } else if (failedCount > 0) {
        setError("Some mission control data could not be loaded, but the dashboard is partially available.");
      }
    } catch (err) {
      setError(err.message || "Failed to load mission control header.");
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

  const ui = useMemo(() => {
    const summaryBlock = summary?.summary || summary || {};
    const submissionHistory = summary?.submission_history || {};
    const portalRadar = health?.portal_radar || {};
    const systemStatus = health?.status || autonomous?.last_status || "unknown";

    return {
      enabled: Boolean(autonomous?.enabled),
      systemStatus,
      totalRfqFolders: summaryBlock?.rfq_folders ?? summary?.total_opportunities ?? summary?.opportunities ?? 0,
      submitted: submissionHistory?.submitted ?? summary?.submitted ?? 0,
      failed: submissionHistory?.failed ?? summary?.failed ?? 0,
      queued: submissionHistory?.queued ?? summary?.pending ?? 0,
      revenue: profit?.total_revenue ?? profit?.revenue ?? 0,
      profit: profit?.total_profit ?? profit?.profit ?? 0,
      healthyPortals: portalRadar?.healthy ?? 0,
      blockedPortals: portalRadar?.blocked ?? 0,
      updatedAt: autonomous?.updated_at || health?.checked_at || summary?.timestamp || null,
      lastMessage: autonomous?.last_message || health?.message || "Mission Control active.",
    };
  }, [summary, health, autonomous, profit]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-cyan-300">
            LMCP Mission Control
          </div>
          <h1 className="mt-2 text-3xl font-semibold">Tender Operations Dashboard</h1>
          <p className="mt-2 max-w-4xl text-sm text-slate-400">
            Global mission-control header with live system summary, financial visibility, and operational status from your LMCP backend.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <StatusPill enabled={ui.enabled} healthStatus={ui.systemStatus} />
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-300">
              Updated: {formatDate(ui.updatedAt)}
            </div>
            <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-200">
              Live refreshed: {formatDate(lastRefreshAt)}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            onClick={load}
            disabled={loading}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh Header"}
          </button>
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-500">
        Backend base URL: <span className="text-slate-300">{API_BASE}</span>
      </div>

      {error ? (
        <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl border border-cyan-500/10 bg-cyan-500/5 px-4 py-3 text-sm text-cyan-100">
        {ui.lastMessage}
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="RFQ Folders" value={ui.totalRfqFolders} hint="Overall harvested opportunity volume" />
        <StatCard label="Submitted" value={ui.submitted} hint="Submission history count" />
        <StatCard label="Failed" value={ui.failed} hint="Submission failures" />
        <StatCard label="Queued" value={ui.queued} hint="Pending submission queue" />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Revenue" value={formatMoney(ui.revenue)} hint="Submission analytics revenue" />
        <StatCard label="Profit" value={formatMoney(ui.profit)} hint="Submission analytics profit" />
        <StatCard label="Healthy Portals" value={ui.healthyPortals} hint="Portal radar healthy count" />
        <StatCard label="Blocked Portals" value={ui.blockedPortals} hint="Portal radar blocked count" />
      </div>
    </section>
  );
}

