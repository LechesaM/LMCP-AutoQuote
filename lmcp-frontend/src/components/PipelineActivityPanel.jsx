import { useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function readJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
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

export default function PipelineActivityPanel() {
  const [summary, setSummary] = useState({});
  const [health, setHealth] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  async function load() {
    setLoading(true);
    setError("");

    try {
      const [summaryData, healthData] = await Promise.allSettled([
        readJson("/dashboard/summary"),
        readJson("/system/health"),
      ]);

      const summaryValue = summaryData.status === "fulfilled" ? summaryData.value : {};
      const healthValue = healthData.status === "fulfilled" ? healthData.value : {};

      setSummary(summaryValue || {});
      setHealth(healthValue || {});
      setLastRefreshAt(new Date().toISOString());

      if (summaryData.status !== "fulfilled" && healthData.status !== "fulfilled") {
        setError("Could not load pipeline activity data from the backend.");
      }
    } catch (err) {
      setError(err.message || "Could not load pipeline activity data.");
    } finally {
      setLoading(false);
    }
  }

  // ✅ Initial load
  useEffect(() => {
    load();
  }, []);

  // 🔥 STEP 8.1 FIX — LISTEN TO CORRECT EVENT
  useEffect(() => {
    const handler = () => {
      load();
    };

    window.addEventListener("lmcp-refresh", handler);

    return () => window.removeEventListener("lmcp-refresh", handler);
  }, []);

  const stats = useMemo(() => {
    return {
      total: summary?.total_opportunities ?? summary?.opportunities ?? 0,
      quoteReady: summary?.quote_ready ?? summary?.quote_ready_total ?? 0,
      submitted: summary?.submitted ?? summary?.submitted_total ?? 0,
      status: health?.status || "unknown",
    };
  }, [summary, health]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-5 shadow-2xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-fuchsia-300">
            Pipeline
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-white">Pipeline Activity</h2>
          <p className="mt-2 text-sm text-slate-400">
            Overview of backend system health and tender pipeline counts.
          </p>
        </div>

        <button
          onClick={load}
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
        >
          Refresh
        </button>
      </div>

      <div className="mt-3 text-xs text-slate-500">
        Last refreshed: <span className="text-slate-300">{formatDate(lastRefreshAt)}</span>
      </div>

      {error && (
        <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Opportunities" value={stats.total} />
        <StatCard label="Quote Ready" value={stats.quoteReady} />
        <StatCard label="Submitted" value={stats.submitted} />
        <StatCard label="System Status" value={String(stats.status).toUpperCase()} />
      </div>

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5">
        <h3 className="text-lg font-semibold text-white">Raw Backend Snapshot</h3>

        {loading && (
          <div className="mt-4 text-sm text-slate-400">Loading pipeline data...</div>
        )}

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div>
            <div className="mb-2 text-sm font-medium text-slate-300">/dashboard/summary</div>
            <pre className="max-h-72 overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-300">
              {JSON.stringify(summary, null, 2)}
            </pre>
          </div>

          <div>
            <div className="mb-2 text-sm font-medium text-slate-300">/system/health</div>
            <pre className="max-h-72 overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-300">
              {JSON.stringify(health, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
