import { FileText } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function LogAggregationPanel({ logs = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  const snapshot = logs.logs || logs;
  if (loading) {
    return (
      <SectionPanel title="Log Aggregation" description="Structured operational log summaries." state="loading">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="Log Aggregation"
      description="Aggregated auth, operator, runtime alert and incident logs with redaction."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {snapshot.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Total Logs</div>
          <div className="mt-2 text-3xl font-black text-white">{snapshot.totalLogs || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Critical</div>
          <div className="mt-2 text-3xl font-black text-white">{snapshot.severityDistribution?.critical || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Warning</div>
          <div className="mt-2 text-3xl font-black text-white">{snapshot.severityDistribution?.warning || 0}</div>
        </div>
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
          <FileText size={14} className="text-command-cyan" /> Redacted Samples
        </div>
        <div className="mt-2 space-y-2">
          {(snapshot.redactedSamples || []).slice(0, 3).map((sample, index) => (
            <div key={index} className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-3 py-2 text-xs text-slate-400">
              {sample}
            </div>
          ))}
        </div>
      </div>
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
