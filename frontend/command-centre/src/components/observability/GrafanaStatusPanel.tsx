import { LayoutDashboard, PanelTopOpen } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function GrafanaStatusPanel({ grafana = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  if (loading) {
    return (
      <SectionPanel title="Grafana Status" description="Dashboard definitions for runtime observability." state="loading">
        <SkeletonCard lines={4} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="Grafana Status"
      description="Dashboard definitions for runtime health, SLA, queue and persistence monitoring."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {grafana.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="text-[10px] font-black uppercase tracking-[.24em] text-slate-400">Dashboard Count</div>
          <div className="mt-2 text-3xl font-black text-white">{grafana.count || 0}</div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[.24em] text-slate-400">
            <LayoutDashboard size={13} className="text-command-green" /> Titles
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(grafana.dashboards || []).slice(0, 4).map((dashboard) => (
              <span key={dashboard.uid || dashboard.title} className="rounded-full border border-slate-700/60 bg-slate-950/55 px-2 py-1 text-[10px] text-slate-300">
                {dashboard.title}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[.24em] text-slate-400">
            <PanelTopOpen size={13} className="text-command-cyan" /> Readiness
          </div>
          <div className="mt-2 text-slate-400">No external Grafana dependency is required for the current contract.</div>
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
