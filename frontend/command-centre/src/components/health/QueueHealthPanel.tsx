import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import StateBadge from "../ui/StateBadge.tsx";
import useQueueStore from "../../store/queueStore";

export default function QueueHealthPanel() {
  const summary = useQueueStore((state) => state.summary);
  const dataSource = useQueueStore((state) => state.dataSource);
  const loading = useQueueStore((state) => state.loading);
  const refreshing = useQueueStore((state) => state.refreshing);
  const stale = useQueueStore((state) => state.stale);
  const error = useQueueStore((state) => state.error);

  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";

  return (
    <SectionPanel title="Queue Health" description="Operator capacity and queue lag remain controlled and advisory." state={state} actions={<StateBadge state={dataSource === "runtime" ? "ready" : "stale"} />}>
      <div className="grid gap-3 md:grid-cols-4">
        <TelemetryStat label="Operator Capacity" value={summary.operatorCapacity || 1000} tone="cyan" />
        <TelemetryStat label="Used" value={summary.operatorCapacityUsed || 0} tone="amber" />
        <TelemetryStat label="Remaining" value={summary.operatorCapacityRemaining || 0} tone="green" />
        <TelemetryStat label="Queue Lag" value={summary.queueLagMinutes || 0} tone="red" />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          Pending reviews: <span className="font-bold text-white">{summary.pendingReviews || 0}</span>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          Approved today: <span className="font-bold text-white">{summary.approvedToday || 0}</span>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          Overdue reviews: <span className="font-bold text-white">{summary.overdueReviews || 0}</span>
        </div>
      </div>
    </SectionPanel>
  );
}
