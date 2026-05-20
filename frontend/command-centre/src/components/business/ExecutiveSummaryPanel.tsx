import { BadgeDollarSign, Gauge, LineChart, ShieldCheck, TrendingUp, Users2 } from "lucide-react";
import MetricCard from "../dashboard/MetricCard.tsx";
import SectionPanel from "../ui/SectionPanel.tsx";
import StateBadge from "../ui/StateBadge.tsx";

export default function ExecutiveSummaryPanel({ data, loading, refreshing, stale, error, onRetry }: any) {
  const state = error ? "error" : loading ? "loading" : refreshing ? "refreshing" : stale ? "stale" : "ready";
  const summary = data?.executiveSummary || {};
  const highlights = Array.isArray(data?.strategicHighlights) ? data.strategicHighlights : [];

  return (
    <SectionPanel
      title="Executive Summary"
      description="Strategic operating view for supervised-live LMCP."
      state={state}
      actions={
        onRetry ? (
          <button className="rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-xs font-black uppercase tracking-[.24em] text-command-cyan" onClick={onRetry} type="button">
            Refresh
          </button>
        ) : null
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 xl:grid-cols-3">
        <MetricCard title="RFQs Harvested" value={summary.rfqsHarvested || 0} subtitle="Executive intake" icon={LineChart} accent="cyan" state={state} />
        <MetricCard title="RFQs Qualified" value={summary.rfqsQualified || 0} subtitle="Supply and delivery fit" icon={BadgeDollarSign} accent="green" state={state} />
        <MetricCard title="RFQs Reviewed" value={summary.rfqsReviewed || 0} subtitle="Operator throughput" icon={Users2} accent="amber" state={state} />
        <MetricCard title="Estimated Profitability" value={`R${new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(summary.estimatedProfitability || 0))}`} subtitle="Projected opportunity value" icon={TrendingUp} accent="cyan" state={state} />
        <MetricCard title="Queue Pressure" value={summary.queuePressure || 0} subtitle="Minutes of queue lag" icon={Gauge} accent="red" state={state} />
        <MetricCard title="Governance Incidents" value={summary.governanceIncidents || 0} subtitle="Manual control events" icon={ShieldCheck} accent="amber" state={state} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <StateBadge state={state} />
        <div className="text-xs uppercase tracking-[.24em] text-slate-500">SLA {summary.slaHealth || "healthy"}</div>
        <div className="text-xs uppercase tracking-[.24em] text-slate-500">Source reliability {Number(summary.sourceReliability || 0).toFixed(1)}%</div>
      </div>
      {highlights.length ? (
        <div className="mt-4 grid gap-2">
          {highlights.map((item: string, index: number) => (
            <div key={`${item}-${index}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/55 px-4 py-3 text-sm text-slate-300">
              {item}
            </div>
          ))}
        </div>
      ) : null}
    </SectionPanel>
  );
}

