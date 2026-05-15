// lmcp-frontend/src/components/LiveMissionMetricsPanel.jsx

import React, { useEffect, useMemo, useState } from "react";
import {
  detectSystemMode,
  fetchAutonomousStatus,
  fetchSubmissionHistory,
  fetchSubmissionProfit,
  fetchSubmissionSummary,
  formatRand,
} from "../services/liveMissionMetrics";

function modeStyles(mode) {
  if (mode === "FULL") {
    return {
      badge: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
      dot: "bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,0.95)]",
      label: "FULL SUBMISSION",
    };
  }

  if (mode === "SAFE") {
    return {
      badge: "bg-amber-500/15 text-amber-300 border-amber-400/30",
      dot: "bg-amber-400 shadow-[0_0_18px_rgba(251,191,36,0.95)]",
      label: "SAFE MODE",
    };
  }

  return {
    badge: "bg-red-500/15 text-red-300 border-red-400/30",
    dot: "bg-red-400 shadow-[0_0_18px_rgba(248,113,113,0.95)]",
    label: "OFF",
  };
}

function getProfitValue(profitPayload, summaryPayload) {
  return (
    profitPayload?.total_profit ||
    profitPayload?.total_profit_incl_vat ||
    profitPayload?.profit ||
    profitPayload?.total ||
    summaryPayload?.total_profit ||
    summaryPayload?.profit_total ||
    0
  );
}

function getSubmissionList(historyPayload, summaryPayload) {
  const candidates =
    historyPayload?.items ||
    historyPayload?.submissions ||
    historyPayload?.recent ||
    summaryPayload?.recent_submissions ||
    summaryPayload?.items ||
    [];

  if (Array.isArray(candidates)) return candidates.slice(0, 8);
  return [];
}

export default function LiveMissionMetricsPanel() {
  const [status, setStatus] = useState(null);
  const [profit, setProfit] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");

  async function refresh() {
    try {
      setError("");

      const [statusResult, profitResult, summaryResult, historyResult] =
        await Promise.allSettled([
          fetchAutonomousStatus(),
          fetchSubmissionProfit(),
          fetchSubmissionSummary(),
          fetchSubmissionHistory(),
        ]);

      if (statusResult.status === "fulfilled") setStatus(statusResult.value);
      if (profitResult.status === "fulfilled") setProfit(profitResult.value);
      if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
      if (historyResult.status === "fulfilled") setHistory(historyResult.value);

      const failures = [statusResult, profitResult, summaryResult, historyResult]
        .filter((x) => x.status === "rejected")
        .map((x) => x.reason?.message)
        .filter(Boolean);

      if (failures.length) {
        setError(failures[0]);
      }

      setUpdatedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message || "Unable to refresh live mission metrics.");
    }
  }

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, []);

  const mode = useMemo(() => detectSystemMode(status), [status]);
  const styles = modeStyles(mode);
  const profitValue = getProfitValue(profit, summary);
  const submissions = getSubmissionList(history, summary);

  const submittedCount =
    summary?.submitted ||
    summary?.total_submitted ||
    summary?.submission_count ||
    submissions.length ||
    0;

  const failedCount =
    summary?.failed ||
    summary?.total_failed ||
    summary?.failure_count ||
    0;

  return (
    <section className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-4 shadow-2xl shadow-black/20 backdrop-blur">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-[0.2em] text-cyan-300">
            Live Mission Status
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            System mode, profit counter and successful submission feed.
          </p>
        </div>

        <button
          onClick={refresh}
          className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-cyan-400/50 hover:text-cyan-200"
        >
          Refresh Now
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            Mode
          </div>
          <div className={`mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-bold ${styles.badge}`}>
            <span className={`h-2.5 w-2.5 rounded-full ${styles.dot}`} />
            {styles.label}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            Real-Time Profit
          </div>
          <div className="mt-3 text-3xl font-black text-emerald-300">
            {formatRand(profitValue)}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            Submitted
          </div>
          <div className="mt-3 text-3xl font-black text-cyan-300">
            {submittedCount}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
            Failed
          </div>
          <div className="mt-3 text-3xl font-black text-red-300">
            {failedCount}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-[0.18em] text-slate-300">
            Submission Success Feed
          </h3>
          <span className="text-xs text-slate-500">
            Updated: {updatedAt || "loading..."}
          </span>
        </div>

        {submissions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 p-4 text-sm text-slate-400">
            No recent submissions returned yet. Once the backend returns submission history, this feed will populate automatically.
          </div>
        ) : (
          <div className="space-y-2">
            {submissions.map((item, index) => {
              const rfq =
                item.buyer_rfq_number ||
                item.rfq_number ||
                item.reference ||
                item.tender_number ||
                `Submission ${index + 1}`;

              const buyer =
                item.buyer_name ||
                item.organ_of_state ||
                item.department ||
                item.client ||
                "Buyer not shown";

              const statusText =
                item.submission_status ||
                item.status ||
                item.pipeline_status ||
                "submitted";

              const amount =
                item.total_profit ||
                item.profit ||
                item.total_sell_incl_vat ||
                item.value ||
                0;

              return (
                <div
                  key={`${rfq}-${index}`}
                  className="grid gap-2 rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-sm md:grid-cols-[1fr_auto]"
                >
                  <div>
                    <div className="font-bold text-white">{rfq}</div>
                    <div className="text-slate-400">{buyer}</div>
                  </div>
                  <div className="flex items-center gap-3 md:justify-end">
                    <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold uppercase text-emerald-300">
                      {statusText}
                    </span>
                    <span className="font-bold text-emerald-300">
                      {formatRand(amount)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-200">
          Live metrics warning: {error}
        </div>
      )}
    </section>
  );
}
