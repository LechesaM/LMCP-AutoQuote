import { AlertTriangle } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function SLAMetricsPanel({ sla = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  const snapshot = sla.sla || sla;
  if (loading) {
    return (
      <SectionPanel title="SLA Monitoring" description="Operational service-level monitoring." state="loading">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="SLA Monitoring"
      description="Processing latency, queue wait, source uptime, acknowledgement time and backup freshness."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {snapshot.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {(snapshot.slaMetrics || []).map((metric) => (
          <TelemetryStat
            key={metric.name}
            label={metric.name.replace(/_/g, " ")}
            value={formatNumber(metric.value)}
            description={metric.state}
            tone={metric.state === "healthy" ? "green" : metric.state === "degraded" ? "amber" : "red"}
          />
        ))}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Healthy</div>
          <div className="mt-2 text-3xl font-black text-white">{snapshot.summary?.healthy || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Degraded</div>
          <div className="mt-2 text-3xl font-black text-white">{snapshot.summary?.degraded || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[.24em] text-slate-400">
            <AlertTriangle size={13} className="text-command-amber" /> Failing
          </div>
          <div className="mt-2 text-3xl font-black text-white">{snapshot.summary?.failing || 0}</div>
        </div>
      </div>
      {snapshot.breachedMetrics?.length ? (
        <div className="mt-4 rounded-2xl border border-command-red/30 bg-command-red/10 p-4 text-sm text-slate-200">
          Breached metrics: {snapshot.breachedMetrics.map((item) => item.name).join(", ")}
        </div>
      ) : null}
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
