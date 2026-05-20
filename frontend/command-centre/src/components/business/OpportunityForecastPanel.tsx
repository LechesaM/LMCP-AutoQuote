import SectionPanel from "../ui/SectionPanel.tsx";

export default function OpportunityForecastPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};

  return (
    <SectionPanel title="Opportunity Forecast" description="RFQ growth, review demand and source growth outlook." state={state}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">RFQ growth: {summary.rfqGrowth || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Review demand: {summary.reviewDemand || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Source growth: {summary.sourceGrowth || 0}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Opportunity value projection: R{new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(summary.opportunityValueProjection || 0))}</div>
      </div>
    </SectionPanel>
  );
}

