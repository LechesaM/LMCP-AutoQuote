import { useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  getSubmissionHistory,
  getSubmissionProfit,
  getSubmissionSummary,
  runSubmissionScheduler,
} from "../services/submissionControlApi";

function MetricCard({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-400">{hint}</div> : null}
    </div>
  );
}

function StatusBadge({ value }) {
  const normalized = String(value || "unknown").toLowerCase();

  const palette =
    normalized === "submitted"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
      : normalized === "pending"
      ? "bg-amber-500/15 text-amber-300 border-amber-500/20"
      : normalized === "failed"
      ? "bg-rose-500/15 text-rose-300 border-rose-500/20"
      : "bg-slate-500/15 text-slate-300 border-slate-500/20";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${palette}`}>
      {value || "Unknown"}
    </span>
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
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-ZA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function SubmissionControlActions() {
  const [summary, setSummary] = useState(null);
  const [profit, setProfit] = useState(null);
  const [history, setHistory] = useState([]);
  const [limit, setLimit] = useState(10);

  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [runningAction, setRunningAction] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  async function loadDashboard() {
    setLoadingDashboard(true);
    setError("");

    try {
      const [summaryData, profitData, historyData] = await Promise.all([
        getSubmissionSummary(),
        getSubmissionProfit(),
        getSubmissionHistory(20).catch(() => []),
      ]);

      setSummary(summaryData || {});
      setProfit(profitData || {});
      setHistory(Array.isArray(historyData) ? historyData : historyData?.items || []);
      setLastRefreshAt(new Date().toISOString());
    } catch (err) {
      setError(err.message || "Failed to load submission dashboard.");
    } finally {
      setLoadingDashboard(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  useEffect(() => {
    function handleLiveRefresh() {
      loadDashboard();
    }
    window.addEventListener("lmcp-live-refresh", handleLiveRefresh);
    return () => window.removeEventListener("lmcp-live-refresh", handleLiveRefresh);
  }, []);

  async function handleRunScheduler() {
    setRunningAction(true);
    setError("");
    setMessage("");

    try {
      const result = await runSubmissionScheduler(limit);
      const totalProcessed =
        result?.total_processed ??
        result?.pending_submission_stage?.processed ??
        0;

      setMessage(
        `Submission scheduler completed successfully. Processed ${totalProcessed} item(s).`
      );

      await loadDashboard();
    } catch (err) {
      setError(err.message || "Failed to run submission scheduler.");
    } finally {
      setRunningAction(false);
    }
  }

  const stats = useMemo(() => {
    return {
      submitted: summary?.submitted ?? summary?.total_submitted ?? 0,
      pending: summary?.pending ?? summary?.pending_submission ?? 0,
      failed: summary?.failed ?? summary?.submission_failed ?? 0,
      profit: profit?.total_profit ?? profit?.profit ?? 0,
      revenue: profit?.total_revenue ?? profit?.revenue ?? 0,
    };
  }, [summary, profit]);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-emerald-300">
            Step 6
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Submission Control Actions</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Trigger the submission scheduler, monitor processed items, and track live submission outcomes from your LMCP backend.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
            <span className="text-sm text-slate-300">Run limit</span>
            <input
              type="number"
              min="1"
              max="100"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value || 1))}
              className="w-24 rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none"
            />
          </label>

          <button
            onClick={handleRunScheduler}
            disabled={runningAction}
            className="rounded-2xl bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningAction ? "Running..." : "Run Submission Scheduler"}
          </button>

          <button
            onClick={loadDashboard}
            disabled={loadingDashboard}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadingDashboard ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-500">
        Backend base URL: <span className="text-slate-300">{API_BASE}</span>
      </div>

      <div className="mt-2 text-xs text-slate-500">
        Last refreshed: <span className="text-slate-300">{formatDate(lastRefreshAt)}</span>
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
        <MetricCard label="Submitted" value={stats.submitted} hint="Successful submissions" />
        <MetricCard label="Pending" value={stats.pending} hint="Queued for submission" />
        <MetricCard label="Failed" value={stats.failed} hint="Need retry / review" />
        <MetricCard label="Revenue" value={formatMoney(stats.revenue)} hint="From submission analytics" />
        <MetricCard label="Profit" value={formatMoney(stats.profit)} hint="Estimated / recorded profit" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Recent Submission History</h3>
            <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
              Latest 20
            </span>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-white/10 text-slate-400">
                <tr>
                  <th className="pb-3 pr-4 font-medium">Buyer RFQ</th>
                  <th className="pb-3 pr-4 font-medium">Quote Number</th>
                  <th className="pb-3 pr-4 font-medium">Status</th>
                  <th className="pb-3 pr-4 font-medium">Submitted At</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td className="py-6 text-slate-500" colSpan={4}>
                      {loadingDashboard ? "Loading history..." : "No submission history returned yet."}
                    </td>
                  </tr>
                ) : (
                  history.map((item, index) => (
                    <tr key={`${item?.quote_number || "submission"}-${index}`} className="border-b border-white/5">
                      <td className="py-4 pr-4 text-slate-200">
                        {item?.buyer_rfq_number || item?.rfq_number || "—"}
                      </td>
                      <td className="py-4 pr-4 text-slate-300">
                        {item?.quote_number || item?.lmcp_quote_number || "—"}
                      </td>
                      <td className="py-4 pr-4">
                        <StatusBadge value={item?.status || item?.submission_status} />
                      </td>
                      <td className="py-4 pr-4 text-slate-400">
                        {formatDate(item?.submitted_at || item?.created_at || item?.timestamp)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-lg font-semibold">Action Notes</h3>
          <div className="mt-4 space-y-4 text-sm text-slate-300">
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Run Submission Scheduler</div>
              <p className="mt-1 text-slate-400">
                Calls <code className="text-emerald-300">POST /submission-scheduler/run-now</code> and processes pending submissions using the limit you set above.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Refresh Dashboard</div>
              <p className="mt-1 text-slate-400">
                Reloads submission summary, profit data, and recent history from the API.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <div className="font-medium text-white">Expected backend endpoints</div>
              <ul className="mt-2 space-y-1 text-slate-400">
                <li>/submission-scheduler/run-now?limit=10</li>
                <li>/submission-analytics/summary</li>
                <li>/submission-analytics/profit</li>
                <li>/submission-history?limit=20</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

