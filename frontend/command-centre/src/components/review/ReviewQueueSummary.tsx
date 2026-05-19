import { useReviewQueue } from "../../hooks/useReviewQueue";
import { formatCurrency } from "../../utils/formatters";
import StateBadge from "../ui/StateBadge.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function ReviewQueueSummary({ state = "ready", onRetry }) {
  const { items, summary } = useReviewQueue();

  if (state === "loading") {
    return (
      <div className="space-y-5">
        <div className="glass-card rounded-3xl p-5">
          <SkeletonCard lines={4} />
        </div>
        <div className="glass-card rounded-3xl p-5">
          <SkeletonCard lines={3} />
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="glass-card rounded-3xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-black text-white">Review Queue Snapshot</h3>
            <p className="mt-1 text-sm text-slate-400">Unable to load review queue data.</p>
          </div>
          <StateBadge state="error" />
        </div>
        {onRetry ? (
          <button
            onClick={onRetry}
            className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  const queueItems = state === "empty" ? [] : items;
  const queueSummary = state === "empty" ? { total: 0, goCount: 0, manualCount: 0, alerts: [] } : summary;

  return (
    <div className="space-y-5">
      <div className={`glass-card rounded-3xl p-5 ${state === "stale" ? "opacity-85" : ""}`}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-black text-white">Review Queue Snapshot</h3>
            <p className="mt-1 text-sm text-slate-400">Queue state remains advisory until manual operator review.</p>
          </div>
          <StateBadge state={state === "refreshing" ? "refreshing" : state === "stale" ? "stale" : "ready"} />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
            <div className="text-xs font-bold uppercase tracking-[.24em] text-slate-500">Total</div>
            <div className="mt-2 text-3xl font-black text-white">{queueSummary.total}</div>
          </div>
          <div className="rounded-2xl border border-command-green/30 bg-command-green/10 p-4">
            <div className="text-xs font-bold uppercase tracking-[.24em] text-command-green">GO</div>
            <div className="mt-2 text-3xl font-black text-white">{queueSummary.goCount}</div>
          </div>
          <div className="rounded-2xl border border-command-cyan/30 bg-command-cyan/10 p-4">
            <div className="text-xs font-bold uppercase tracking-[.24em] text-command-cyan">Manual Review</div>
            <div className="mt-2 text-3xl font-black text-white">{queueSummary.manualCount}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-3">
        {queueItems.length ? (
          queueItems.map((item) => (
            <div key={item.id} className="glass-card rounded-3xl p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-black text-white">{item.title}</div>
                  <div className="mt-1 text-xs text-slate-400">{item.province}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-black text-command-green">{item.recommendation}</div>
                  <div className="mt-1 text-xs text-slate-400">{formatCurrency(Number(item.value.replace("R", "").replace("M", "")) * 1000000 || 0)}</div>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="glass-card rounded-3xl p-6 text-sm text-slate-400">No review queue items available.</div>
        )}
      </div>
    </div>
  );
}
