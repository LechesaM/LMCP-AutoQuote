import { useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

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
    second: "2-digit",
  });
}

function DecisionBadge({ decision }) {
  const normalized = String(decision || "unknown").toLowerCase();

  const palette =
    normalized === "auto_approve"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/20"
      : normalized === "manual_review"
      ? "bg-amber-500/15 text-amber-300 border-amber-500/20"
      : normalized === "reject"
      ? "bg-rose-500/15 text-rose-300 border-rose-500/20"
      : "bg-slate-500/15 text-slate-300 border-slate-500/20";

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${palette}`}>
      {decision || "unknown"}
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

export default function DecisionIntelligencePanel() {
  const [snapshot, setSnapshot] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  async function loadSnapshot() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/decision-intelligence/summary`);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const data = await response.json();
      setSnapshot(data);
      setLastRefreshAt(new Date().toISOString());
    } catch (err) {
      setError(err.message || "Could not load decision intelligence summary.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSnapshot();
  }, []);

  useEffect(() => {
    function handleLiveRefresh() {
      loadSnapshot();
    }
    window.addEventListener("lmcp-live-refresh", handleLiveRefresh);
    return () => window.removeEventListener("lmcp-live-refresh", handleLiveRefresh);
  }, []);

  useEffect(() => {
    function handleMessage(event) {
      const detail = event.detail || {};
      const payload = detail.payload || {};

      const resolvedType =
        payload?.type ||
        payload?.payload?.type ||
        detail?.payload?.type;

      const resolvedPayload = payload?.payload || payload || {};

      const allowed = new Set([
        "decision_scored",
        "opportunity_auto_approved",
        "opportunity_rejected",
        "opportunity_manual_review",
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

      setEvents((prev) => [item, ...prev].slice(0, 20));
      loadSnapshot();
    }

    window.addEventListener("lmcp-ws-message", handleMessage);
    return () => window.removeEventListener("lmcp-ws-message", handleMessage);
  }, []);

  const stats = useMemo(() => {
    const summary = snapshot?.summary || {};
    return {
      total: summary.total_scored || 0,
      autoApproved: summary.auto_approved || 0,
      manualReview: summary.manual_review || 0,
      rejected: summary.rejected || 0,
      avgScore: summary.average_score || 0,
    };
  }, [snapshot]);

  const top = snapshot?.top_opportunities || [];
  const rejected = snapshot?.recent_rejections || [];

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-900/80 p-6 text-white shadow-2xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-lime-300">
            Step 18
          </div>
          <h2 className="mt-2 text-2xl font-semibold">Decision Intelligence Layer</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Scores opportunities against LMCP rules, prioritises high-value RFQs, and rejects tenders that should not enter the quote pipeline.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="rounded-full border border-lime-500/20 bg-lime-500/10 px-4 py-2 text-xs text-lime-200">
            Last Refresh: {formatDate(lastRefreshAt)}
          </div>

          <button
            onClick={loadSnapshot}
            disabled={loading}
            className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10 disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh Intelligence"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Scored" value={stats.total} hint="RFQs evaluated" />
        <StatCard label="Auto-Approved" value={stats.autoApproved} hint="Ready for quote pipeline" />
        <StatCard label="Manual Review" value={stats.manualReview} hint="Needs operator check" />
        <StatCard label="Rejected" value={stats.rejected} hint="Blocked by LMCP rules" />
        <StatCard label="Avg Score" value={Number(stats.avgScore).toFixed(1)} hint="Decision quality indicator" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">Top Opportunities</h3>
            <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Highest scoring</span>
          </div>

          <div className="mt-4 space-y-3 max-h-[520px] overflow-y-auto pr-2">
            {top.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-400">
                No scored opportunities returned yet.
              </div>
            ) : (
              top.map((item, index) => (
                <article key={`${item.buyer_rfq_number || "rfq"}-${index}`} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <DecisionBadge decision={item.decision} />
                        <span className="text-xs text-slate-400">Score: {item.score}</span>
                      </div>

                      <h4 className="mt-3 text-base font-semibold text-white">
                        {item.title || item.buyer_rfq_number || "Untitled Opportunity"}
                      </h4>

                      <div className="mt-2 text-sm text-slate-300">
                        RFQ: {item.buyer_rfq_number || "—"}
                      </div>
                      <div className="mt-1 text-sm text-slate-300">
                        Buyer: {item.buyer_name || "—"}
                      </div>
                      <div className="mt-1 text-sm text-slate-300">
                        Estimated Profit: {formatMoney(item.estimated_profit)}
                      </div>
                      <div className="mt-1 text-sm text-slate-300">
                        Estimated Margin: {item.estimated_margin_percent ?? "—"}%
                      </div>
                    </div>
                  </div>

                  {Array.isArray(item.reasons) && item.reasons.length > 0 ? (
                    <div className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                      {item.reasons.join(" • ")}
                    </div>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">Recent Rejections</h3>
            <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Blocked</span>
          </div>

          <div className="mt-4 space-y-3 max-h-[520px] overflow-y-auto pr-2">
            {rejected.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-400">
                No rejected opportunities returned yet.
              </div>
            ) : (
              rejected.map((item, index) => (
                <article key={`${item.buyer_rfq_number || "reject"}-${index}`} className="rounded-2xl border border-rose-500/10 bg-rose-500/5 p-4">
                  <DecisionBadge decision={item.decision || "reject"} />

                  <h4 className="mt-3 text-base font-semibold text-white">
                    {item.title || item.buyer_rfq_number || "Rejected Opportunity"}
                  </h4>

                  <div className="mt-2 text-sm text-slate-300">
                    RFQ: {item.buyer_rfq_number || "—"}
                  </div>

                  <div className="mt-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                    {Array.isArray(item.reasons) && item.reasons.length > 0
                      ? item.reasons.join(" • ")
                      : "Rejected by LMCP decision rules."}
                  </div>
                </article>
              ))
            )}
          </div>
        </div>
      </div>

      {events.length > 0 ? (
        <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-lg font-semibold">Live Decision Events</h3>
          <div className="mt-4 space-y-3">
            {events.map((event) => (
              <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 text-sm text-slate-300">
                <span className="text-lime-300">{event.type}</span>
                <span className="mx-2 text-slate-500">•</span>
                <span>{formatDate(event.receivedAt)}</span>
                <span className="mx-2 text-slate-500">•</span>
                <span>{event.data?.buyer_rfq_number || event.data?.title || "decision update"}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
