import { Trash2, TimerReset } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function RuntimeCleanupPanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Runtime Cleanup" description="Dry-run cleanup and stale artifact review">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Runtime Cleanup"
      description="Dry-run cleanup recommendations for stale telemetry, temp artifacts and expired runtime caches."
      state={snapshot?.status === "healthy" ? "ready" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Dry Run Only" value={snapshot?.dryRunOnly ? "Yes" : "No"} description="No destructive cleanup by default" tone="green" />
        <TelemetryStat label="Confirmed" value={snapshot?.confirmed ? "Yes" : "No"} description="Explicit operator confirmation" tone={snapshot?.confirmed ? "green" : "amber"} />
        <TelemetryStat label="Candidates" value={formatNumber(snapshot?.wouldCleanup?.length)} description="Potential cleanup items" tone="cyan" />
        <TelemetryStat label="Warnings" value={formatNumber(snapshot?.warnings?.length)} description="Cleanup warnings" tone={snapshot?.warnings?.length ? "amber" : "green"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Trash2 size={14} className="text-command-cyan" /> Cleanup Candidates
          </div>
          <div className="mt-3 space-y-2">
            {(snapshot?.wouldCleanup || []).map((item) => (
              <div key={item.label} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">{item.label}</span>
                  <span className="text-xs uppercase tracking-[.22em] text-slate-500">{formatNumber(item.count)}</span>
                </div>
              </div>
            ))}
            {!(snapshot?.wouldCleanup || []).length ? (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No cleanup candidates identified.</div>
            ) : null}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <TimerReset size={14} className="text-command-amber" /> Cleanup Controls
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {(snapshot?.blockers || []).length ? snapshot.blockers.map((blocker) => (
              <div key={blocker} className="rounded-2xl border border-command-red/20 bg-command-red/10 px-3 py-2 text-command-red">
                {blocker}
              </div>
            )) : (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No cleanup blockers detected.</div>
            )}
            <div className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2 text-command-amber">
              Runtime cleanup remains dry-run only unless explicit confirmation is provided.
            </div>
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
