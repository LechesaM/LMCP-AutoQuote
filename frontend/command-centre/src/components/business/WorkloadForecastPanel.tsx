import SectionPanel from "../ui/SectionPanel.tsx";

export default function WorkloadForecastPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};

  return (
    <SectionPanel title="Workload Forecast" description="Queue growth and operator demand projections." state={state}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Queue growth: {summary.queueGrowth || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Operator workload: {summary.operatorWorkload || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Review demand: {summary.estimatedReviewDemand || 0}</div>
      </div>
    </SectionPanel>
  );
}

