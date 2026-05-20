import { Gauge, TimerReset } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function RuntimePerformancePanel({ performance = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  const snapshot = performance.performance || performance;
  if (loading) {
    return (
      <SectionPanel title="Runtime Performance" description="Latency and deployment freshness signals." state="loading">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="Runtime Performance"
      description="API latency, queue response time, database health and build freshness."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {snapshot.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="API Latency" value={`${Number(snapshot.apiLatencyMs || 0).toFixed(1)}ms`} description="Telemetry response latency" tone="cyan" />
        <TelemetryStat label="Queue Response" value={`${Number(snapshot.queueResponseTimeMs || 0).toFixed(1)}ms`} description="Queue responsiveness" tone="amber" />
        <TelemetryStat label="DB Health" value={snapshot.dbResponseHealth || "unknown"} description="Database readiness" tone={snapshot.dbResponseHealth === "healthy" ? "green" : snapshot.dbResponseHealth === "failing" ? "red" : "amber"} />
        <TelemetryStat label="Build Freshness" value={`${Number(snapshot.frontendBuildFreshnessMinutes || -1).toFixed(1)}m`} description="Frontend build timestamp" tone="slate" />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
          <Gauge size={14} className="text-command-green" /> Deployment Health
        </div>
        <div className="mt-2 text-slate-400">Performance monitoring is advisory only and never mutates workflow state.</div>
      </div>
      <div className="mt-4 flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
        <TimerReset size={13} className="text-command-cyan" /> {snapshot.deploymentHealth || "degraded"}
      </div>
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
