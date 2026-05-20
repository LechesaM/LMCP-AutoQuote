import { BellRing, Webhook } from "lucide-react";
import SectionPanel from "../ui/SectionPanel.tsx";
import { SkeletonCard } from "../ui/SkeletonBlocks.tsx";

export default function AlertRoutingPanel({ alerts = {}, loading = false, refreshing = false, stale = false, error = "", onRetry = null }) {
  const statusState = error ? "error" : loading ? "loading" : stale ? "stale" : refreshing ? "refreshing" : "ready";
  const routes = alerts.alerts || [];
  if (loading) {
    return (
      <SectionPanel title="Alert Routing" description="Advisory routing targets for runtime alerts." state="loading">
        <SkeletonCard lines={3} />
      </SectionPanel>
    );
  }
  return (
    <SectionPanel
      title="Alert Routing"
      description="Routes alerts to logs, incidents and operator notifications without autonomous remediation."
      state={statusState}
      actions={
        <div className="rounded-full border border-slate-700/60 bg-slate-950/55 px-3 py-1 text-[10px] font-black uppercase tracking-[.24em] text-slate-300">
          {alerts.dataSource || "runtime_fallback"}
        </div>
      }
    >
      {error ? <div className="rounded-2xl border border-command-red/30 bg-command-red/10 px-4 py-3 text-sm text-slate-200">{error}</div> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {(routes || []).slice(0, 6).map((route) => (
          <div key={route.alertId} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
                <BellRing size={13} className="text-command-cyan" /> {route.category}
              </div>
              <div className="rounded-full border border-slate-700/60 px-2 py-1 text-[10px] uppercase tracking-[.24em] text-slate-400">{route.severity}</div>
            </div>
            <div className="mt-2 text-slate-400">Targets: {(route.targets || []).join(", ") || "runtime_log"}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 text-sm text-slate-300">
        <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[.24em] text-slate-400">
          <Webhook size={14} className="text-command-amber" /> Advisory Count
        </div>
        <div className="mt-2 text-slate-400">Routes generated: {alerts.routeCount || 0}. No remediation actions are triggered.</div>
      </div>
      {onRetry ? (
        <button onClick={onRetry} type="button" className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan">
          Retry
        </button>
      ) : null}
    </SectionPanel>
  );
}
