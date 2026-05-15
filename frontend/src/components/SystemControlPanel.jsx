import { useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  disableAutonomousSystem,
  enableAutonomousSystem,
  getAutonomousStatus,
  runAutonomousCycleNow,
} from "../services/systemControlApi";

function MetricCard({ label, value, hint }) {
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
    second: "2-digit",
  });
}

function StatusPill({ enabled, status }) {
  const label = enabled ? "SYSTEM ON" : "SYSTEM OFF";
  const palette = enabled
    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
    : "bg-rose-500/15 text-rose-300 border-rose-500/20";

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${palette}`}>
      <span>{label}</span>
      <span className="opacity-70">•</span>
      <span>{String(status || "unknown").toUpperCase()}</span>
    </div>
  );
}

export default function SystemControlPanel() {
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  async function loadStatus() {
    setLoading(true);
    setError("");

    try {
      const result = await getAutonomousStatus();
      setStatusData({
        ...(result?.data || {}),
        _resolved_path: result?.path || "",
      });
      setLastRefreshAt(new Date().toISOString());
    } catch (err) {
      setError(err.message || "Failed to load autonomous system status.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    function handleLiveRefresh() {
      loadStatus();
    }
    window.addEventListener("lmcp-live-refresh", handleLiveRefresh);
    return () => window.removeEventListener("lmcp-live-refresh", handleLiveRefresh);
  }, []);

  async function handleEnable() {
    setBusyAction("enable");
    setError("");
    setMessage("");

    try {
      const result = await enableAutonomousSystem();
      setMessage(`Autonomous system enabled using ${result.path}.`);
      await loadStatus();
    } catch (err) {
      setError(err.message || "Failed to enable autonomous system.");
    } finally {
      setBusyAction("");
    }
  }

  async function handleDisable() {
    setBusyAction("disable");
    setError("");
    setMessage("");

    try {
      const result = await disableAutonomousSystem();
      setMessage(`Autonomous system disabled using ${result.path}.`);
      await loadStatus();
    } catch (err) {
      setError(err.message || "Failed to disable autonomous system.");
    } finally {
      setBusyAction("");
    }
  }

  async function handleRunNow() {
    setBusyAction("run");
    setError("");
    setMessage("");

    try {
      const result = await runAutonomousCycleNow();
      setMessage(`Autonomous cycle started using ${result.path}.`);
      await loadStatus();
    } catch (err) {
      setError(err.message || "Failed to run autonomous cycle.");
    } finally {
      setBusyAction("");
    }
  }

  const ui = useMemo(() => {
    const enabled = Boolean(statusData?.enabled);
    const lastResult = statusData?.last_result || {};
    return {
      enabled,
      status: statusData?.last_status || statusData?.status || "unknown",
      message: statusData?.last_message || statusData?.message || "No recent message.",
      updatedAt: statusData?.updated_at || statusData?.checked_at || null,
      lastRunAt: statusData?.last_run_at || null,
      totalItems:
        lastResult?.total_processed ??
        lastResult?.items_processed ??
        lastResult?.total ??
        0,
      successfulItems:
        lastResult?.submitted ??
        lastResult?.successful ??
        lastResult?.success_count ??
        0,
    };
  }, [statusData]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-amber-300">
            Step 7
          </div>
          <h2 className="mt-2 text-2xl font-semibold">ON/OFF System Control</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Control the autonomous LMCP engine directly from the dashboard, monitor live system status, and trigger an immediate run when needed.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <StatusPill enabled={ui.enabled} status={ui.status} />
            <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-200">
              Live refreshed: {formatDate(lastRefreshAt)}
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <button
            onClick={handleEnable}
            disabled={busyAction !== ""}
            className="rounded-2xl bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "enable" ? "Turning ON..." : "Turn System ON"}
          </button>

          <button
            onClick={handleDisable}
            disabled={busyAction !== ""}
            className="rounded-2xl bg-rose-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "disable" ? "Turning OFF..." : "Turn System OFF"}
          </button>

          <button
            onClick={handleRunNow}
            disabled={busyAction !== ""}
            className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "run" ? "Running..." : "Run One Cycle"}
          </button>

          <button
            onClick={loadStatus}
            disabled={loading || busyAction !== ""}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh Status"}
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
        <MetricCard label="Enabled" value={ui.enabled ? "YES" : "NO"} hint="Autonomous engine flag" />
        <MetricCard label="Last Status" value={String(ui.status).toUpperCase()} hint="Latest engine state" />
        <MetricCard label="Last Run" value={formatDate(ui.lastRunAt)} hint="Most recent autonomous run" />
        <MetricCard label="Updated" value={formatDate(ui.updatedAt)} hint="Latest status refresh" />
        <MetricCard label="Processed" value={ui.totalItems} hint="Last result item count" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-lg font-semibold">System Summary</h3>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="text-sm font-medium text-white">Last Message</div>
              <p className="mt-2 text-sm text-slate-300">{ui.message}</p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="text-sm font-medium text-white">Last Successful Items</div>
              <p className="mt-2 text-2xl font-semibold text-white">{ui.successfulItems}</p>
              <p className="mt-1 text-sm text-slate-400">Derived from last_result when available.</p>
            </div>
          </div>

          <div className="mt-4">
            <div className="mb-2 text-sm font-medium text-slate-300">Raw /autonomous/status</div>
            <pre className="max-h-80 overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-300">
              {JSON.stringify(statusData || {}, null, 2)}
            </pre>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-lg font-semibold">Control Notes</h3>

          <div className="mt-4 space-y-4 text-sm text-slate-300">
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Turn System ON</div>
              <p className="mt-1 text-slate-400">
                Tries common enable endpoints such as <code className="text-emerald-300">/autonomous/enable</code> and <code className="text-emerald-300">/autonomous/start</code>.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Turn System OFF</div>
              <p className="mt-1 text-slate-400">
                Tries common disable endpoints such as <code className="text-rose-300">/autonomous/disable</code> and <code className="text-rose-300">/autonomous/stop</code>.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Run One Cycle</div>
              <p className="mt-1 text-slate-400">
                Calls <code className="text-cyan-300">/autonomous/run-once</code> when available so you can trigger an immediate engine run.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Status endpoint used</div>
              <p className="mt-1 break-all text-slate-400">
                {statusData?._resolved_path || "/autonomous/status"}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

