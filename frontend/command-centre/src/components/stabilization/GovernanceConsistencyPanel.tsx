import { AlertTriangle, CheckCircle2, FileSearch, ShieldCheck } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

function formatNumber(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 1 }).format(Number(value || 0));
}

export default function GovernanceConsistencyPanel({ snapshot, loading = false }) {
  if (loading) {
    return (
      <SectionPanel title="Governance Consistency" description="Manual-only governance, review_ready and proof capture consistency">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }

  return (
    <SectionPanel
      title="Governance Consistency"
      description="Verifies review_ready enforcement, proof capture consistency, RBAC integrity and manual-only governance."
      state={snapshot?.status === "healthy" ? "ready" : snapshot?.blockers?.length ? "error" : "stale"}
      actions={<span className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">{snapshot?.dataSource || "runtime_fallback"}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <TelemetryStat label="Consistency Score" value={formatNumber(snapshot?.consistencyScore)} description="Advisory only" tone={snapshot?.consistencyScore >= 90 ? "green" : "amber"} />
        <TelemetryStat label="Checks" value={formatNumber(snapshot?.checks?.length)} description="Governance validation checks" tone="cyan" />
        <TelemetryStat label="Inconsistencies" value={formatNumber(snapshot?.inconsistencies?.length)} description="Detected governance drift" tone={snapshot?.inconsistencies?.length ? "amber" : "green"} />
        <TelemetryStat label="Audit Attribution Missing" value={snapshot?.auditAttributionMissing ? "Yes" : "No"} description="Operator attribution completeness" tone={snapshot?.auditAttributionMissing ? "red" : "green"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <ShieldCheck size={14} className="text-command-green" /> Governance Checks
          </div>
          <div className="mt-3 space-y-2">
            {(snapshot?.checks || []).map((check) => (
              <div key={check.label} className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-white">{check.label}</span>
                  <span className={`text-[11px] uppercase tracking-[.22em] ${check.passed ? "text-command-green" : "text-command-red"}`}>{check.status}</span>
                </div>
                <div className="mt-1 text-slate-400">{check.detail}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
            <FileSearch size={14} className="text-command-cyan" /> Governance Signals
          </div>
          <div className="mt-3 space-y-2 text-sm text-slate-300">
            <div className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2">
              Role distribution: {JSON.stringify(snapshot?.roleDistribution || {})}
            </div>
            <div className="rounded-2xl border border-slate-800/70 bg-slate-950/50 px-3 py-2">
              Permissions: {(snapshot?.permissions || []).join(", ") || "none"}
            </div>
            {(snapshot?.warnings || []).length ? (
              snapshot.warnings.map((warning) => (
                <div key={warning} className="rounded-2xl border border-command-amber/20 bg-command-amber/10 px-3 py-2">
                  {warning}
                </div>
              ))
            ) : null}
            {(snapshot?.blockers || []).length ? (
              snapshot.blockers.map((blocker) => (
                <div key={blocker} className="rounded-2xl border border-command-red/20 bg-command-red/10 px-3 py-2">
                  <span className="mr-2 inline-flex items-center gap-2 text-command-red">
                    <AlertTriangle size={13} /> Blocker
                  </span>
                  {blocker}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-slate-500">No governance blockers detected.</div>
            )}
          </div>
        </div>
      </div>
    </SectionPanel>
  );
}
