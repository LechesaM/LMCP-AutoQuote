import { Activity } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function PrometheusHealthPanel({ prometheus = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  if (loading) {
    return (
      <SectionPanel title="Prometheus Health" description="Read-only scrape visibility for runtime metrics." state="loading">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }
  const metrics = prometheus.metrics || {};
  const textPreview = String(prometheus.text || "")
    .split("\n")
    .filter(Boolean)
    .slice(0, 4)
    .join(" · ");
  return (
    <SectionPanel
      title="Prometheus Health"
      description="Runtime metrics export, scrape readiness and metric coverage."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {prometheus.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? (
        <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div>
      ) : null}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Metric Count" value={formatNumber(prometheus.metricsCount)} description="Exported scrape series" tone="cyan" />
        <TelemetryStat label="RFQs Qualified" value={formatNumber(metrics.rfqs_qualified || metrics.rfqsQualified)} description="Quality signals" tone="green" />
        <TelemetryStat label="Runtime Alerts" value={formatNumber(metrics.runtime_alerts || metrics.runtimeAlerts)} description="Alert series" tone="amber" />
        <TelemetryStat label="DLQ Count" value={formatNumber(metrics.dlq_count || metrics.dlqCount)} description="Dead-letter queue depth" tone="red" />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
          <Activity size={14} className="text-command-cyan" /> Export Preview
        </div>
        <div className="mt-2 line-clamp-2 text-slate-400">{textPreview || "No Prometheus text available."}</div>
      </div>
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
