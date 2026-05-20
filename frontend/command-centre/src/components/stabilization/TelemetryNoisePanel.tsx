import { BellRing, Megaphone, ShieldAlert } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function TelemetryNoisePanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Telemetry Noise Reduction" description="Duplicate alert tuning and noise suppression">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Telemetry Noise Reduction"
      description="Duplicate alerts are deduplicated and grouped, while critical alerts remain visible."
      state={snapshot?.status === "healthy" ? "ready" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Retained Alerts" value={formatNumber(snapshot?.retainedCount)} description="Alerts preserved after deduplication" tone="cyan" />
        <TelemetryStat label="Suppressed" value={formatNumber(snapshot?.suppressedCount)} description="Repeated alerts removed" tone={snapshot?.suppressedCount > 0 ? "green" : "slate"} />
        <TelemetryStat label="Critical Alerts" value={formatNumber(snapshot?.criticalCount)} description="Critical alerts are never hidden" tone={snapshot?.criticalCount > 0 ? "red" : "green"} />
        <TelemetryStat label="Noise Score" value={formatNumber(snapshot?.noiseScore)} description="Lower is quieter" tone={snapshot?.noiseScore > 0 ? "amber" : "green"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <BellRing size={14} className="text-command-cyan" /> Alert Groups
          </div>
          <div className="mt-3 space-y-2">
            {(snapshot?.alertGroups || []).map((group) => (
              <div key={`${group.label}-${group.severity}`} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">{group.label}</span>
                  <span className="text-xs uppercase tracking-[.22em] text-slate-500">{formatNumber(group.count)}</span>
                </div>
                <div className="mt-1 text-[11px] uppercase tracking-[.2em] text-slate-400">{group.severity}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Megaphone size={14} className="text-command-green" /> Alert Samples
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {(snapshot?.alerts || []).slice(0, 5).map((alert, index) => (
              <div key={`${alert.alertId || index}`} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">{String(alert.title || alert.type || "Alert")}</span>
                  <span className="text-[11px] uppercase tracking-[.22em] text-slate-500">{String(alert.severity || "info")}</span>
                </div>
                <div className="mt-1 text-slate-400">{String(alert.message || "")}</div>
              </div>
            ))}
            {!(snapshot?.alerts || []).length ? (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No retained alert samples.</div>
            ) : null}
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs font-black uppercase tracking-[.22em] text-slate-400">
            <ShieldAlert size={13} className="text-command-amber" /> Critical alerts remain visible
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
