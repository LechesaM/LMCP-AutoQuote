import { AlertTriangle, Activity, Clock3, Gauge, ShieldCheck, Siren } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function RuntimeStabilityPanel({ snapshot, loading = false, refreshing = false, error = "" }) {
  if (loading) {
    return (
      <SectionPanel title="Runtime Stability" description="Runtime degradation, fallback resilience and deployment stability">
        <SkeletonCard lines={5} />
      </SectionPanel>
    );
  }

  const state = snapshot?.status === "healthy" ? "ready" : "stale";

  return (
    <SectionPanel
      title="Runtime Stability"
      description="Runtime degradation frequency, queue instability, stale telemetry, worker instability and deployment instability."
      state={state}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {snapshot?.dataSource || "runtime_fallback"}
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Stability Score" value={formatNumber(snapshot?.stabilityScore)} description="Higher means fewer operational issues" tone={snapshot?.stabilityScore > 80 ? "green" : "amber"} />
        <TelemetryStat label="Queue Lag" value={`${formatNumber(snapshot?.queueLagMinutes)}m`} description="Queue instability signal" tone={snapshot?.queueLagMinutes > 30 ? "red" : "amber"} />
        <TelemetryStat label="Telemetry Freshness" value={`${formatNumber(snapshot?.telemetryFreshnessMinutes)}m`} description="Freshness window" tone={snapshot?.telemetryFreshnessMinutes > 15 ? "amber" : "green"} />
        <TelemetryStat label="Worker Stale" value={formatNumber(snapshot?.workerStaleCount)} description="Heartbeat instability" tone={snapshot?.workerStaleCount > 0 ? "amber" : "green"} />
        <TelemetryStat label="Source Failures" value={formatNumber(snapshot?.sourceFailureCount)} description="Source instability" tone={snapshot?.sourceFailureCount > 0 ? "red" : "green"} />
        <TelemetryStat label="Runtime Alerts" value={formatNumber(snapshot?.alertCount)} description="Alert volume after tuning" tone={snapshot?.alertCount > 0 ? "amber" : "green"} />
        <TelemetryStat label="Anomalies" value={formatNumber(snapshot?.anomalyCount)} description="Advisory anomaly count" tone={snapshot?.anomalyCount > 0 ? "amber" : "green"} />
        <TelemetryStat label="Window Size" value={formatNumber(snapshot?.windowSize)} description="Recent stabilization window" tone="slate" />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Activity size={14} className="text-command-cyan" /> Degradation Trends
          </div>
          <div className="mt-3 space-y-2">
            {(snapshot?.degradationTrends || []).map((trend) => (
              <div key={trend.label} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 p-3 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">{trend.label}</span>
                  <span className="text-xs uppercase tracking-[.22em] text-slate-500">{formatNumber(trend.value)}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-black uppercase tracking-[.2em] text-slate-400">
                  <span className="rounded-full border border-command-green/25 bg-command-green/10 px-2 py-1">Healthy {formatNumber(trend.healthy)}</span>
                  <span className="rounded-full border border-command-amber/25 bg-command-amber/10 px-2 py-1">Degraded {formatNumber(trend.degraded)}</span>
                  <span className="rounded-full border border-command-red/25 bg-command-red/10 px-2 py-1">Failing {formatNumber(trend.failing)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Siren size={14} className="text-command-amber" /> Operational Warnings
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {(snapshot?.operationalWarnings || []).length ? (
              snapshot.operationalWarnings.map((warning) => (
                <div key={warning} className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2">
                  {warning}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No stabilization warnings detected.</div>
            )}
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-black uppercase tracking-[.22em]">
            <span className="inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-950/45 px-3 py-1 text-slate-300">
              <Gauge size={13} className="text-command-cyan" /> Advisory only
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-950/45 px-3 py-1 text-slate-300">
              <Clock3 size={13} className="text-command-green" /> Polling every 30s
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-slate-700/60 bg-slate-950/45 px-3 py-1 text-slate-300">
              <ShieldCheck size={13} className="text-command-green" /> Governance preserved
            </span>
            {error ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-command-red/40 bg-command-red/10 px-3 py-1 text-command-red">
                <AlertTriangle size={13} /> Refresh error
              </span>
            ) : null}
            {refreshing ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-command-cyan/40 bg-command-cyan/10 px-3 py-1 text-command-cyan">
                <Clock3 size={13} /> Refreshing
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
