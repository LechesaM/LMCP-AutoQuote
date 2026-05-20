import SectionPanel from "../ui/SectionPanel.tsx";

export default function RevenueProjectionPanel({ data, loading, refreshing, stale, error }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};
  return (
    <SectionPanel title="Revenue Projection" description="Heuristic and non-financial projection for operational planning." state={state}>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Projected opportunity value: R{new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(summary.projectedRfqOpportunityValue || 0))}</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Margin opportunity: {Number(summary.projectedMarginOpportunity || 0).toFixed(2)}%</div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4 text-sm text-slate-300">Source-based opportunity: {summary.sourceBasedOpportunityProjection || 0}</div>
      </div>
    </SectionPanel>
  );
}

