import SectionPanel from "../ui/SectionPanel.tsx";

export default function OperatorTrendPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};
  const throughput = data?.throughputTrends || {};

  return (
    <SectionPanel title="Operator Trends" description="Throughput, escalation and review-efficiency trends." state={state}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Average reviews/operator: {Number(summary.averageReviewsPerOperator || 0).toFixed(2)}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Throughput trends: {summary.throughputTrendCount || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Escalation trends: {summary.escalationTrendCount || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Queue ownership trends: {summary.queueOwnershipTrendCount || 0}</div>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {Object.entries(throughput).slice(0, 8).map(([operator, count]) => (
          <div key={operator} className="flex items-center justify-between rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-sm text-slate-300">
            <span>{operator}</span>
            <span className="font-black text-white">{String(count)}</span>
          </div>
        ))}
      </div>
    </SectionPanel>
  );
}

