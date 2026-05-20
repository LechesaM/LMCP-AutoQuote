import { MessageSquareMore, Smile, SlidersHorizontal } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function OperatorUXFeedbackPanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Operator UX Feedback" description="Queue pain points and review friction trends">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Operator UX Feedback"
      description="Summarised queue pain points, review friction and evidence handling feedback."
      state={snapshot?.status === "healthy" ? "ready" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Pain Points" value={snapshot?.painPoints?.length || 0} description="Captured operator friction" tone={snapshot?.painPoints?.length ? "amber" : "green"} />
        <TelemetryStat label="Feedback Items" value={snapshot?.feedbackItems?.length || 0} description="Operational summaries" tone="cyan" />
        <TelemetryStat label="Trend Keys" value={Object.keys(snapshot?.trendSummary || {}).length || 0} description="Trend summary fields" tone="slate" />
        <TelemetryStat label="Signals" value={Object.keys(snapshot?.operationalSignals || {}).length || 0} description="Operational feedback signals" tone="slate" />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <MessageSquareMore size={14} className="text-command-cyan" /> Pain Points
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {(snapshot?.painPoints || []).length ? (
              snapshot.painPoints.map((point) => (
                <div key={point} className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2">
                  {point}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No operator friction reported.</div>
            )}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <SlidersHorizontal size={14} className="text-command-green" /> Feedback Summary
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {(snapshot?.feedbackItems || []).map((item) => (
              <div key={item.label} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2">
                <div className="font-semibold text-white">{item.label}</div>
                <div className="mt-1 text-slate-400">{item.value}</div>
              </div>
            ))}
            <div className="rounded-2xl border border-command-green/20 bg-command-green/10 px-3 py-2 text-command-green">
              <Smile size={13} className="mr-2 inline-block" />
              Feedback is summarised for operational improvement only.
            </div>
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
