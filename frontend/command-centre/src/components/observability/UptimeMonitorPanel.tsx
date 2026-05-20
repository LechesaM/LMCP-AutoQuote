import { ShieldCheck } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import TelemetryStat from "../ui/TelemetryStat.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function UptimeMonitorPanel({ uptime = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  const snapshot = uptime.uptime || uptime;
  if (loading) {
    return (
      <SectionPanel title="Uptime Monitor" description="API and deployment availability view." state="loading">
        <SkeletonCard lines={3} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="Uptime Monitor"
      description="Read-only availability view for supervised-live runtime operations."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {snapshot.dataSource || "runtime_fallback"}
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <TelemetryStat label="API Uptime" value={`${Number(snapshot.apiUptimePercentage || 0).toFixed(2)}%`} description="Observed runtime availability" tone="green" />
        <TelemetryStat label="Observed Window" value={`${Number(snapshot.observedWindowMinutes || 0).toFixed(0)}m`} description="Monitoring window" tone="cyan" />
        <TelemetryStat label="Status" value={snapshot.status || "degraded"} description="Operational health state" tone={snapshot.status === "healthy" ? "green" : snapshot.status === "degraded" ? "amber" : "red"} />
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
          <ShieldCheck size={14} className="text-command-green" /> Deployment Discipline
        </div>
        <div className="mt-2 text-slate-400">Observability is read-only and does not change workflow transitions or submission behavior.</div>
      </div>
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
