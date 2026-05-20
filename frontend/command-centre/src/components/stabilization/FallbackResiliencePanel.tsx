import { Database, RefreshCcw, ShieldAlert } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function FallbackResiliencePanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Fallback Resilience" description="Fallback activation and recovery hygiene">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Fallback Resilience"
      description="Tracks fallback activation frequency, stale fallback detection and runtime recovery success."
      state={snapshot?.status === "healthy" ? "ready" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Fallback Activations" value={formatNumber(snapshot?.fallbackActivations)} description="How often fallback has activated" tone={snapshot?.fallbackActivations > 0 ? "amber" : "green"} />
        <TelemetryStat label="Stale Fallbacks" value={formatNumber(snapshot?.staleFallbacks)} description="Fallbacks that need cleanup" tone={snapshot?.staleFallbacks > 0 ? "red" : "green"} />
        <TelemetryStat label="Recovery Success" value={`${formatNumber(snapshot?.recoverySuccessRate)}%`} description="Runtime recovery success rate" tone={snapshot?.runtimeRecoverySuccess ? "green" : "amber"} />
        <TelemetryStat label="Advisory" value={snapshot?.advisoryOnly ? "Yes" : "No"} description="No automatic recovery actions" tone="slate" />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Database size={14} className="text-command-cyan" /> Fallback Summary
          </div>
          <pre className="mt-3 overflow-x-auto rounded-2xl border border-slate-800/70 bg-slate-950/50 p-3 text-[11px] leading-5 text-slate-300">
            {JSON.stringify(snapshot?.fallbackHealthSummary || {}, null, 2)}
          </pre>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <ShieldAlert size={14} className="text-command-amber" /> Fallback Warnings
          </div>
          <div className="mt-3 space-y-2">
            {(snapshot?.warnings || []).length ? (
              snapshot.warnings.map((warning) => (
                <div key={warning} className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2">
                  {warning}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No fallback warnings detected.</div>
            )}
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs font-black uppercase tracking-[.22em] text-slate-400">
            <RefreshCcw size={13} className="text-command-green" /> Runtime cleanup remains dry-run only
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
