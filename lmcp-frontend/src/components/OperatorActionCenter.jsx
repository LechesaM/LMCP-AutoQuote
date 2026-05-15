import { useEffect, useMemo, useState } from "react";
import { API_BASE, getOperatorActionSummary, runOperatorAction } from "../services/operatorActionsApi";

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

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint ? <div className="mt-1 text-sm text-slate-400">{hint}</div> : null}
    </div>
  );
}

function ActionBadge({ action }) {
  const normalized = String(action || "unknown").toLowerCase();

  const palette =
    normalized.includes("force")
      ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/20"
      : normalized.includes("retry")
      ? "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/20"
      : normalized.includes("reject")
      ? "bg-rose-500/15 text-rose-300 border-rose-500/20"
      : normalized.includes("pause")
      ? "bg-orange-500/15 text-orange-300 border-orange-500/20"
      : normalized.includes("review")
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
      : "bg-slate-500/15 text-slate-300 border-slate-500/20";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${palette}`}>
      {action || "unknown"}
    </span>
  );
}

export default function OperatorActionCenter() {
  const [summary, setSummary] = useState(null);
  const [buyerRfq, setBuyerRfq] = useState("");
  const [quoteNumber, setQuoteNumber] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadSummary() {
    setError("");
    try {
      const data = await getOperatorActionSummary();
      setSummary(data);
    } catch (err) {
      setError(err.message || "Could not load operator action summary.");
    }
  }

  useEffect(() => {
    loadSummary();
  }, []);

  useEffect(() => {
    function handleLiveRefresh() {
      loadSummary();
    }
    window.addEventListener("lmcp-live-refresh", handleLiveRefresh);
    return () => window.removeEventListener("lmcp-live-refresh", handleLiveRefresh);
  }, []);

  async function handleAction(action) {
    setBusy(action);
    setError("");
    setMessage("");

    try {
      const payload = {
        buyer_rfq_number: buyerRfq,
        quote_number: quoteNumber,
        source_name: sourceName,
        reason,
      };

      const result = await runOperatorAction(action, payload);
      setMessage(result?.message || `Action ${action} completed.`);
      await loadSummary();

      window.dispatchEvent(
        new CustomEvent("lmcp-live-refresh", {
          detail: { triggeredAt: new Date().toISOString(), source: "operator-action-center" },
        })
      );
    } catch (err) {
      setError(err.message || `Action ${action} failed.`);
    } finally {
      setBusy("");
    }
  }

  const stats = useMemo(() => {
    const s = summary?.summary || {};
    return {
      total: s.total_actions || 0,
      forced: s.force_quote || 0,
      retries: s.retry_submission || 0,
      rejected: s.reject_opportunity || 0,
      paused: s.pause_source || 0,
    };
  }, [summary]);

  const recent = summary?.recent_actions || [];

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-violet-300">
            Step 19
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Operator Action Center</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Manual control point for forcing quote generation, retrying failed submissions, rejecting RFQs, marking review complete, and pausing sources.
          </p>
        </div>

        <button
          onClick={loadSummary}
          className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
        >
          Refresh Actions
        </button>
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
        <StatCard label="Total Actions" value={stats.total} hint="Operator commands recorded" />
        <StatCard label="Force Quote" value={stats.forced} hint="RFQs pushed to quote" />
        <StatCard label="Retries" value={stats.retries} hint="Submission retries" />
        <StatCard label="Rejected" value={stats.rejected} hint="Manually blocked RFQs" />
        <StatCard label="Paused Sources" value={stats.paused} hint="Portal/source pauses" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-lg font-semibold">Action Form</h3>

          <div className="mt-4 space-y-4">
            <label className="block">
              <span className="text-sm text-slate-300">Buyer RFQ Number</span>
              <input
                value={buyerRfq}
                onChange={(e) => setBuyerRfq(e.target.value)}
                placeholder="e.g. BSM 110/26"
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none"
              />
            </label>

            <label className="block">
              <span className="text-sm text-slate-300">Quote Number</span>
              <input
                value={quoteNumber}
                onChange={(e) => setQuoteNumber(e.target.value)}
                placeholder="Optional"
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none"
              />
            </label>

            <label className="block">
              <span className="text-sm text-slate-300">Source / Portal Name</span>
              <input
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                placeholder="Optional"
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none"
              />
            </label>

            <label className="block">
              <span className="text-sm text-slate-300">Reason / Note</span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Operator note"
                rows={3}
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none"
              />
            </label>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <button
              onClick={() => handleAction("force-quote")}
              disabled={busy !== ""}
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
            >
              {busy === "force-quote" ? "Running..." : "Force Quote"}
            </button>

            <button
              onClick={() => handleAction("retry-submission")}
              disabled={busy !== ""}
              className="rounded-2xl bg-fuchsia-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
            >
              {busy === "retry-submission" ? "Running..." : "Retry Submission"}
            </button>

            <button
              onClick={() => handleAction("mark-review-complete")}
              disabled={busy !== ""}
              className="rounded-2xl bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
            >
              {busy === "mark-review-complete" ? "Running..." : "Mark Review Complete"}
            </button>

            <button
              onClick={() => handleAction("reject-opportunity")}
              disabled={busy !== ""}
              className="rounded-2xl bg-rose-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
            >
              {busy === "reject-opportunity" ? "Running..." : "Reject Opportunity"}
            </button>

            <button
              onClick={() => handleAction("pause-source")}
              disabled={busy !== ""}
              className="rounded-2xl bg-orange-400 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60 md:col-span-2"
            >
              {busy === "pause-source" ? "Running..." : "Pause Source / Portal"}
            </button>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Recent Operator Actions</h3>
            <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Latest 30</span>
          </div>

          <div className="mt-4 space-y-3 max-h-[720px] overflow-y-auto pr-2">
            {recent.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-400">
                No operator actions recorded yet.
              </div>
            ) : (
              recent.map((item, index) => (
                <article key={`${item.action}-${item.created_at}-${index}`} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <ActionBadge action={item.action} />
                    <span className="text-xs text-slate-400">{formatDate(item.created_at)}</span>
                    <span className="text-xs text-slate-500">{item.status}</span>
                  </div>

                  <div className="mt-3 text-sm text-slate-300">
                    RFQ: {item.buyer_rfq_number || "—"}
                  </div>
                  <div className="mt-1 text-sm text-slate-300">
                    Quote: {item.quote_number || "—"}
                  </div>
                  <div className="mt-1 text-sm text-slate-300">
                    Source: {item.source_name || "—"}
                  </div>

                  {item.reason ? (
                    <div className="mt-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300">
                      {item.reason}
                    </div>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
