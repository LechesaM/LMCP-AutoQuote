import { AlertTriangle, HeartPulse, Users2 } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function OperatorFatiguePanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Operator Fatigue" description="Workload strain and fatigue warnings">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Operator Fatigue"
      description="Tracks prolonged queue exposure, escalation load and focus-session exhaustion."
      state={snapshot?.status === "healthy" ? "ready" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Fatigue Score" value={formatNumber(snapshot?.fatigueScore)} description="Advisory only" tone={snapshot?.fatigueScore > 50 ? "amber" : "green"} />
        <TelemetryStat label="Rows" value={formatNumber(snapshot?.fatigueRows?.length)} description="Operator fatigue records" tone="cyan" />
        <TelemetryStat label="Warnings" value={formatNumber(snapshot?.warnings?.length)} description="Fatigue warnings" tone={snapshot?.warnings?.length ? "amber" : "green"} />
        <TelemetryStat label="Rebalance Recs" value={formatNumber(snapshot?.workloadRebalanceRecommendations?.length)} description="Workload rebalance suggestions" tone="slate" />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <Users2 size={14} className="text-command-cyan" /> Fatigue Rows
          </div>
          <div className="mt-3 space-y-2">
            {(snapshot?.fatigueRows || []).map((row) => (
              <div key={row.operatorId} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">{row.operatorId}</span>
                  <span className="text-[11px] uppercase tracking-[.22em] text-slate-500">score {formatNumber(row.fatigueScore)}</span>
                </div>
                <div className="mt-2 grid gap-2 text-[11px] uppercase tracking-[.2em] text-slate-400 sm:grid-cols-2">
                  <span>Overdue {formatNumber(row.overdueReviews)}</span>
                  <span>Escalations {formatNumber(row.repeatedEscalations)}</span>
                  <span>Queue exposure {formatNumber(row.prolongedQueueExposure)}m</span>
                  <span>Focus exhaustion {formatNumber(row.focusSessionExhaustion)}</span>
                </div>
                {row.warning ? <div className="mt-2 rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2 text-command-amber">{row.warning}</div> : null}
                {row.recommendation ? <div className="mt-2 rounded-2xl border border-command-green/20 bg-command-green/10 px-3 py-2 text-command-green">{row.recommendation}</div> : null}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <HeartPulse size={14} className="text-command-amber" /> Fatigue Warnings
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            {(snapshot?.warnings || []).length ? (
              snapshot.warnings.map((warning) => (
                <div key={warning} className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2">
                  {warning}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No fatigue warnings detected.</div>
            )}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
