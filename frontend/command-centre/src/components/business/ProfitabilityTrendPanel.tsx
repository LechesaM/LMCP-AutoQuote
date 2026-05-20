import MetricCard from "../dashboard/MetricCard.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";

export default function ProfitabilityTrendPanel({ data, loading, refreshing, stale, error, onRetry }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.summary || {};

  return (
    <SectionPanel
      title="Profitability Trends"
      description="Estimated profitability, margins, evidence impact and stale-pricing pressure."
      state={state}
      actions={
        onRetry ? (
          <button className="rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-xs font-black uppercase tracking-[.24em] text-command-cyan" onClick={onRetry} type="button">
            Refresh
          </button>
        ) : null
      }
    >
      <div className="grid gap-3 lg:grid-cols-3">
        <MetricCard title="Estimated Total Profit" value={`R${new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(summary.estimatedTotalProfit || 0))}`} subtitle="Heuristic opportunity value" state={state} accent="cyan" />
        <MetricCard title="Average Margin" value={`${Number(summary.averageMargin || 0).toFixed(2)}%`} subtitle="Estimated supply margin" state={state} accent="green" />
        <MetricCard title="High-Value RFQs" value={summary.highValueRfqCount || 0} subtitle="Above R30,000 profit" state={state} accent="amber" />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Margin Distribution</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {Object.entries(data?.estimatedMarginDistribution || {}).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="uppercase tracking-[.18em] text-slate-500">{key.replaceAll("_", " ")}</span>
                <span className="font-black text-white">{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/55 p-4">
          <div className="text-xs font-black uppercase tracking-[.24em] text-command-cyan">Evidence Impact</div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            <div className="flex items-center justify-between"><span>Low-confidence profitability</span><span className="font-black">{summary.lowConfidenceProfitabilityCount || 0}</span></div>
            <div className="flex items-center justify-between"><span>Stale pricing impact</span><span className="font-black">{summary.stalePricingImpactCount || 0}</span></div>
            <div className="flex items-center justify-between"><span>Supplier evidence avg</span><span className="font-black">{Number(summary.supplierEvidenceImpactAverage || 0).toFixed(2)}</span></div>
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}

